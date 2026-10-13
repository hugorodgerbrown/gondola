"""``{% site_footer %}``: the footer every page ends with (apps/public/conf.py)."""

import logging
from typing import Any

from django import template
from django.urls import reverse
from django.utils import timezone

from apps.public import conf
from apps.pwa.conf import APP_NAME

logger = logging.getLogger(__name__)

register = template.Library()


def footer_links() -> list[tuple[str, str]]:
    """Return the footer's links as (label, URL), fragments kept."""
    links = []
    for label, target in conf.LINKS:
        name, _, fragment = target.partition("#")
        links.append((label, reverse(name) + (f"#{fragment}" if fragment else "")))
    return links


@register.inclusion_tag("includes/_footer.html")
def site_footer() -> dict[str, Any]:
    """Draw the site footer: name, tagline, links and this year's copyright."""
    return {
        "name": APP_NAME,
        "tagline": conf.TAGLINE,
        "links": footer_links(),
        "holder": conf.COPYRIGHT_HOLDER,
        "year": timezone.localdate().year,
    }
