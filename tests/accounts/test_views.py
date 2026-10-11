"""Tests for apps/accounts/views.py."""

import re

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import make_sign_in_token, make_unsubscribe_token
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _link_from_outbox() -> str:
    match = re.search(r"http://testserver(/sign-in/[^\s]+/)", str(mail.outbox[-1].body))
    assert match
    return match.group(1)


def test_sign_in_page_renders(client: Client) -> None:
    response = client.get(reverse("accounts:sign_in"))
    assert response.status_code == 200
    assert b"Email me a link" in response.content


def test_full_sign_up_flow(client: Client) -> None:
    response = client.post(
        reverse("accounts:sign_in"), {"email": "Hugo@Example.com", "next": "/days/"}
    )
    assert response["Location"] == reverse("accounts:check_email")
    page = client.get(response["Location"])
    assert b"hugo@example.com" in page.content
    assert b"Open the sign-in link" in page.content  # DEBUG shows the link
    welcome = client.get(_link_from_outbox())
    assert welcome["Location"] == f"{reverse('accounts:welcome')}?next=%2Fdays%2F"
    assert client.get(welcome["Location"]).status_code == 200
    done = client.post(
        reverse("accounts:welcome"), {"display_name": " Hugo ", "next": "/days/"}
    )
    # A passkey is suggested once, on the way to where they were going.
    assert done["Location"] == f"{reverse('accounts:passkey_welcome')}?next=%2Fdays%2F"
    nudge = client.get(done["Location"])
    assert b"Add a passkey?" in nudge.content
    assert nudge.context["next_url"] == "/days/"
    assert User.objects.get(email="hugo@example.com").display_name == "Hugo"


def test_new_account_keeps_every_query_parameter_of_next(client: Client) -> None:
    next_url = "/map/?date=2027-01-16&pass=magic-pass"
    client.post(
        reverse("accounts:sign_in"), {"email": "new@example.com", "next": next_url}
    )
    welcome = client.get(_link_from_outbox())
    page = client.get(welcome["Location"])
    assert page.status_code == 200
    done = client.post(
        reverse("accounts:welcome"),
        {"display_name": "New", "next": page.context["next_url"]},
    )
    assert client.get(done["Location"]).context["next_url"] == next_url


def test_welcome_requires_a_name(client: Client) -> None:
    client.force_login(UserFactory.create(display_name=""))
    response = client.post(reverse("accounts:welcome"), {"display_name": ""})
    assert response.status_code == 200
    assert b"required" in response.content


def test_named_user_goes_straight_to_next(client: Client) -> None:
    user = UserFactory.create()
    token = make_sign_in_token(user.email, "/groups/")
    response = client.get(reverse("accounts:verify", kwargs={"token": token}))
    assert response["Location"] == "/groups/"


def test_used_link_shows_error(client: Client) -> None:
    response = client.get(reverse("accounts:verify", kwargs={"token": "bad"}))
    assert response.status_code == 400
    assert b"not valid" in response.content


def test_signed_in_user_skips_sign_in(client: Client) -> None:
    client.force_login(UserFactory.create())
    response = client.get(reverse("accounts:sign_in") + "?next=/days/")
    assert response["Location"] == "/days/"


def test_rate_limited_sign_in(client: Client) -> None:
    for _ in range(5):
        client.post(reverse("accounts:sign_in"), {"email": "x@example.com"})
    response = client.post(reverse("accounts:sign_in"), {"email": "x@example.com"})
    assert response.status_code == 200
    assert b"Too many links" in response.content
    assert len(mail.outbox) == 5


def test_settings_saves(client: Client) -> None:
    user = UserFactory.create()
    client.force_login(user)
    assert client.get(reverse("accounts:settings")).status_code == 200
    response = client.post(reverse("accounts:settings"), {"display_name": "Jo"})
    assert response["Location"] == reverse("accounts:settings")
    user.refresh_from_db()
    assert user.display_name == "Jo"
    assert user.evening_email_enabled is False


def test_sign_out_goes_straight_home(client: Client) -> None:
    client.force_login(UserFactory.create())
    page = client.get(reverse("accounts:settings"))
    # The page drops the worker's cached pages before posting (app.js).
    assert b"data-sign-out" in page.content
    response = client.post(reverse("accounts:sign_out"))
    assert response["Location"] == reverse("core:home")
    # Chrome on Android held the redirect while it cleared the cache.
    assert "Clear-Site-Data" not in response
    assert "_auth_user_id" not in client.session


def test_delete_account(client: Client) -> None:
    user = UserFactory.create()
    client.force_login(user)
    assert client.get(reverse("accounts:delete")).status_code == 200
    client.post(reverse("accounts:delete"))
    assert not User.objects.filter(pk=user.pk).exists()


def test_stop_evening_email(client: Client) -> None:
    user = UserFactory.create()
    url = reverse("accounts:stop_email", kwargs={"token": make_unsubscribe_token(user)})
    assert b"Stop the evening email?" in client.get(url).content
    user.refresh_from_db()
    assert user.evening_email_enabled  # a GET (link preview) changes nothing
    assert b"Stopped" in client.post(url).content
    user.refresh_from_db()
    assert not user.evening_email_enabled


def test_stop_evening_email_bad_link(client: Client) -> None:
    url = reverse("accounts:stop_email", kwargs={"token": "bad"})
    assert client.get(url).status_code == 400
