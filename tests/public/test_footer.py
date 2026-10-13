"""Tests for the site footer (DESIGN.md, "Every site has a legit footer")."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.public import conf
from apps.public.templatetags.site_footer import footer_links, site_footer

pytestmark = pytest.mark.django_db


def test_public_pages_end_with_the_footer(client: Client) -> None:
    """A public page ends with the footer: its links and the copyright."""
    content = client.get(reverse("public:home")).content.decode()
    assert 'class="site-footer"' in content
    for _label, url in footer_links():
        assert f'href="{url}"' in content
    year = timezone.localdate().year
    assert f"© {year} {escape(conf.COPYRIGHT_HOLDER)}. All rights reserved." in content


def test_app_pages_end_with_the_footer(signed_in: Client) -> None:
    """A signed-in page ends with it too."""
    content = signed_in.get(reverse("accounts:settings")).content.decode()
    assert 'class="site-footer"' in content


def test_the_footer_links_to_help_terms_and_privacy() -> None:
    """Without terms and a privacy notice, a site isn't legit."""
    names = {target.partition("#")[0] for _label, target in conf.LINKS}
    assert {"public:help", "public:terms", "public:privacy"} <= names


def test_a_link_can_name_part_of_a_page(monkeypatch: Any) -> None:
    """A "#fragment" after the URL name is kept on the link."""
    monkeypatch.setattr(conf, "LINKS", [("Use with Claude", "public:home#mcp")])
    assert footer_links() == [("Use with Claude", reverse("public:home") + "#mcp")]


def test_the_tagline_shows_only_when_set(client: Client, monkeypatch: Any) -> None:
    """An empty tagline leaves no empty line."""
    monkeypatch.setattr(conf, "TAGLINE", "")
    assert 'class="site-footer__tagline"' not in client.get(reverse("public:help")).content.decode()
    monkeypatch.setattr(conf, "TAGLINE", "Notes that work offline.")
    assert site_footer()["tagline"] == "Notes that work offline."
    assert "Notes that work offline." in client.get(reverse("public:help")).content.decode()
