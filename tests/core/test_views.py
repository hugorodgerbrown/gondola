"""Tests for apps/core/views.py, context processors and HTTP helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from django.db import OperationalError, connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.context_processors import site
from apps.core.http import is_htmx, refresh

pytestmark = pytest.mark.django_db


def test_old_root_addresses_are_gone(client: Client) -> None:
    """Signed-in pages live under /app/ only; nothing answers at the old root."""
    assert client.get("/map/").status_code == 404
    assert client.get("/sw.js").status_code == 404


def test_site_context_without_match() -> None:
    request = RequestFactory().get("/")
    assert site(request)["tab"] == ""


def test_refresh_plain_post_redirects() -> None:
    request = RequestFactory().post("/")
    assert not is_htmx(request)
    assert refresh(request, "/app/days/")["Location"] == "/app/days/"


def test_refresh_htmx() -> None:
    request = RequestFactory().post("/", headers={"HX-Request": "true"})
    response = refresh(request, "/app/days/")
    assert response.status_code == 204
    assert response["HX-Refresh"] == "true"


def test_livez_needs_no_sign_in_or_database(client: Client) -> None:
    """Render's health check answers 200 to anyone, without a query."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("core:livez"))
    assert response.status_code == 200
    assert response.content == b"ok"
    assert len(queries) == 0
    assert "no-cache" in response["Cache-Control"]


def test_healthz_reads_the_database(client: Client) -> None:
    """/healthz answers 200 once the database answers a read."""
    response = client.get(reverse("core:healthz"))
    assert response.status_code == 200
    assert response.content == b"ok"


def test_healthz_is_503_when_the_database_fails(client: Client) -> None:
    """A failed read is a 503 with a fixed body: no driver message leaks."""
    with mock.patch("apps.core.views.get_user_model") as get_user_model:
        exists = get_user_model.return_value.objects.exists
        exists.side_effect = OperationalError("host=db.internal")
        response = client.get(reverse("core:healthz"))
    assert response.status_code == 503
    assert response.content == b"error"


@pytest.mark.django_db
def test_security_txt_follows_rfc_9116(client: Client, settings: Any) -> None:
    """security.txt is plain text naming the contact, a future Expires and its own address."""
    settings.SITE_URL = "https://example.ultraniche.ai"
    settings.SECURITY_CONTACT = "mailto:sec@ultraniche.ai"
    with CaptureQueriesContext(connection) as queries:
        response = client.get("/.well-known/security.txt")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain; charset=utf-8"
    assert "max-age=86400" in response["Cache-Control"]
    assert len(queries) == 0
    fields = dict(line.split(": ", 1) for line in response.content.decode().splitlines())
    assert fields["Contact"] == "mailto:sec@ultraniche.ai"
    assert fields["Preferred-Languages"] == "en"
    assert fields["Canonical"] == "https://example.ultraniche.ai/.well-known/security.txt"
    expires = datetime.fromisoformat(fields["Expires"])
    assert fields["Expires"].endswith("Z")
    now = datetime.now(UTC)
    assert now + timedelta(days=179) < expires < now + timedelta(days=365)
