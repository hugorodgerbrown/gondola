"""Tests for apps/accounts/models.py."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

<<<<<<< before updating
from apps.accounts.models import SignInRequest, User, normalise_email
from tests.factories import SignInRequestFactory, UserFactory
=======
from apps.accounts.checks import email_key_is_set
from apps.accounts.models import (
    Passkey,
    SignInRequest,
    User,
    account_name,
    email_key,
    mask_email,
)
from tests.factories import PasskeyFactory, SignInRequestFactory, UserFactory
>>>>>>> after updating

pytestmark = pytest.mark.django_db


def test_normalise_email() -> None:
    assert normalise_email("  Bob@Example.COM ") == "bob@example.com"


def test_create_user_lowercases_email_and_hashes_password() -> None:
    user = User.objects.create_user("Anna@Example.com", "s3cret-pass")
    assert user.email == "anna@example.com"
    assert user.check_password("s3cret-pass")
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_without_email_fails() -> None:
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user("")


def test_create_user_without_password_has_none() -> None:
    user = User.objects.create_user("anna@example.com")
    assert not user.has_usable_password()


def test_create_user_validates_the_password() -> None:
    with pytest.raises(ValidationError):
        User.objects.create_user("anna@example.com", "123")


def test_create_superuser() -> None:
    user = User.objects.create_superuser("admin@example.com", "s3cret-pass")
    assert user.is_staff
    assert user.is_superuser


def test_save_normalises_email() -> None:
    user = UserFactory.create()
    user.email = "MIXED@Example.com"
    user.save()
    user.refresh_from_db()
    assert user.email == "mixed@example.com"


def test_natural_key_lookup_ignores_case() -> None:
    user = UserFactory.create(email="carla@example.com")
    assert User.objects.get_by_natural_key("Carla@EXAMPLE.com") == user


def test_to_string_prefers_display_name() -> None:
    user = UserFactory.create(display_name="Dani", email="dani@example.com")
    assert str(user) == "Dani"
    assert user.get_short_name() == "Dani"
    assert user.get_full_name() == "Dani"
    user.display_name = ""
    assert str(user) == "dani@example.com"


def test_querysets() -> None:
    keen = UserFactory.create()
    opted_out = UserFactory.create(evening_email_enabled=False)
    inactive = UserFactory.create(is_active=False)
    assert set(User.objects.active()) == {keen, opted_out}
    assert list(User.objects.wants_evening_email()) == [keen]
    assert inactive not in User.objects.wants_evening_email()


def test_sign_in_request_querysets() -> None:
    live = SignInRequestFactory.create(email="a@example.com")
    used = SignInRequestFactory.create(used_at=timezone.now())
    old = SignInRequestFactory.create(expires_at=timezone.now() - timedelta(minutes=1))
    assert list(SignInRequest.objects.live()) == [live]
    assert list(SignInRequest.objects.expired()) == [old]
    assert list(SignInRequest.objects.for_email(" A@Example.com")) == [live]
    assert used not in SignInRequest.objects.live()


<<<<<<< before updating
def test_sign_in_request_to_string() -> None:
    request = SignInRequestFactory.create(email="a@example.com")
    assert str(request) == "Sign-in for a@example.com (unused)"
    request.used_at = timezone.now()
    assert request.to_string() == "Sign-in for a@example.com (used)"
=======
def test_user_to_string() -> None:
    """An account reads as its masked address, or its username without one."""
    assert str(UserFactory.create(address="walker@example.com")) == "w•••@example.com"
    assert str(UserFactory.create(username="admin", masked_email="")) == "admin"


def test_the_consent_page_names_the_masked_address() -> None:
    """mcp-auth's consent page names an account by its masked address, never its key."""
    user = UserFactory.create(address="walker@example.com")
    assert account_name(user) == "w•••@example.com"
>>>>>>> after updating
