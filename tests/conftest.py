"""
tests/conftest.py — Shared pytest configuration.

Swaps the password hasher for MD5 for the test run: PBKDF2 is slow by
design and every ``UserFactory`` pays for it. No real credential is ever
stored by the suite.
"""

from __future__ import annotations


def pytest_configure() -> None:
    """Install the cheap password hasher before any fixture builds a user."""
    from django.conf import settings

    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
