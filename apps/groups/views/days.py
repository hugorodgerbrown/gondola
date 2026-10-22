"""apps/groups/views/days.py — the calendar, and the sheet for one day.

The calendar is about you: a month, this month by default; arrows step a
month (``?from=``, any day in it) as far as plans can be made. A day shows
which resort you'll be in and whether friends will be there too. Chips
above it pick one of your groups (``?group=``): the days you haven't said
then show, pale, where that group's people will be. Your own days never
change.

Tapping a day selects it (``?day=``) and fills the panel below the month:
where you are, the friends with you (in the picked group, if one is),
where the others are, and Add plans or Edit plans, which opens a sheet with one
answer: where you'll be (the resorts friends picked first, then a search
over every resort).

Pressing and holding a day starts selecting: tap more days (or drag
across a run), then one sheet puts them all in one resort (``?days=``).

``plans_write`` is the same save and clear as JSON, for the offline
outbox (static/js/plans.js): the sheets' forms go there when JavaScript
runs, and post as plain forms when it doesn't.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.core.analytics import record
from apps.core.decorators import login_required_json
from apps.core.http import refresh, render_sheet
from apps.core.shortcuts import render
from apps.resorts.models import Resort
from apps.resorts.search import search_resorts

from ..forms import DayForm
from ..models import Group, PlanDay
from ..services.month import (
    Month,
    MonthDay,
    build_month,
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
    groups = list(Group.objects.for_user(user).order_by("name"))
    group = _group(request, groups)
    picked = _picked_day(request)
    month = build_month(user, picked or parse_day(request.GET.get("from")), group)
    window_from = _later_month(month.first)
    back = _back(window_from, group)
    selected = _selected(month, picked)
    here_resort = selected.plan.resort if selected.plan else None
    here, elsewhere = _split_friends(
        _in_group(friends_by_resort(user, selected.date), group), here_resort
    )
    return render(
        request,
        "groups/calendar.html",
        {
            "month": month,
            "today": today(),
            "selected": selected,
            # Your resort that day, the friends with you, and the rest.
            "here_resort": here_resort,
            "here": here,
            "elsewhere": elsewhere,
            # Only a later month needs carrying through a plain form post.
            "window_from": window_from,
            "back_query": urlencode(back),
            "groups": groups,
            "max_selected": MAX_SELECTED_DAYS,
            "group": group,
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


def _in_group(entries: list[ResortFriends], group: Group | None) -> list[ResortFriends]:
    """Return ``entries`` cut to ``group``'s people, if a group is picked."""
    if group is None:
        return entries
    members = set(group.memberships.values_list("user_id", flat=True))
    kept = []
    for entry in entries:
        friends = [f for f in entry.friends if f.pk in members]
        if friends:
            kept.append(ResortFriends(entry.resort, friends))
    return kept


def _later_month(first: datetime.date) -> datetime.date | None:
    """Return ``first`` if it is a month after this one, else ``None``."""
    return first if first > today().replace(day=1) else None


def _group(request: HttpRequest, groups: list[Group]) -> Group | None:
    """Return the group the calendar shows (``group=<uuid>``), if one of ``groups``."""
    value = request.POST.get("group") or request.GET.get("group")
    return next((g for g in groups if str(g.uuid) == value), None)


def _window_from(request: HttpRequest) -> datetime.date | None:
    """Return the calendar month a sheet was opened from, if not this month."""
    value = request.POST.get("from") or request.GET.get("from")
    return _later_month(month_start(parse_day(value))) if value else None


def _back(window_from: datetime.date | None, group: Group | None) -> dict[str, str]:
    """Return what takes the calendar back to how it was: the month and group."""
    back = {}
    if window_from is not None:
        back["from"] = window_from.isoformat()
    if group is not None:
        back["group"] = str(group.uuid)
    return back


def _request_back(request: HttpRequest) -> dict[str, str]:
    """Return the calendar state a sheet was opened from."""
    user = current_user(request)
    groups = list(Group.objects.for_user(user))
    return _back(_window_from(request), _group(request, groups))


