"""
apps/core/context_processors.py — Template context every page needs.

Adds the product name and the active bottom tab, so the base template can
title the page and highlight where the person is.
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest

# Which bottom tab each planning URL belongs to.
TABS: dict[str, str] = {
    "map": "map",
    "resort_sheet": "map",
    "my_days": "days",
    "day": "days",
    "group_list": "groups",
    "group_detail": "groups",
    "board": "groups",
    "meetup_new": "groups",
    "meetup": "groups",
}


def site(request: HttpRequest) -> dict[str, object]:
    """Return the site name and the bottom tab the page belongs to."""
    match = getattr(request, "resolver_match", None)
    url_name = match.url_name if match else ""
    return {"SITE_NAME": settings.SITE_NAME, "tab": TABS.get(url_name or "", "")}
