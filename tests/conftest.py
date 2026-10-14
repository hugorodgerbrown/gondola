"""tests/conftest.py — Shared pytest configuration.

Swaps the password hasher for MD5 for the test run: PBKDF2 is slow by
design and every ``UserFactory`` pays for it. No real credential is ever
stored by the suite.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from apps.accounts.models import User
from tests.factories import UserFactory

IMMEDIATE = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}


@pytest.fixture(autouse=True)
def _tasks_run_inline(settings: Any) -> None:
    """Run tasks in the test's own thread, so their email is sent before the response.

    The app runs them on threads (apps.core.task_backends); its own tests
    put that backend back.
    """
    settings.TASKS = IMMEDIATE


def pytest_configure() -> None:
    """Install the cheap password hasher before any fixture builds a user."""
    from django.conf import settings

    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def user(db: None) -> User:
    """A signed-up user."""
    return UserFactory.create()


@pytest.fixture
def signed_in(client: Client, user: User) -> Client:
    """The test client, signed in as ``user``."""
    client.force_login(user)
    return client
