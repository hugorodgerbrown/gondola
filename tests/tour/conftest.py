"""Shared fixtures for the tour tests: the demo's resorts and a tourist."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.resorts.models import Resort
from apps.tour.demo import RESORTS
from tests.factories import ResortFactory, UserFactory


@pytest.fixture
def resorts(db: None) -> dict[str, Resort]:
    """Return the five resorts the demo uses, by code."""
    return {code: ResortFactory.create(name=name, code=code) for code, name in RESORTS.items()}


@pytest.fixture
def tourist(db: None) -> User:
    """Return someone about to take the tour."""
    return UserFactory.create(display_name="Tess")


@pytest.fixture
def touring(client: Client, tourist: User, resorts: dict[str, Resort]) -> Client:
    """Return a client signed in as ``tourist``, part way into the tour."""
    client.force_login(tourist)
    client.post("/tour/start/", {"next": "/map/"})
    return client