def _calendar_url(back: dict[str, str], days: list[datetime.date] | None = None) -> str:
    """Return the calendar, as the person was looking at it.

    After one day's sheet, ``days`` keeps that day selected in the panel.
    """
    if days is not None and len(days) == 1:
        back = {**back, "day": days[0].isoformat()}
    url = reverse("planning:calendar")
    return f"{url}?{urlencode(back)}" if back else url


def _initial(
    days: list[datetime.date], plans: dict[datetime.date, PlanDay]
) -> tuple[dict[str, object], bool]:
    """Return the sheet's starting resort, and whether the days differ.

    Days that all say the same resort start with it picked; days that say
    different things (or some nothing) start with none picked.
    """
    said = {str(plans[day].resort.uuid) if day in plans else "" for day in days}
    if len(said) == 1:
        return {"resort": said.pop()}, False
    return {}, True


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
        for plan in PlanDay.objects.filter(user=user, date__in=days).select_related("resort")
    }
    initial, mixed = _initial(days, plans)
    # Bound on any POST, even an empty one, so a missing resort is an error.
    form = DayForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        record_day_planned(request, user)
        update_plans(user, days, form.cleaned_data["resort"])
        return refresh(request, _calendar_url(_request_back(request), days))
    friends = friends_by_resort(user, days)
    listed = {entry.resort.pk for entry in friends}
    picks = {plan.resort for plan in plans.values()}
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
            "elsewhere": sorted((r for r in picks if r.pk not in listed), key=lambda r: r.name),
            "selected": selected,
            "groups_count": Group.objects.for_user(user).count(),
            "back": _request_back(request),
            # For the outbox (static/js/plans.js): the days, and where to go
            # once the write is queued when the sheet is a page of its own.
            "days_csv": ",".join(day.isoformat() for day in days),
            "done_url": _calendar_url(_request_back(request), days),
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


def _bad_write(reason: str) -> JsonResponse:
    """Refuse a plan write the outbox can't fix by sending it again."""
    return JsonResponse({"error": reason}, status=400)


def _written_at(value: Any) -> datetime.datetime:
    """Return when the person made a queued write: its ``written_at``, else now.

    A time in the future (a phone's clock running fast) counts as now.
    """
    now = timezone.now()
    try:
        written = datetime.datetime.fromisoformat(str(value))
    except ValueError:
        return now
    if written.tzinfo is None:
        return now
    return min(written, now)


@require_POST
@login_required_json
def plans_write(request: HttpRequest) -> JsonResponse:
    """Put the person in a resort on some days, or clear them: JSON for the outbox.

    The body is ``{"days": ["2026-12-14", ...], "resort": "<uuid>" or null,
    "written_at": "<ISO time>"}``; a null resort clears the days. A queued
    write can arrive long after it was made, so a day that has since gone
    by, or that was said after ``written_at`` (from another device, or a
    later write), is skipped rather than overwritten. The check is on
    ``said_at``, which a queued write sets to its own ``written_at``, so
    several writes queued for one day still land in the order they were
    made. The answer lists
    what was saved and what was skipped.
    """
    try:
        data = json.loads(request.body)
        raw_days = data["days"]
        days = sorted({datetime.date.fromisoformat(str(day)) for day in raw_days})
    except ValueError, TypeError, KeyError:
        return _bad_write("days")
    if not days or len(days) > MAX_SELECTED_DAYS:
        return _bad_write("days")
    resort = None
    if data.get("resort") is not None:
        try:
            resort = Resort.objects.get(uuid=uuid.UUID(str(data["resort"])))
        except ValueError, Resort.DoesNotExist:
            return _bad_write("resort")
    user = current_user(request)
    written_at = _written_at(data.get("written_at"))
    changed_since = set(
        PlanDay.objects.filter(user=user, date__in=days, said_at__gt=written_at).values_list(
            "date", flat=True
        )
    )
    wanted = [day for day in days if is_plannable(day) and day not in changed_since]
    if wanted and resort is not None:
        record_day_planned(request, user)
        update_plans(user, wanted, resort, said_at=written_at)
    elif wanted:
        clear_plans(user, wanted)
    skipped = [day for day in days if day not in wanted]
    return JsonResponse(
        {
            "saved": [day.isoformat() for day in wanted],
            "skipped": [day.isoformat() for day in skipped],
        }
    )
