"""The public pages: the front page, terms, privacy and help.

They sit outside the installed app's /app/ scope, so the service worker
never caches them and they never show inside the installed app.
"""

import calendar
import datetime
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET


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
    return [
        [
            None
            if not day
            else {
                "day": day,
                "kind": DEMO_DAYS.get(day, ("", "", ""))[0],
                "friends": DEMO_DAYS.get(day, ("", "", ""))[1],
                "code": DEMO_DAYS.get(day, ("", "", ""))[2],
                "selected": day == DEMO_SELECTED,
            }
            for day in week
        ]
        for week in weeks
    ]


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """The front page: what Gondola is, and the way in. Signed in, the map."""
    if request.user.is_authenticated:
        return redirect("planning:map")
    mcp_url = settings.SITE_URL + reverse("mcp")
    context = {"mcp_url": mcp_url, "demo_month": DEMO_MONTH, "demo_weeks": demo_weeks()}
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
    """Help: signing in, passkeys, groups, days, installing the app, offline."""
    return render(request, "public/help.html")
