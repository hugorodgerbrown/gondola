"""Tests for apps/accounts/services.py."""

import pytest

from apps.accounts import services
from apps.accounts.models import User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


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
