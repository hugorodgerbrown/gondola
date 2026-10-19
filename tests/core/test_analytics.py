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
    request.resolver_match = resolve("/app/days/")
    assert counted_path(request) == ""
<<<<<<< before updating


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
=======
    assert counted_path(factory.get("/nowhere/")) == ""


def test_context_has_no_path_while_off(settings: Any) -> None:
    """Off, the context names nothing, so the tag isn't drawn."""
    settings.FIVEBAR_DOMAIN = ""
    request = RequestFactory().get("/signin/link/abc/")
    request.resolver_match = resolve("/signin/link/abc/")
    assert analytics(request)["analytics"] == {
        "domain": "",
        "script": SCRIPT,
        "path": "",
        "counts_mcp": False,
    }


def test_privacy_notice_names_fivebar_only_while_on(settings: Any) -> None:
    """The notice (and its Markdown for the MCP tools) says what is counted, once it is."""
    settings.FIVEBAR_DOMAIN = ""
    assert "fivebar" not in page_as_markdown("privacy")["markdown"]
    settings.FIVEBAR_DOMAIN = DOMAIN
    markdown = page_as_markdown("privacy")["markdown"]
    assert "## Visitor counts" in markdown
    assert "fivebar" in markdown


def test_mark(settings: Any) -> None:
    """An event's fragment is added only while on, and never over another fragment."""
    settings.FIVEBAR_DOMAIN = ""
    assert mark("/app/", SIGNED_UP) == "/app/"
    settings.FIVEBAR_DOMAIN = DOMAIN
    assert mark("/app/", SIGNED_UP) == "/app/#signed-up"
    assert mark("/app/#top", SIGNED_UP) == "/app/#top"
>>>>>>> after updating
