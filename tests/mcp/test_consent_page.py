"""Tests for mcp_auth's consent page in Gondola's layout and words."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory

pytestmark = pytest.mark.django_db


def test_the_consent_page_is_in_gondolas_layout_and_words() -> None:
    """The shared page keeps Use another account, with Gondola's heading and promise."""
    request = RequestFactory().get("/o/authorize/")
    request.user = AnonymousUser()
    html = render_to_string(
        "mcp_auth/authorize.html",
        {
            "application": SimpleNamespace(name="Claude"),
            "form": [],
            "redirect_host": "claude.ai",
            "account_name": "Hugo",
            "consent_path": "/o/authorize/?client_id=x",
        },
        request=request,
    )
    assert "Connect Claude to Gondola?" in html
    assert "never their names" in html
    assert "Use another account" in html
    assert 'class="mcp-auth"' in html
    assert "<title>Connect Claude · Gondola</title>" in html
