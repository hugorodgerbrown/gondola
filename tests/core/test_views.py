"""Tests for apps/core/views.py, context processors and HTTP helpers."""

import json

import pytest
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.core.context_processors import site
from apps.core.http import is_htmx, refresh
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_home_signed_out(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert b"Get started" in response.content
    assert b"<title>Gondola</title>" in response.content
    # A picture of the board shows what the app does before anyone signs in.
    assert b"img/home-board" in response.content
    # app.js drops the cached pages of whoever was signed in.
    assert b"data-forget-pages" in response.content


def test_home_signed_in_goes_to_map(client: Client) -> None:
    client.force_login(UserFactory.create())
    assert client.get("/")["Location"] == reverse("planning:map")


def test_manifest(client: Client) -> None:
    data = json.loads(client.get(reverse("core:manifest")).content)
    assert data["display"] == "standalone"
    assert data["start_url"] == "/map/"
    assert data["name"] == data["short_name"] == "Gondola"
    maskable = [i["src"] for i in data["icons"] if i.get("purpose") == "maskable"]
    assert maskable and all("maskable" in src for src in maskable)


def test_service_worker(client: Client) -> None:
    response = client.get(reverse("core:service_worker"))
    assert response["Content-Type"] == "application/javascript"
    assert b'"/offline/"' in response.content


def test_offline_page(client: Client) -> None:
    assert b"No signal" in client.get(reverse("core:offline")).content


def test_site_context_without_match() -> None:
    request = RequestFactory().get("/")
    assert site(request)["tab"] == ""


def test_refresh_plain_post_redirects() -> None:
    request = RequestFactory().post("/")
    assert not is_htmx(request)
    assert refresh(request, "/days/")["Location"] == "/days/"


def test_refresh_htmx() -> None:
    request = RequestFactory().post("/", headers={"HX-Request": "true"})
    response = refresh(request, "/days/")
    assert response.status_code == 204
    assert response["HX-Refresh"] == "true"
