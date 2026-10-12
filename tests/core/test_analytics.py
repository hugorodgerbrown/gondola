"""Tests for apps/core/analytics.py: fivebar's tag and its event queue."""

from __future__ import annotations

import pytest
from django.test import Client, RequestFactory
from django.urls import resolve, reverse

from apps.core.analytics import SCRIPT, counted_path, pending, record
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def fivebar(settings: object) -> None:
    settings.FIVEBAR_DOMAIN = "gondola.ultraniche.ai"  # type: ignore[attr-defined]


def test_no_tag_while_fivebar_is_off(client: Client) -> None:
    assert SCRIPT.encode() not in client.get("/").content


@pytest.mark.usefixtures("fivebar")
def test_every_page_carries_the_tag(client: Client) -> None:
    content = client.get("/").content
    assert b'data-domain="gondola.ultraniche.ai"' in content
    assert SCRIPT.encode() in content
    assert b"js/analytics.js" in content


@pytest.mark.usefixtures("fivebar")
def test_a_page_with_a_token_is_counted_under_its_route(client: Client) -> None:
    content = client.get(reverse("planning:invite", args=["secret"])).content
    assert b'data-path="/i/:token/"' in content
    assert b"secret" not in content.split(b"<body")[0]


def test_counted_path_names_the_values() -> None:
    request = RequestFactory().get("/i/abc/")
    assert counted_path(request) == ""  # no match resolved yet
    request.resolver_match = resolve("/i/abc/")
    assert counted_path(request) == "/i/:token/"
    request.resolver_match = resolve("/days/")
    assert counted_path(request) == ""


@pytest.mark.usefixtures("fivebar")
def test_events_wait_for_a_full_page_and_go_once(client: Client) -> None:
    client.force_login(UserFactory.create())
    request = RequestFactory().get("/")
    request.session = client.session
    record(request, "Tour started", replay=False)
    request.session.save()
    assert pending(request) == [["Tour started", {"replay": False}]]
    assert pending(request) == []


@pytest.mark.usefixtures("fivebar")
def test_too_much_data_is_refused() -> None:
    request = RequestFactory().get("/")
    request.session = {}  # type: ignore[assignment]
    with pytest.raises(ValueError, match="at most 8"):
        record(request, "Big", **{f"k{n}": n for n in range(9)})
