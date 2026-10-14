"""The public pages: the front page, terms, privacy and help.

They sit outside the installed app's /app/ scope, so the service worker
never caches them and they never show inside the installed app.
"""

import calendar
import datetime
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.public.connector import mcp_url

# The front page's made-up month: day -> (kind, friends, resort code). "in" is
# a day you said (blue); "friends" a day you haven't, where your group will be
# (pale blue, "…" when some are elsewhere). Friends: "user" for one, "people"
# for more, as on the real calendar.
DEMO_MONTH = datetime.date(2027, 1, 1)
DEMO_DAYS: dict[int, tuple[str, str, str]] = {
    2: ("in", "people", "VER"),
    3: ("in", "people", "VER"),
    9: ("in", "people", "VER"),
    10: ("in", "people", "VER"),
    11: ("in", "people", "VER"),
    12: ("friends", "user", "CHA"),
    13: ("friends", "people", "VER …"),
    14: ("in", "people", "CRA"),
    15: ("in", "user", "SAA"),
    23: ("in", "people", "ZER"),
    24: ("in", "user", "ZER"),
    30: ("friends", "people", "VER"),
    31: ("friends", "user", "VER"),
}
DEMO_SELECTED = 9


def demo_weeks() -> list[list[dict[str, Any] | None]]:
    """Return the demo month as weeks of days, Monday first; None pads a week."""
    weeks = calendar.Calendar().monthdayscalendar(DEMO_MONTH.year, DEMO_MONTH.month)
    return [[_demo_day(day) if day else None for day in week] for week in weeks]


def _demo_day(day: int) -> dict[str, Any]:
    """Return one day of the demo month, as the template draws it."""
    kind, friends, code = DEMO_DAYS.get(day, ("", "", ""))
    return {
        "day": day,
        "kind": kind,
        "friends": friends,
        "code": code,
        "selected": day == DEMO_SELECTED,
    }


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """The front page: what Gondola is, and the way in.

    Signed in, it shows too (the account page links to it); its topbar then
    offers the app, and Start a group goes straight to the groups.
    """
    context = {"mcp_url": mcp_url(), "demo_month": DEMO_MONTH, "demo_weeks": demo_weeks()}
    return render(request, "public/home.html", context)


@require_GET
def terms(request: HttpRequest) -> HttpResponse:
    """The terms of service."""
    return render(request, "public/terms.html")


@require_GET
def privacy(request: HttpRequest) -> HttpResponse:
    """The privacy notice."""
    return render(request, "public/privacy.html")


@require_GET
def help_page(request: HttpRequest) -> HttpResponse:
    """Help: signing in, passkeys, groups, days, the app, offline and AI chats."""
    return render(request, "public/help.html", {"mcp_url": mcp_url()})
