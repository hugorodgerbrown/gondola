"""Tests for apps.public.views: the homepage, terms, privacy and help."""

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
    """A picture of the calendar shows what the app does before anyone signs in."""
    response = client.get(reverse("public:home"))
    assert b"Get started" in response.content
    assert b"<title>Gondola</title>" in response.content
    assert b"img/home-calendar" in response.content
    # Public: no service worker, no outbox.
    assert b"pwa.js" not in response.content


def test_home_signed_in_goes_to_the_map(signed_in: Client) -> None:
    """Signed in, the front page opens the app."""
    assert signed_in.get(reverse("public:home"))["Location"] == reverse("planning:map")
