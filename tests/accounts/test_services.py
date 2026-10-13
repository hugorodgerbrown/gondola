"""Tests for apps/accounts/services.py."""

import pytest
from django.core import mail, signing
from django.test import RequestFactory

from apps.accounts import services
from apps.accounts.models import User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_new_email_creates_account_once() -> None:
    token = services.make_sign_in_token("New@Example.com", "/days/")
    result = services.read_sign_in_token(token)
    assert result.created
    assert result.user.email == "new@example.com"
    assert result.next_url == "/days/"
    assert not result.user.has_usable_password()


def test_link_dies_once_used() -> None:
    user = UserFactory.create()
    token = services.make_sign_in_token(user.email, "/")
    result = services.read_sign_in_token(token)
    assert result.user == user and not result.created
    user.last_login = user.created_at
    user.save()
    with pytest.raises(services.InvalidLink, match="already been used"):
        services.read_sign_in_token(token)


def test_tampered_link_is_refused() -> None:
    with pytest.raises(services.InvalidLink):
        services.read_sign_in_token("nonsense")


def test_link_missing_fields_is_refused() -> None:
    token = signing.dumps({"e": "a@b.c"}, salt=services.SIGN_IN_SALT)
    with pytest.raises(services.InvalidLink):
        services.read_sign_in_token(token)


def test_inactive_account_is_refused() -> None:
    user = UserFactory.create(is_active=False)
    with pytest.raises(services.InvalidLink, match="switched off"):
        services.read_sign_in_token(services.make_sign_in_token(user.email, "/"))


def test_safe_next_keeps_local_paths_only() -> None:
    request = RequestFactory().get("/")
    assert services.safe_next("/groups/", request) == "/groups/"
    assert services.safe_next("https://evil.example/", request) == "/map/"
    assert services.safe_next(None, request) == "/map/"


def test_sign_in_is_rate_limited() -> None:
    allowed = [services.sign_in_allowed("Limit@example.com") for _ in range(6)]
    assert allowed == [True] * 5 + [False]


def test_sign_in_email_is_sent() -> None:
    services.send_sign_in_email("A@Example.com", "https://x/sign-in/abc/")
    assert mail.outbox[0].to == ["a@example.com"]
    assert "https://x/sign-in/abc/" in mail.outbox[0].body


def test_unsubscribe_token_round_trip() -> None:
    user = UserFactory.create()
    assert services.read_unsubscribe_token(services.make_unsubscribe_token(user)) == user
    with pytest.raises(services.InvalidLink):
        services.read_unsubscribe_token("bad")


def test_unsubscribe_token_for_deleted_user() -> None:
    user = UserFactory.create()
    token = services.make_unsubscribe_token(user)
    User.objects.filter(pk=user.pk).delete()
    with pytest.raises(services.InvalidLink):
        services.read_unsubscribe_token(token)
