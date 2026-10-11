"""
apps/groups/views/resort_map.py — The resort map and the resort sheet.

The map page is a shell; its script fetches ``map_pins`` for the chosen
day and pass, and opens ``resort_sheet`` when a pin is tapped. The day and
the pass live in the URL, so a link to "Saturday on the Magic Pass" works.
"""

from __future__ import annotations

import datetime
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core.http import refresh, render_sheet
from apps.resorts.models import Pass, Resort

from ..models import Group, PlanDay
from ..services.plans import (
    is_plannable,
    last_plannable_day,
    plan_marks,
    set_plan,
    today,
    upcoming_plans,
)
from ..services.resort_map import map_pins, resort_day, resort_index
from .helpers import current_user, parse_day


@login_required
@require_GET
def map_page(request: HttpRequest) -> HttpResponse:
    """Show the map for a day, optionally narrowed to one pass."""
    day = parse_day(request.GET.get("date"))
    pass_slug = request.GET.get("pass", "")
    passes = list(Pass.objects.all())
    return render(
        request,
        "groups/map.html",
        {
            "day": day,
            "today": today(),
            "previous_day": day - datetime.timedelta(days=1),
            "next_day": day + datetime.timedelta(days=1),
            "pass_slug": pass_slug,
            "passes": passes,
            "has_groups": Group.objects.for_user(current_user(request)).exists(),
            "map_style_url": settings.MAP_STYLE_URL,
            "sheet_url_template": _sheet_url_template(),
            "resort_index": resort_index(),
            "last_day": last_plannable_day(),
            "marks": plan_marks(upcoming_plans(current_user(request))),
        },
    )


def _sheet_url_template() -> str:
    """Return the resort sheet URL with ``RESORT`` where the uuid goes."""
    blank = uuid.UUID(int=0)
    url = reverse("planning:resort_sheet", kwargs={"resort_uuid": blank})
    return url.replace(str(blank), "RESORT")


@login_required
@require_GET
def pins(request: HttpRequest) -> JsonResponse:
    """Return the day's pins as JSON for the map script."""
    day = parse_day(request.GET.get("date"))
    return JsonResponse(
        {
            "date": day.isoformat(),
            "pins": map_pins(current_user(request), day, request.GET.get("pass", "")),
        }
    )


@login_required
@require_GET
def resort_sheet(request: HttpRequest, resort_uuid: str) -> HttpResponse:
    """Show who from your groups is at a resort on a day."""
    resort = get_object_or_404(
        Resort.objects.prefetch_related("passes"), uuid=resort_uuid
    )
    day = parse_day(request.GET.get("date"))
    user = current_user(request)
    groups = list(Group.objects.for_user(user).order_by("name"))
    return render_sheet(
        request,
        "groups/resort_sheet.html",
        {
            "info": resort_day(user, resort, day),
            "plannable": is_plannable(day),
            "groups": groups,
        },
    )


@login_required
@require_POST
def plan_here(request: HttpRequest, resort_uuid: str) -> HttpResponse:
    """Set the day to this resort, from the resort sheet."""
    resort = get_object_or_404(Resort, uuid=resort_uuid)
    day = parse_day(request.POST.get("date"))
    url = f"{reverse('planning:map')}?date={day.isoformat()}"
    if is_plannable(day):
        user = current_user(request)
        existing = PlanDay.objects.filter(user=user, date=day).first()
        set_plan(
            user,
            day,
            PlanDay.Status.RESORT,
            resort=resort,
            is_private=existing.is_private if existing else False,
        )
    return refresh(request, url)
