"""Tests for apps/accounts/views.py."""

import re
from typing import Any
from urllib.parse import urlencode, urlsplit

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.accounts.models import SignInRequest, User
from apps.accounts.services import make_unsubscribe_token
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SIGN_IN = reverse("accounts:sign_in")
CODE = reverse("accounts:sign_in_code")


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> None:
    """Rate-limit counters live in the cache; start each test with none."""
    cache.clear()


def request_email(client: Client, email: str = "walker@example.com", next_url: str = "") -> Any:
    """Ask for a sign-in email; return the response."""
    return client.post(SIGN_IN, {"email": email, "next": next_url})


def emailed() -> tuple[str, str]:
    """Return the path of the last email's link, and its code."""
    body = str(mail.outbox[-1].body)
    link = re.search(r"https?://\S+/sign-in/link/\S+/", body)
    code = re.search(r"^(\d{6})$", body, re.MULTILINE)
    assert link, body
    assert code, body
    return urlsplit(link.group()).path, code.group(1)


def signed_in_user(client: Client) -> User | None:
    """Return the user the client's session belongs to, or None."""
    user_id = client.session.get("_auth_user_id")
    return User.objects.filter(pk=user_id).first() if user_id else None


# ---------- asking for an email ----------


def test_sign_in_page_renders(client: Client) -> None:
    response = client.get(SIGN_IN)
    assert response.status_code == 200
    assert b"Email me a link" in response.content
    assert b"data-passkey-sign-in" in response.content


def test_signed_in_user_skips_sign_in(signed_in: Client) -> None:
    response = signed_in.get(SIGN_IN + "?next=/app/days/")
    assert response["Location"] == "/app/days/"


def test_sign_in_emails_a_link_and_a_code(client: Client) -> None:
    response = request_email(client, "Walker@Example.com")
    assert response["Location"] == CODE
    message = mail.outbox[-1]
    assert isinstance(message, mail.EmailMultiAlternatives)
    assert message.to == ["walker@example.com"]
    _, code = emailed()
    assert message.subject == f"Your Gondola sign-in code is {code}"
    assert code in str(message.alternatives[0][0])
    page = client.get(CODE)
    assert b"walker@example.com" in page.content
    assert b"30 minutes" in page.content
    assert b"Open the sign-in link" not in page.content  # DEBUG only
    assert SignInRequest.objects.get().email == "walker@example.com"


def test_debug_shows_the_link_on_the_code_page(client: Client, settings: Any) -> None:
    settings.DEBUG = True
    request_email(client)
    assert b"Open the sign-in link" in client.get(CODE).content


def test_a_bad_email_is_refused(client: Client) -> None:
    response = request_email(client, "not an email")
    assert response.status_code == 400
    assert not mail.outbox


def test_sign_in_emails_are_rate_limited(client: Client) -> None:
    for _ in range(5):
        request_email(client, "x@example.com")
    response = request_email(client, "x@example.com")
    assert response.status_code == 429
    assert b"Too many sign-in emails" in response.content
    assert len(mail.outbox) == 5


def test_code_page_needs_a_request_from_this_browser(client: Client) -> None:
    assert client.get(CODE)["Location"] == SIGN_IN


# ---------- the link ----------


def test_link_asks_for_a_click_then_signs_in(client: Client) -> None:
    """GET shows Continue without signing in (mail scanners); POST signs in."""
    UserFactory.create(email="walker@example.com")
    request_email(client, next_url="/app/groups/")
    link, _ = emailed()
    other_browser = Client()
    page = other_browser.get(link)
    assert page.status_code == 200
    assert b"walker@example.com" in page.content
    assert signed_in_user(other_browser) is None
    response = other_browser.post(link)
    assert response["Location"] == "/app/groups/"
    user = signed_in_user(other_browser)
    assert user is not None
    assert user.email == "walker@example.com"


def test_a_used_link_has_expired(client: Client) -> None:
    request_email(client)
    link, _ = emailed()
    client.post(link)
    page = Client().get(link)
    assert page.status_code == 410
    assert b"Send a new link" in page.content
    assert Client().post(link).status_code == 410


def test_a_link_for_a_switched_off_account_does_not_sign_in(client: Client) -> None:
    UserFactory.create(email="walker@example.com", is_active=False)
    request_email(client)
    link, _ = emailed()
    response = client.post(link)
    assert response.status_code == 403
    assert signed_in_user(client) is None


