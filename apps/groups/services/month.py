"""apps/groups/services/month.py — the calendar, one month at a time.

One month at a time, weeks starting Monday. By default the calendar is
about the viewer: each day carries their plan and how many friends will be
with them.

A group picked from the chips adds one more answer: on the days the viewer
hasn't said, where that group's people will be. Such a day carries the
resort most of them are in, and whether others are elsewhere. The
viewer's own days never change, so the group only shows or hides those
pale days.
"""

from __future__ import annotations

import calendar
import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from apps.accounts.models import User

from ..models import Group, PlanDay
from .people import visible_friend_plans
from .plans import ResortFriends, is_plannable, join_names, last_plannable_day, today


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
    # On a day without your plan, with a group picked: the resort most of
    # its people are in (and them), and how many other resorts they're at.
    crowd: ResortFriends | None = None
    more: int = 0

    @property
    def friends_out(self) -> int:
        """Return how many friends are at a resort that day."""
        return len(self.friends)

    @property
    def count(self) -> int:
        """Return the friends the day marks.

        On your days, the friends with you; on the others, those in the crowd.
        """
        if self.plan is not None:
            return self.with_me
        return len(self.crowd.friends) if self.crowd is not None else 0

    @property
    def plan_words(self) -> str:
        """Return your answer for the day panel: "In Verbier"."""
        return f"In {self.plan.resort.name}" if self.plan is not None else ""

    @property
    def summary(self) -> str:
        """Return the day for a screen reader: date, plan, then friends."""
        day = self.date
        parts = [f"{day:%A} {day.day} {day:%B}"]
        if self.is_today:
            parts.append("today")
        plan = self.plan
        parts.append("no plan" if plan is None else plan.describe())
        # A pale day speaks for the picked group alone, as the square shows.
        if self.friends and self.crowd is None:
            parts.append(f"friends at resorts: {join_names(self.friends)}")
        if self.with_me:
            parts.append(f"{self.with_me} with you")
        if self.crowd is not None:
            parts.append(f"most at {self.crowd.resort.name}: {self.crowd.names}")
            if self.more:
                parts.append("others elsewhere")
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


def _crowd(plans: list[PlanDay]) -> tuple[ResortFriends | None, int]:
    """Return the resort most of ``plans``' people are in, and the others' count.

    Ties go to the resort first by name.
    """
    by_resort: dict[int, ResortFriends] = {}
    for plan in plans:
        entry = by_resort.setdefault(plan.resort_id, ResortFriends(plan.resort))
        entry.friends.append(plan.user)
    if not by_resort:
        return None, 0
    crowd = min(
        by_resort.values(),
        key=lambda e: (-len(e.friends), e.resort.name.lower()),
    )
    crowd.friends.sort(key=lambda f: f.to_string().lower())
    return crowd, len(by_resort) - 1


def build_month(viewer: User, first: datetime.date, group: Group | None = None) -> Month:
    """Return ``viewer``'s calendar for the month starting ``first``.

    With ``group``, a day without the viewer's plan shows where that
    group's people will be.
    """
    first = month_start(first)
    weeks_of_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
    dates = [day for week in weeks_of_dates for day in week]
    mine = {
        plan.date: plan
        for plan in PlanDay.objects.filter(user=viewer, date__in=dates).select_related("resort")
    }
    friends: dict[datetime.date, list[str]] = defaultdict(list)
    with_me: dict[datetime.date, int] = defaultdict(int)
    free: dict[datetime.date, list[PlanDay]] = defaultdict(list)
    members = (
        set(group.memberships.values_list("user_id", flat=True)) if group is not None else set()
    )
    for plan in visible_friend_plans(viewer, dates):
        friends[plan.date].append(plan.user.to_string())
        if plan.date not in mine and plan.user_id in members:
            free[plan.date].append(plan)
        own = mine.get(plan.date)
        if own is not None and own.resort_id == plan.resort_id:
            with_me[plan.date] += 1
    crowds = {day: _crowd(free[day]) for day in dates}
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
                crowd=crowds[day][0],
                more=crowds[day][1],
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
