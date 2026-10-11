"""
apps/groups/services/month.py — My days as a month calendar.

One month at a time, weeks starting Monday. Each day carries what the
viewer said about it and what their groups are up to: how many friends
are at a resort (skiing or just around), how many of them at the viewer's
resort, and whether one of the viewer's groups has a meet-up. Friends'
private days count for nothing, as everywhere else.

With one resort highlighted, each day also says which friends are there,
and whether the viewer is, so the calendar can pick those days out.
"""

from __future__ import annotations

import calendar
import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import Group, MeetUp, PlanDay
from .people import visible_friend_plans
from .plans import is_plannable, join_names, last_plannable_day, today


@dataclass
class MonthDay:
    """One square of the month: the viewer's plan and their groups' activity."""

    date: datetime.date
    in_month: bool
    is_today: bool
    plannable: bool
    plan: PlanDay | None = None
    friends: list[str] = field(default_factory=list)
    with_me: int = 0
    meetup: MeetUp | None = None
    # The highlighted resort's name, if one is; the friends there that day;
    # and whether you are.
    highlight: str = ""
    there: list[str] = field(default_factory=list)
    me_there: bool = False

    @property
    def lit(self) -> bool:
        """Return whether anyone is at the highlighted resort that day."""
        return self.me_there or bool(self.there)

    @property
    def friends_out(self) -> int:
        """Return how many friends are at a resort that day."""
        return len(self.friends)

    @property
    def summary(self) -> str:
        """Return the day for a screen reader: date, plan, then friends."""
        day = self.date
        parts = [f"{day:%A} {day.day} {day:%B}"]
        if self.is_today:
            parts.append("today")
        plan = self.plan
        parts.append("no plan" if plan is None else plan.describe())
        if plan is not None and plan.is_private:
            parts.append("private")
        if self.friends:
            parts.append(f"friends at resorts: {join_names(self.friends)}")
        if self.with_me:
            parts.append(f"{self.with_me} with you")
        if self.meetup is not None:
            parts.append(f"meet-up at {self.meetup.resort.name}")
        if self.there:
            parts.append(f"at {self.highlight}: {join_names(self.there)}")
        return ", ".join(parts)


@dataclass
class Month:
    """A month of days, in Monday-first weeks, and the months either side."""

    first: datetime.date
    weeks: list[list[MonthDay]]
    previous: datetime.date | None
    next: datetime.date | None


def month_start(day: datetime.date) -> datetime.date:
    """Return the first of ``day``'s month, kept within the plannable months."""
    earliest = today().replace(day=1)
    latest = last_plannable_day().replace(day=1)
    return min(max(day.replace(day=1), earliest), latest)


def _shift(first: datetime.date, months: int) -> datetime.date:
    """Return the first of the month ``months`` after ``first``."""
    index = first.year * 12 + first.month - 1 + months
    return datetime.date(index // 12, index % 12 + 1, 1)


def month_dates(first: datetime.date) -> list[datetime.date]:
    """Return the dates of ``first``'s month (``first`` is a month start)."""
    return [
        first + datetime.timedelta(days=n)
        for n in range(calendar.monthrange(first.year, first.month)[1])
    ]


def build_month(
    viewer: User, first: datetime.date, highlight: Resort | None = None
) -> Month:
    """Return ``viewer``'s calendar for the month starting ``first``.

    ``highlight`` is a resort to pick out: each day then names the friends
    there and says whether the viewer is.
    """
    first = month_start(first)
    weeks_of_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(
        first.year, first.month
    )
    dates = [day for week in weeks_of_dates for day in week]
    mine = {
        plan.date: plan
        for plan in PlanDay.objects.filter(user=viewer, date__in=dates).select_related(
            "resort"
        )
    }
    friends: dict[datetime.date, list[str]] = defaultdict(list)
    with_me: dict[datetime.date, int] = defaultdict(int)
    there: dict[datetime.date, list[str]] = defaultdict(list)
    for plan in visible_friend_plans(viewer, dates).at_resorts():
        friends[plan.date].append(plan.user.to_string())
        if highlight is not None and plan.resort_id == highlight.pk:
            there[plan.date].append(plan.user.to_string())
        own = mine.get(plan.date)
        if own is not None and own.resort_id == plan.resort_id:
            with_me[plan.date] += 1
    meetups: dict[datetime.date, MeetUp] = {}
    for meetup in (
        MeetUp.objects.filter(group__in=Group.objects.for_user(viewer), date__in=dates)
        .select_related("resort")
        .order_by("created_at")
    ):
        meetups.setdefault(meetup.date, meetup)
    now = today()
    weeks = [
        [
            MonthDay(
                date=day,
                in_month=day.month == first.month,
                is_today=day == now,
                plannable=is_plannable(day),
                plan=mine.get(day),
                friends=sorted(friends[day], key=str.lower),
                with_me=with_me[day],
                meetup=meetups.get(day),
                highlight=highlight.name if highlight is not None else "",
                there=sorted(there[day], key=str.lower),
                me_there=highlight is not None
                and day in mine
                and mine[day].resort_id == highlight.pk,
            )
            for day in week
        ]
        for week in weeks_of_dates
    ]
    previous = _shift(first, -1)
    following = _shift(first, 1)
    return Month(
        first=first,
        weeks=weeks,
        previous=previous if previous >= month_start(now) else None,
        next=following if following <= month_start(last_plannable_day()) else None,
    )
