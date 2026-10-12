"""
apps/groups/views/days.py — the calendar, and the sheet for one day.

The calendar is about you: a month, this month by default; arrows step a
month (``?from=``, any day in it) as far as plans can be made. A day shows
whether you're skiing, how many friends will be where you are, a lock if
you keep it private and a dot for a meet-up. Chips above it highlight one
resort (``?highlight=``): the days anyone is there stand out, and the
count is the friends there instead.

Tapping a day selects it (``?day=``) and fills the panel below the month:
where you are, the friends with you (the day's number, so the highlighted
resort's while one is picked), where the others are, any meet-up, and Add
plans or Edit plans, which opens a sheet with two separate answers: where you'll
be (the resorts friends picked first, then a search over every resort, or
no resort) and whether you're skiing (yes, not sure yet, no); then an
optional note, and a switch to keep the day private.

Pressing and holding a day starts selecting: tap more days (or drag
across a run), then one sheet plans them all (``?days=``). An answer that
differs across the days is left out of the sheet and kept unless changed,
so a sheet only ever saves what was touched.
"""

from __future__ import annotations

import datetime
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.core.analytics import record
from apps.core.http import refresh, render_sheet
from apps.resorts.models import Resort
from apps.resorts.search import search_resorts

from ..forms import KEEP_RESORT, DayForm
from ..models import Group, PlanDay
from ..services.highlight import resorts_in_play
from ..services.meetups import meetups_for
from ..services.month import (
    Month,
    MonthDay,
    build_month,
    month_dates,
    month_start,
)
from ..services.plans import (
    ResortFriends,
    clear_plan,
    clear_plans,
    friends_by_resort,
    is_plannable,
    join_names,
    today,
    update_plans,
)
from .helpers import current_user, parse_day


def record_day_planned(request: HttpRequest, user: User) -> None:
    """Count a day planned in fivebar: the first ever, and whether after the tour."""
    record(
        request,
        "Day planned",
        first=not PlanDay.objects.filter(user=user).exists(),
        after_tour=user.toured_at is not None,
    )


# The most days one selection can plan.
MAX_SELECTED_DAYS = 62


@login_required
@require_GET
def calendar(request: HttpRequest) -> HttpResponse:
    """Show a month of days: the person's plans and their groups' activity."""
    user = current_user(request)
    highlight = _highlight(request)
    picked = _picked_day(request)
    month = build_month(user, picked or parse_day(request.GET.get("from")), highlight)
    resorts = resorts_in_play(user, month_dates(month.first))
    if highlight is not None and highlight not in resorts:
        resorts.insert(0, highlight)
    window_from = _later_month(month.first)
    back = _back(window_from, highlight)
    selected = _selected(month, picked)
    here_resort = highlight or (selected.plan.resort if selected.plan else None)
    here, elsewhere = _split_friends(
        friends_by_resort(user, selected.date), here_resort
    )
    return render(
        request,
        "groups/calendar.html",
        {
            "month": month,
            "today": today(),
            "selected": selected,
            # The resort the day's number counts, its friends, and the rest.
            "here_resort": here_resort,
            "here": here,
            "elsewhere": elsewhere,
            # Only a later month needs carrying through a plain form post.
            "window_from": window_from,
            "back_query": urlencode(back),
            "groups": list(Group.objects.for_user(user).order_by("name")),
            "max_selected": MAX_SELECTED_DAYS,
            "resorts": resorts,
            "highlight": highlight,
        },
    )


def _picked_day(request: HttpRequest) -> datetime.date | None:
    """Return the day tapped on the calendar (``day=``), if any and valid."""
    value = request.GET.get("day")
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _selected(month: Month, picked: datetime.date | None) -> MonthDay:
    """Return the month's selected day: the one tapped, else today, else the 1st."""
    days = [day for week in month.weeks for day in week if day.in_month]
    for wanted in (picked, today()):
        for day in days:
            if day.date == wanted:
                return day
    return days[0]


def _split_friends(
    entries: list[ResortFriends], resort: Resort | None
) -> tuple[ResortFriends | None, list[ResortFriends]]:
    """Return the friends at ``resort``, if any, and those everywhere else."""
    here = None
    elsewhere = []
    for entry in entries:
        if resort is not None and entry.resort.pk == resort.pk:
            here = entry
        else:
            elsewhere.append(entry)
    return here, elsewhere


def _later_month(first: datetime.date) -> datetime.date | None:
    """Return ``first`` if it is a month after this one, else ``None``."""
    return first if first > today().replace(day=1) else None


def _highlight(request: HttpRequest) -> Resort | None:
    """Return the resort the calendar highlights (``highlight=<uuid>``), if any."""
    # Not "resort": that's the day sheet's own answer to where you'll be.
    value = request.POST.get("highlight") or request.GET.get("highlight")
    if not value:
        return None
    try:
        return Resort.objects.filter(uuid=value).first()
    except ValidationError:
        return None


def _window_from(request: HttpRequest) -> datetime.date | None:
    """Return the calendar month a sheet was opened from, if not this month."""
    value = request.POST.get("from") or request.GET.get("from")
    return _later_month(month_start(parse_day(value))) if value else None


