"""
apps/groups/views/days.py — My days, and the sheet for one day.

My days lists the next two weeks. Tapping a day opens a sheet: skiing,
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
    plans_by_date,
    set_plan,
    today,
)
from .helpers import current_user


@login_required
@require_GET
def my_days(request: HttpRequest) -> HttpResponse:
    """List the next two weeks with what the person has said about each."""
    user = current_user(request)
    days = date_range(today(), MY_DAYS_SPAN)
    plans = plans_by_date(user, days)
    groups = list(Group.objects.for_user(user).order_by("name"))
    return render(
        request,
        "groups/my_days.html",
        {
            "rows": [(day, plans.get(day)) for day in days],
            "today": days[0],
            "groups": groups,
        },
    )


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
        return refresh(request, reverse("planning:my_days"))
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
        },
    )


@login_required
@require_POST
def day_clear(request: HttpRequest, day: datetime.date) -> HttpResponse:
    """Forget what the person said about a day."""
    clear_plan(current_user(request), day)
    return refresh(request, reverse("planning:my_days"))


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
