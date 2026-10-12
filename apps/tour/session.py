"""
apps/tour/session.py — Who is touring, kept in their session.

The session names the person's demo group and where they were headed
before the tour (``next``). ``apps.tour.middleware`` reads it on every
request. Two more keys carry the tour's edges: ``OFFER_KEY`` holds back
the offer for someone who signed up through an invite link until they've
joined, and ``HANDOFF_KEY`` carries chapter 7's hand-off to the real My
days, shown once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.http import HttpRequest
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.utils.http import urlencode

from apps.accounts.models import User
from apps.groups.models import Group, PlanDay
from apps.groups.services.people import friend_ids
from apps.groups.services.plans import today

from .demo import discard_demos

TOUR_KEY = "tour"
OFFER_KEY = "tour_offer"
HANDOFF_KEY = "tour_handoff"

GroupState = Literal["busy", "quiet", "none"]


@dataclass(frozen=True)
class Tour:
    """A tour in progress: the person's demo copy and where they were headed."""

    group: Group
    next_url: str


def begin(request: HttpRequest, group: Group, next_url: str) -> None:
    """Remember that the person is touring ``group``."""
    request.session[TOUR_KEY] = {"group": str(group.uuid), "next": next_url}


def tour_state(request: HttpRequest) -> dict[str, str] | None:
    """Return the session's tour state, if the person is touring."""
    state = request.session.get(TOUR_KEY)
    return state if isinstance(state, dict) and state.get("group") else None


def stop(request: HttpRequest, user: User) -> str:
    """End the tour: delete the demo copy, forget it; return where they were headed."""
    state = tour_state(request) or {}
    request.session.pop(TOUR_KEY, None)
    discard_demos(user)
    # The rest of this request sees the person's real groups again.
    user.tour_group_id = None  # type: ignore[attr-defined]
    return state.get("next", "")


def group_state(user: User) -> GroupState:
    """Return whether ``user``'s real groups are busy, quiet or missing.

    Busy: a friend has said something about a day from today on. Quiet:
    they're in a group, but nobody else has yet.
    """
    if not Group.objects.for_user(user).exists():
        return "none"
    busy = PlanDay.objects.filter(
        user_id__in=friend_ids(user), date__gte=today()
    ).exists()
    return "busy" if busy else "quiet"


def finish(request: HttpRequest, user: User) -> GroupState:
    """Finish the tour and set up the hand-off; return the group state."""
    next_url = stop(request, user)
    user.toured_at = timezone.now()
    user.save(update_fields=["toured_at", "updated_at"])
    state = group_state(user)
    request.session[HANDOFF_KEY] = {"group": state, "next": next_url}
    return state


def take_handoff(request: HttpRequest) -> dict[str, str] | None:
    """Return chapter 7's hand-off and forget it: it shows once."""
    handoff = request.session.pop(HANDOFF_KEY, None)
    return handoff if isinstance(handoff, dict) else None


def is_invite(url: str) -> bool:
    """Return whether ``url`` is a group's invite link."""
    try:
        match = resolve(url.split("?")[0])
    except Resolver404:
        return False
    return match.view_name == "planning:invite"


def offer_url(next_url: str) -> str:
    """Return the tour's welcome, going on to ``next_url`` after."""
    return f"{reverse('tour:offer')}?{urlencode({'next': next_url})}"


def after_welcome(request: HttpRequest, next_url: str) -> str:
    """Return where a new account goes after its name and passkey screens.

    The tour is offered there, once. Someone who came from an invite link
    joins first, so the offer waits until they have (``after_join``).
    """
    if is_invite(next_url):
        request.session[OFFER_KEY] = True
        return next_url
    return offer_url(next_url)


def after_join(request: HttpRequest, group_url: str) -> str:
    """Return where joining a group goes: the held-back offer, else the group."""
    if request.session.pop(OFFER_KEY, False):
        return offer_url(group_url)
    return group_url