def _back(
    window_from: datetime.date | None, highlight: Resort | None
) -> dict[str, str]:
    """Return what takes the calendar back to how it was: the month and resort."""
    back = {}
    if window_from is not None:
        back["from"] = window_from.isoformat()
    if highlight is not None:
        back["highlight"] = str(highlight.uuid)
    return back


def _request_back(request: HttpRequest) -> dict[str, str]:
    """Return the calendar state a sheet was opened from."""
    return _back(_window_from(request), _highlight(request))


def _calendar_url(back: dict[str, str], days: list[datetime.date] | None = None) -> str:
    """Return the calendar, as the person was looking at it.

    After one day's sheet, ``days`` keeps that day selected in the panel.
    """
    if days is not None and len(days) == 1:
        back = {**back, "day": days[0].isoformat()}
    url = reverse("planning:calendar")
    return f"{url}?{urlencode(back)}" if back else url


# What a day with no plan yet starts from in the sheet.
FRESH = {"skiing": PlanDay.Skiing.YES, "resort": "", "note": "", "is_private": False}


def _answers(plan: PlanDay | None) -> dict[str, object]:
    """Return one day's answers as the sheet's form values."""
    if plan is None:
        return dict(FRESH)
    return {
        "skiing": plan.skiing,
        "resort": str(plan.resort.uuid) if plan.resort else "",
        "note": plan.note,
        "is_private": plan.is_private,
    }


def _initial(
    days: list[datetime.date], plans: dict[datetime.date, PlanDay]
) -> tuple[dict[str, object], set[str]]:
    """Return the sheet's starting values, and which answers differ by day.

    An answer the days share is filled in; one that differs is left out
    and named in the second value, so saving keeps it unless it's changed.
    """
    per_day = [_answers(plans.get(day)) for day in days]
    initial: dict[str, object] = {}
    mixed = set()
    for name in FRESH:
        values = {str(answers[name]) for answers in per_day}
        if len(values) == 1:
            initial[name] = per_day[0][name]
        else:
            mixed.add(name)
    if "resort" in mixed:
        initial["resort"] = KEEP_RESORT
    return initial, mixed


def _sheet(
    request: HttpRequest,
    days: list[datetime.date],
    *,
    form_url: str,
    clear_url: str,
    title: str,
    eyebrow: str,
    save_label: str,
) -> HttpResponse:
    """Show and save the sheet for one day or several."""
    user = current_user(request)
    plans = {
        plan.date: plan
        for plan in PlanDay.objects.filter(user=user, date__in=days).select_related(
            "resort"
        )
    }
    initial, mixed = _initial(days, plans)
    form = DayForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        record_day_planned(request, user)
        update_plans(user, days, **form.changes())
        return refresh(request, _calendar_url(_request_back(request), days))
    friends = friends_by_resort(user, days)
    listed = {entry.resort.pk for entry in friends}
    picks = {plan.resort for plan in plans.values() if plan.resort is not None}
    selected = str(form["resort"].value() or "")
    return render_sheet(
        request,
        "groups/day_sheet.html",
        {
            "day": days[0],
            "span": len(days),
            "eyebrow": eyebrow,
            "title": title,
            "save_label": save_label,
            "form_url": form_url,
            "clear_url": clear_url,
            "has_plans": bool(plans),
            "mixed": mixed,
            "form": form,
            "friends": friends,
            # The days' own resorts that no friend has picked, to keep them
            # one tap away.
            "elsewhere": sorted(
                (r for r in picks if r.pk not in listed), key=lambda r: r.name
            ),
            "selected": selected,
            "keep_resort": KEEP_RESORT,
            "groups_count": Group.objects.for_user(user).count(),
            # One day's sheet lists that day's meet-ups in your groups.
            "meetups": meetups_for(user, days[0]) if len(days) == 1 else [],
            "back": _request_back(request),
        },
    )


@login_required
def day(request: HttpRequest, day: datetime.date) -> HttpResponse:
    """Show and save the sheet for one day."""
    if not is_plannable(day):
        raise Http404("That day can't be planned.")
    return _sheet(
        request,
        [day],
        form_url=reverse("planning:day", kwargs={"day": day}),
        clear_url=reverse("planning:day_clear", kwargs={"day": day}),
        title=f"{day:%A} {day.day} {day:%B}",
        eyebrow="Calendar",
        save_label=f"Save {day:%a} {day.day} {day:%b}",
    )


@login_required
@require_POST
def day_clear(request: HttpRequest, day: datetime.date) -> HttpResponse:
    """Forget what the person said about a day."""
    clear_plan(current_user(request), day)
    return refresh(request, _calendar_url(_request_back(request), [day]))


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
    query = _days_query(days)
    count = f"{len(days)} day{'s' if len(days) > 1 else ''}"
    return _sheet(
        request,
        days,
        form_url=reverse("planning:several_days") + query,
        clear_url=reverse("planning:several_days_clear") + query,
        title=_days_title(days),
        eyebrow=f"Calendar · {count}",
        save_label=f"Save {count}",
    )


@login_required
@require_POST
def several_days_clear(request: HttpRequest) -> HttpResponse:
    """Forget what the person said about several selected days."""
    clear_plans(current_user(request), _selected_days(request))
    return refresh(request, _calendar_url(_request_back(request)))


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
