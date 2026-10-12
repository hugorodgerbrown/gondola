"""
apps/tour/context_processors.py — What a page needs to play the tour.

While someone tours, every page gets ``tour.script``: the chapters played
on that page, as data for ``static/js/tour.js``, and the URLs it posts to.
The base template then shows the demo bar and loads the script. After the
tour, the real calendar gets ``tour.handoff`` (chapter 7) once.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.urls import reverse

from apps.groups.models import Group
from apps.groups.views.groups import invite_url

from .demo import DemoUnavailable, demo_week
from .script import HANDOFF, TELL_THE_GROUP, chapters_for
from .session import is_invite, take_handoff


def _page(request: HttpRequest) -> str:
    """Return the page's URL name, or "" outside the planning screens."""
    match = getattr(request, "resolver_match", None)
    if match is None or match.namespace != "planning":
        return ""
    return match.url_name or ""


def _script(request: HttpRequest, page: str) -> dict[str, object] | None:
    """Return the tour's data for this page, or ``None`` if not touring."""
    if getattr(request, "tour", None) is None:
        return None
    try:
        week = demo_week()
    except DemoUnavailable:
        return None
    return {
        "page": page,
        "chapters": chapters_for(page, week),
        "end_url": reverse("tour:end"),
        "finish_url": reverse("tour:finish"),
    }


def _handoff(request: HttpRequest) -> dict[str, object] | None:
    """Return chapter 7 for the real calendar, once, after the tour."""
    handoff = take_handoff(request)
    if handoff is None:
        return None
    user = request.user
    state = handoff.get("group", "none")
    next_url = handoff.get("next", "")
    go_url = ""
    if is_invite(next_url):
        go_url = next_url
    elif state == "none":
        go_url = reverse("planning:group_list")
    share_url = ""
    if state == "quiet":
        group = Group.objects.for_user(user).order_by("name").first()  # type: ignore[arg-type]
        share_url = invite_url(request, group) if group else ""
    return {
        "text": HANDOFF,
        "go_url": go_url,
        "share_url": share_url,
        "share_text": TELL_THE_GROUP,
    }


def tour(request: HttpRequest) -> dict[str, dict[str, object]]:
    """Expose the tour to every template as ``tour``.

    ``handoff`` is a function, so it is only taken (and forgotten) by the
    page that shows it: the real calendar.
    """
    page = _page(request)

    def handoff() -> dict[str, object] | None:
        """Return the hand-off, when the calendar asks for it."""
        return _handoff(request) if page == "calendar" else None

    return {"tour": {"script": _script(request, page), "handoff": handoff}}
