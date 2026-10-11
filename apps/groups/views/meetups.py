"""
apps/groups/views/meetups.py — Proposing a meet-up, and its shared page.

Starting a meet-up from the board or a resort sheet pre-fills the day and
the resort; the organiser only confirms. The meet-up page is public so the
link unfurls in a group chat and reads before sign-in; only group members
see who is going by name, everyone else sees a count.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..forms import MeetUpForm
from ..models import Group, MeetUp
from ..services.meetups import (
    MeetUpError,
    can_cancel,
    cancel_meetup,
    is_going,
    is_open,
    join_meetup,
    leave_meetup,
    propose_meetup,
)
from ..services.people import is_member
from ..services.suggestions import Suggestion, suggest_resorts
from .helpers import current_user, member_group, parse_day


def _initial_resort(
    request: HttpRequest, suggestions: list[Suggestion]
) -> Resort | None:
    """Return the resort to pre-select: the one asked for, else the top pick."""
    asked = request.GET.get("resort", "")
    try:
        resort = Resort.objects.filter(uuid=uuid.UUID(asked)).first()
    except ValueError:
        resort = None
    if resort:
        return resort
    return suggestions[0].resort if suggestions else None


@login_required
def meetup_new(request: HttpRequest, group_uuid: str) -> HttpResponse:
    """Propose a meet-up for one of your groups."""
    group = member_group(request, group_uuid)
    user = current_user(request)
    day = parse_day(request.POST.get("date") or request.GET.get("date"))
    suggestions = suggest_resorts(group, day, user)
    initial_resort = _initial_resort(request, suggestions)
    form = MeetUpForm(
        request.POST or None,
        initial={
            "date": day,
            "resort": initial_resort.uuid if initial_resort else None,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        meetup = propose_meetup(
            group,
            user,
            data["date"],
            data["resort"],
            start_time=data["start_time"],
            latitude=data["meeting_latitude"],
            longitude=data["meeting_longitude"],
        )
        messages.success(
            request, "Meet-up proposed. Share the link in your group chat."
        )
        return redirect("planning:meetup", token=meetup.share_token)
    selected = form["resort"].value()
    listed = {s.resort.uuid for s in suggestions}
    extra = (
        initial_resort if initial_resort and initial_resort.uuid not in listed else None
    )
    return render(
        request,
        "groups/meetup_new.html",
        {
            "group": group,
            "day": day,
            "form": form,
            "suggestions": suggestions,
            "extra": extra,
            "selected": str(selected) if selected else "",
            "map_centre": initial_resort,
            "map_style_url": settings.MAP_STYLE_URL,
        },
    )


@login_required
def meetup_choose_group(request: HttpRequest) -> HttpResponse:
    """Pick which group a meet-up is for, then go on to propose it."""
    user = current_user(request)
    groups = list(Group.objects.for_user(user).order_by("name"))
    query = request.GET.urlencode()
    if len(groups) == 1:
        url = reverse("planning:meetup_new", kwargs={"group_uuid": groups[0].uuid})
        return redirect(f"{url}?{query}")
    return render(
        request, "groups/meetup_choose_group.html", {"groups": groups, "query": query}
    )


def meetup(request: HttpRequest, token: str) -> HttpResponse:
    """Show a meet-up's shared page. Anyone with the link can read it."""
    item = get_object_or_404(
        MeetUp.objects.select_related("group", "resort", "organiser"), share_token=token
    )
    viewer = request.user if isinstance(request.user, User) else None
    member = viewer is not None and is_member(item.group, viewer)
    going = list(item.participants.select_related("user"))
    return render(
        request,
        "groups/meetup.html",
        {
            "meetup": item,
            "going": going,
            "show_names": member,
            "is_member": member,
            "is_going": viewer is not None and is_going(item, viewer),
            "is_open": is_open(item),
            "can_cancel": viewer is not None and can_cancel(item, viewer),
            "share_url": request.build_absolute_uri(),
            "map_style_url": settings.MAP_STYLE_URL,
        },
    )


@login_required
@require_POST
def meetup_join(request: HttpRequest, token: str) -> HttpResponse:
    """Join a meet-up (and its group, if you weren't in it)."""
    item = get_object_or_404(MeetUp, share_token=token)
    try:
        joined_group = join_meetup(item, current_user(request))
    except MeetUpError as exc:
        messages.error(request, str(exc))
    else:
        note = f" You're in {item.group.name} now too." if joined_group else ""
        messages.success(
            request, f"You're going. {item.date:%A} is set to {item.resort}.{note}"
        )
    return redirect("planning:meetup", token=token)


@login_required
@require_POST
def meetup_leave(request: HttpRequest, token: str) -> HttpResponse:
    """Take yourself off a meet-up."""
    item = get_object_or_404(MeetUp, share_token=token)
    try:
        leave_meetup(item, current_user(request))
    except MeetUpError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "You're off the list. Your day is unchanged.")
    return redirect("planning:meetup", token=token)


@login_required
@require_POST
def meetup_cancel(request: HttpRequest, token: str) -> HttpResponse:
    """Cancel a meet-up (organiser or group owner)."""
    item = get_object_or_404(MeetUp.objects.select_related("group"), share_token=token)
    try:
        cancel_meetup(item, current_user(request))
    except MeetUpError as exc:
        messages.error(request, str(exc))
        return redirect("planning:meetup", token=token)
    messages.success(request, "Meet-up cancelled. People's days are unchanged.")
    return redirect("planning:board", group_uuid=item.group.uuid)
