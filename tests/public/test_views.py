"""Tests for apps.public.views: the homepage, terms, privacy and help."""

import re
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from apps.public import views

pytestmark = pytest.mark.django_db


PAGES = ["public:home", "public:terms", "public:privacy", "public:help"]


@pytest.mark.parametrize("name", PAGES)
def test_public_pages_need_no_sign_in(client: Client, name: str) -> None:
    """Anyone can read them, and they link to each other."""
    response = client.get(reverse(name))
    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("public:terms") in content
    assert reverse("public:privacy") in content
    assert reverse("public:help") in content


@pytest.mark.parametrize("name", PAGES)
def test_public_pages_are_outside_the_app(client: Client, name: str) -> None:
    """No manifest, worker or outbox: the installed app is /app/ alone."""
    content = client.get(reverse(name)).content.decode()
    assert "manifest" not in content
    assert "pwa.js" not in content


def test_home_invites_sign_in(client: Client) -> None:
    """Signed out, the homepage's call to action is signing in."""
    content = client.get(reverse("public:home")).content.decode()
    assert reverse("accounts:sign_in") in content


def test_home_shows_what_the_app_does(client: Client) -> None:
    """A fortnight in the calendar's own cells shows what the app does."""
    response = client.get(reverse("public:home"))
    assert b"Start a group" in response.content
    assert b"<title>Gondola</title>" in response.content
    assert b"demo-month" in response.content
    assert b"January 2027" in response.content
    assert b"mday--in" in response.content
    # Public: no service worker, no outbox.
    assert b"pwa.js" not in response.content


def test_home_start_a_group_signs_in_to_the_groups(client: Client) -> None:
    """Start a group signs in, then lands on the groups page to start one."""
    content = client.get(reverse("public:home")).content.decode()
    groups = reverse("planning:group_list").replace("/", "%2F")
    assert f"{reverse('accounts:sign_in')}?next={groups}" in content


def test_home_gives_the_mcp_connector_address(client: Client, settings: Any) -> None:
    """The front page names the address to add Gondola to an AI chat."""
    settings.SITE_URL = "https://gondola.example"
    content = client.get(reverse("public:home")).content.decode()
    assert "https://gondola.example/mcp" in content
    assert 'data-copy="https://gondola.example/mcp"' in content


def primary_actions(content: str) -> list[tuple[str, str]]:
    """The front page's primary actions, as (href, label): the block buttons."""
    pattern = r'<a class="button button--block[^"]*" href="([^"]*)">([^<]*)</a>'
    return [(match[1], match[2]) for match in re.finditer(pattern, content)]


def test_home_has_one_promise(client: Client) -> None:
    """One H1, and it is the promise, not the app's name (the header says that)."""
    content = client.get(reverse("public:home")).content.decode()
    assert content.count("<h1") == 1
    assert '<h1 class="splash__title">Ski the same mountain.</h1>' in content


def test_home_offers_one_way_in(client: Client) -> None:
    """Signed out, both primary actions sign in and land on the groups, to start one."""
    content = client.get(reverse("public:home")).content.decode()
    groups = reverse("planning:group_list").replace("/", "%2F")
    first_job = f"{reverse('accounts:sign_in')}?next={groups}"
    assert primary_actions(content) == [(first_job, "Start a group")] * 2
    assert "Create an account" not in content


def test_home_opens_the_app_when_signed_in(signed_in: Client) -> None:
    """Signed in, the page changes its offer, not its shape: everything opens the app."""
    content = signed_in.get(reverse("public:home")).content.decode()
    assert primary_actions(content) == [(reverse("planning:map"), "Open the app")] * 2
    header = content[content.index("<header") : content.index("</header>")]
    assert "Open the app" in header
    assert "Sign in" not in content
    assert "Start a group" not in content


def test_home_links_to_the_connector_steps(client: Client) -> None:
    """The steps for Claude and ChatGPT live on the help page; the front page links there."""
    content = client.get(reverse("public:home")).content.decode()
    assert f'href="{reverse("public:help")}#use-with-ai"' in content


def test_home_leaves_the_connector_out_without_mcp(client: Client, monkeypatch: Any) -> None:
    """With no /mcp to add, the AI-chat section goes."""
    monkeypatch.setattr(views, "mcp_url", lambda: "")
    content = client.get(reverse("public:home")).content.decode()
    assert 'class="chat"' not in content
    assert "data-copy" not in content


def test_help_gives_the_steps_for_claude_and_chatgpt(client: Client, settings: Any) -> None:
    """The steps every Titan app shares, around the address to copy."""
    settings.SITE_URL = "https://gondola.example"
    content = client.get(reverse("public:help")).content.decode()
    assert 'id="use-with-ai"' in content
    assert "<h3>Claude</h3>" in content
    assert "<h3>ChatGPT</h3>" in content
    assert 'data-copy="https://gondola.example/mcp"' in content


def test_help_leaves_the_steps_out_without_mcp(client: Client, monkeypatch: Any) -> None:
    """No connector, no steps."""
    monkeypatch.setattr(views, "mcp_url", lambda: "")
    content = client.get(reverse("public:help")).content.decode()
    assert 'id="use-with-ai"' not in content


APP_PAGES = ["accounts:settings", "planning:calendar", "planning:group_list", "planning:map"]


@pytest.mark.parametrize("name", APP_PAGES)
def test_app_pages_have_no_footer(signed_in: Client, name: str) -> None:
    """The app is an app, not a website: its links are on the account page."""
    assert b'class="site-footer"' not in signed_in.get(reverse(name)).content


@pytest.mark.parametrize("name", APP_PAGES)
def test_the_app_logo_goes_to_the_front_page(signed_in: Client, name: str) -> None:
    """The top-left mark links to the front page, the way to it from the app."""
    content = signed_in.get(reverse(name)).content.decode()
    assert f'class="topbar__brand" href="{reverse("public:home")}"' in content


def test_the_chat_sample_names_no_friend(client: Client) -> None:
    """The connector counts friends and never names them, so the sample doesn't either."""
    content = client.get(reverse("public:home")).content.decode()
    assert "2 friends on Saturday" in content
    for name in ("Anna", "Ben", "Chloé", "Ella"):
        assert name not in content
