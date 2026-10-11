"""
apps/groups/views/days.py — My days, and the sheet for one day.

My days lists two weeks at a time, from today by default. Arrows step a
fortnight, and a calendar jumps to any day you can plan (``?from=``), so
December and January are as easy to fill in as next week. Plans outside
the two weeks on show are listed under them. Tapping a day opens a sheet: skiing,
not sure yet or not skiing; the resorts friends already picked that day
first, then a search over every resort; an optional note; and a switch to
keep the day private.
"""

from __future__ import annotations

import datetime

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core.http import refresh, render_sheet
from apps.resorts.models import Resort
from apps.resorts.search import search_resorts

from ..forms import DayForm
from ..models import Group, PlanDay
from ..services.plans import (
    MY_DAYS_SPAN,
    clear_plan,
    date_range,
    friends_by_resort,
    is_plannable,
    last_plannable_day,
    plan_marks,
    set_plan,
    today,
    upcoming_plans,
    window_start,
)
from .helpers import current_user, parse_day


@login_required
@require_GET
def my_days(request: HttpRequest) -> HttpResponse:
    """List two weeks of days with what the person has said about each."""
    user = current_user(request)
    start = window_start(parse_day(request.GET.get("from")))
    days = date_range(start, MY_DAYS_SPAN)
    upcoming = upcoming_plans(user)
    plans = {plan.date: plan for plan in upcoming}
    shown = set(days)
    span = datetime.timedelta(days=MY_DAYS_SPAN)
    first = today()
    last = last_plannable_day()
    return render(
        request,
        "groups/my_days.html",
        {
            "rows": [(day, plans.get(day)) for day in days],
            "today": first,
            "start": start,
            "end": days[-1],
            "previous_start": window_start(start - span) if start > first else None,
            "next_start": start + span if days[-1] < last else None,
            "elsewhere": [plan for plan in upcoming if plan.date not in shown],
            "last_day": last,
            "marks": plan_marks(upcoming),
            # Only a later fortnight needs carrying through a plain form post.
            "window_from": start if start > first else None,
            "groups": list(Group.objects.for_user(user).order_by("name")),
        },
    )


def _window_from(request: HttpRequest) -> datetime.date | None:
    """Return the My days fortnight a sheet was opened from, if not the first."""
    value = request.POST.get("from") or request.GET.get("from")
    start = window_start(parse_day(value)) if value else None
    return start if start and start > today() else None


def _my_days_url(window_from: datetime.date | None) -> str:
    """Return My days, at the fortnight the person was looking at."""
    url = reverse("planning:my_days")
    return f"{url}?from={window_from.isoformat()}" if window_from else url


def _initial(plan: PlanDay | None) -> dict[str, object]:
    """Return the form's starting values from an existing plan."""
    if plan is None:
        return {"status": PlanDay.Status.RESORT}
    return {
        "status": plan.status,
        "resort": plan.resort.uuid if plan.resort else None,
        "note": plan.note,
        "is_private": plan.is_private,
    }


def _resort_choices(
    request: HttpRequest, day: datetime.date, plan: PlanDay | None
) -> tuple[list[object], Resort | None]:
    """Return friends' resorts for the day, and the current pick if elsewhere."""
    by_resort = friends_by_resort(current_user(request), day)
    current = plan.resort if plan else None
    listed = {entry.resort.pk for entry in by_resort}
    elsewhere = current if current and current.pk not in listed else None
    return list(by_resort), elsewhere


@login_required
def day(request: HttpRequest, day: datetime.date) -> HttpResponse:
    """Show and save the sheet for one day."""
    if not is_plannable(day):
        raise Http404("That day can't be planned.")
    user = current_user(request)
    plan = PlanDay.objects.filter(user=user, date=day).select_related("resort").first()
    form = DayForm(request.POST or None, initial=_initial(plan))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        set_plan(
            user,
            day,
            data["status"],
            resort=data["resort"],
            note=data["note"],
            is_private=data["is_private"],
        )
        return refresh(request, _my_days_url(_window_from(request)))
    friends, elsewhere = _resort_choices(request, day, plan)
    selected = form["resort"].value()
    return render_sheet(
        request,
        "groups/day_sheet.html",
        {
            "day": day,
            "plan": plan,
            "form": form,
            "friends": friends,
            "elsewhere": elsewhere,
            "selected": str(selected) if selected else "",
            "groups_count": Group.objects.for_user(user).count(),
            "window_from": _window_from(request),
        },
    )


@login_required
@require_POST
def day_clear(request: HttpRequest, day: datetime.date) -> HttpResponse:
    """Forget what the person said about a day."""
    clear_plan(current_user(request), day)
    return refresh(request, _my_days_url(_window_from(request)))


@login_required
@require_GET
def resort_search(request: HttpRequest) -> HttpResponse:
    """Return resort options matching the typed text (an HTMX fragment)."""
    query = request.GET.get("q", "")
    return render(
        request,
        "groups/partials/resort_options.html",
        {
            "resorts": search_resorts(query),
            "query": query,
            "field": request.GET.get("field", "resort"),
        },
    )
