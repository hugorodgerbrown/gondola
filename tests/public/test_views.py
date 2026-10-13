"""Tests for apps.public.views: the homepage, terms, privacy and help."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

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


def test_home_shows_when_signed_in(signed_in: Client) -> None:
    """Signed in, the front page still shows, and its topbar offers the app."""
    response = signed_in.get(reverse("public:home"))
    assert response.status_code == 200
    assert b"Start a group" in response.content
    assert reverse("planning:map").encode() in response.content


def test_account_page_links_to_the_front_page(signed_in: Client) -> None:
    """The account page is the way from the app to the front page."""
    content = signed_in.get(reverse("accounts:settings")).content.decode()
    assert f'href="{reverse("public:home")}"' in content
