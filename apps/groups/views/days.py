"""
apps/groups/views/days.py — My days, and the sheet for one day.

My days is a month calendar, this month by default; arrows step a month
(``?from=``, any day in it) as far as plans can be made. Each day shows
what you said about it and what your groups are up to: friends skiing,
friends at your resort, and a meet-up. Tapping a day opens a sheet: skiing,
not sure yet or not skiing; the resorts friends already picked that day
first, then a search over every resort; an optional note; and a switch to
keep the day private.

Pressing and holding a day starts selecting: tap more days (or drag
across a run), then one sheet plans them all the same (``?days=``).
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
from ..services.month import build_month, month_start
from ..services.plans import (
    clear_plan,
    clear_plans,
    friends_by_resort,
    is_plannable,
    join_names,
    set_plan,
    set_plans,
    today,
)
from .helpers import current_user, parse_day

# The most days one selection can plan.
MAX_SELECTED_DAYS = 62


@login_required
@require_GET
def my_days(request: HttpRequest) -> HttpResponse:
    """Show a month of days: the person's plans and their groups' activity."""
    user = current_user(request)
    month = build_month(user, parse_day(request.GET.get("from")))
    return render(
        request,
        "groups/my_days.html",
        {
            "month": month,
            "today": today(),
            # Only a later month needs carrying through a plain form post.
            "window_from": _later_month(month.first),
            "groups": list(Group.objects.for_user(user).order_by("name")),
            "max_selected": MAX_SELECTED_DAYS,
        },
    )


def _later_month(first: datetime.date) -> datetime.date | None:
    """Return ``first`` if it is a month after this one, else ``None``."""
    return first if first > today().replace(day=1) else None


def _window_from(request: HttpRequest) -> datetime.date | None:
    """Return the My days month a sheet was opened from, if not this month."""
    value = request.POST.get("from") or request.GET.get("from")
    return _later_month(month_start(parse_day(value))) if value else None


def _my_days_url(window_from: datetime.date | None) -> str:
    """Return My days, at the month the person was looking at."""
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
    request: HttpRequest, days: list[datetime.date], plan: PlanDay | None
) -> tuple[list[object], Resort | None]:
    """Return friends' resorts on the days, and the current pick if elsewhere."""
    by_resort = friends_by_resort(current_user(request), days)
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
    friends, elsewhere = _resort_choices(request, [day], plan)
    selected = form["resort"].value()
    return render_sheet(
        request,
        "groups/day_sheet.html",
        {
            "day": day,
            "eyebrow": "My days",
            "title": f"{day:%A} {day.day} {day:%B}",
            "save_label": f"Save {day:%a} {day.day} {day:%b}",
            "form_url": reverse("planning:day", kwargs={"day": day}),
            "clear_url": reverse("planning:day_clear", kwargs={"day": day}),
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


def _selected_days(request: HttpRequest) -> list[datetime.date]:
    """Return the selected days (``days=2026-12-14,2026-12-20``), or 404."""
    raw = request.POST.get("days") or request.GET.get("days") or ""
    try:
        days = sorted({datetime.date.fromisoformat(part) for part in raw.split(",")})
    except ValueError:
        raise Http404("Those days can't be planned.") from None
    if len(days) > MAX_SELECTED_DAYS or not all(is_plannable(d) for d in days):
        raise Http404("Those days can't be planned.")
    return days


def _days_title(days: list[datetime.date]) -> str:
    """Return the selection in words: a run, a short list, or a count."""
    first, last = days[0], days[-1]
    if len(days) == 1:
        return f"{first:%A} {first.day} {first:%B}"
    if (last - first).days + 1 == len(days):
        start = f"{first:%a} {first.day}"
        if first.month != last.month:
            start += f" {first:%B}"
        return f"{start} – {last:%a} {last.day} {last:%B}"
    if len(days) <= 4:
        names = []
        for index, day in enumerate(days):
            name = f"{day:%a} {day.day}"
            following = days[index + 1] if index + 1 < len(days) else None
            if following is None or following.month != day.month:
                name += f" {day:%B}"
            names.append(name)
        return join_names(names)
    span = f"{first.day} {first:%B}" if first.month != last.month else str(first.day)
    return f"{len(days)} days, {span} – {last.day} {last:%B}"


def _days_query(days: list[datetime.date]) -> str:
    """Return the selection as a query string."""
    return "?days=" + ",".join(day.isoformat() for day in days)


@login_required
def several_days(request: HttpRequest) -> HttpResponse:
    """Show and save one sheet for several selected days."""
    days = _selected_days(request)
    user = current_user(request)
    planned = list(
        PlanDay.objects.filter(user=user, date__in=days)
        .select_related("resort")
        .order_by("date")
    )
    first = planned[0] if planned and planned[0].date == days[0] else None
    form = DayForm(request.POST or None, initial=_initial(first))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        set_plans(
            user,
            days,
            data["status"],
            resort=data["resort"],
            note=data["note"],
            is_private=data["is_private"],
        )
        return refresh(request, _my_days_url(_window_from(request)))
    friends, elsewhere = _resort_choices(request, days, first)
    selected = form["resort"].value()
    query = _days_query(days)
    count = f"{len(days)} day{'s' if len(days) > 1 else ''}"
    return render_sheet(
        request,
        "groups/day_sheet.html",
        {
            "day": days[0],
            "days": days,
            "span": len(days),
            "replacing": len(planned),
            "eyebrow": f"My days · {count}",
            "title": _days_title(days),
            "save_label": f"Save {count}",
            "form_url": reverse("planning:several_days") + query,
            "clear_url": reverse("planning:several_days_clear") + query,
            "plan": first or (planned[0] if planned else None),
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
def several_days_clear(request: HttpRequest) -> HttpResponse:
    """Forget what the person said about several selected days."""
    clear_plans(current_user(request), _selected_days(request))
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