def test_next_from_elsewhere_is_ignored(client: Client) -> None:
    UserFactory.create(email="walker@example.com")
    request_email(client, next_url="https://evil.example/")
    link, _ = emailed()
    assert client.post(link)["Location"] == reverse("planning:map")


# ---------- the code ----------


def test_code_signs_in_this_browser(client: Client) -> None:
    UserFactory.create(email="walker@example.com")
    request_email(client, next_url="/app/days/")
    _, code = emailed()
    response = client.post(CODE, {"code": f" {code} "})
    assert response["Location"] == "/app/days/"
    assert signed_in_user(client) is not None
    assert SignInRequest.objects.get().used_at is not None


def test_code_does_not_work_in_another_browser(client: Client) -> None:
    request_email(client)
    _, code = emailed()
    other = Client()
    assert other.post(CODE, {"code": code})["Location"] == SIGN_IN
    assert signed_in_user(other) is None


def test_a_wrong_code_says_so(client: Client) -> None:
    request_email(client)
    _, code = emailed()
    wrong = "000000" if code != "000000" else "111111"
    response = client.post(CODE, {"code": wrong})
    assert response.status_code == 400
    assert b"didn&#x27;t work" in response.content
    assert client.post(CODE, {"code": "12"}).status_code == 400
    assert signed_in_user(client) is None


def test_code_guesses_are_rate_limited(client: Client) -> None:
    request_email(client)
    _, code = emailed()
    for _ in range(20):
        client.post(CODE, {"code": "12"})
    response = client.post(CODE, {"code": code})
    assert response.status_code == 429
    assert b"Too many attempts" in response.content


# ---------- the first sign-in ----------


def test_full_sign_up_flow(client: Client) -> None:
    request_email(client, "Hugo@Example.com", "/app/days/")
    _, code = emailed()
    welcome = client.post(CODE, {"code": code})
    assert welcome["Location"] == f"{reverse('accounts:welcome')}?next=%2Fapp%2Fdays%2F"
    assert client.get(welcome["Location"]).status_code == 200
    done = client.post(
        reverse("accounts:welcome"), {"display_name": " Hugo ", "next": "/app/days/"}
    )
    # A passkey is suggested once, then the tour is offered, on the way to
    # where they were going.
    offer = f"{reverse('tour:offer')}?next=%2Fapp%2Fdays%2F"
    assert done["Location"] == (
        f"{reverse('accounts:passkey_welcome')}?{urlencode({'next': offer})}"
    )
    nudge = client.get(done["Location"])
    assert b"Add a passkey?" in nudge.content
    assert nudge.context["next_url"] == offer
    assert client.get(offer).context["next_url"] == "/app/days/"
    assert User.objects.get(email="hugo@example.com").display_name == "Hugo"


def test_new_account_keeps_every_query_parameter_of_next(client: Client) -> None:
    next_url = "/app/map/?date=2027-01-16&pass=magic-pass"
    request_email(client, "new@example.com", next_url)
    link, _ = emailed()
    welcome = client.post(link)
    page = client.get(welcome["Location"])
    assert page.status_code == 200
    done = client.post(
        reverse("accounts:welcome"),
        {"display_name": "New", "next": page.context["next_url"]},
    )
    offer = client.get(done["Location"]).context["next_url"]
    assert client.get(offer).context["next_url"] == next_url


def test_welcome_requires_a_name(client: Client) -> None:
    client.force_login(UserFactory.create(display_name=""))
    response = client.post(reverse("accounts:welcome"), {"display_name": ""})
    assert response.status_code == 200
    assert b"required" in response.content


# ---------- the admin ----------


def test_admin_sign_in_is_the_normal_sign_in(client: Client) -> None:
    response = client.get("/admin/login/?next=/admin/groups/")
    assert response["Location"] == f"{SIGN_IN}?next=%2Fadmin%2Fgroups%2F"


def test_admin_refuses_signed_in_non_staff(signed_in: Client) -> None:
    assert signed_in.get("/admin/login/").status_code == 403


def test_staff_reach_the_admin_after_signing_in(client: Client) -> None:
    UserFactory.create(email="boss@example.com", is_staff=True, is_superuser=True)
    request_email(client, "boss@example.com", "/admin/")
    _, code = emailed()
    assert client.post(CODE, {"code": code})["Location"] == "/admin/"
    assert client.get("/admin/").status_code == 200


# ---------- the account page ----------


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
    assert response["Location"] == reverse("public:home")
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
