"""
apps/groups/services/highlight.py — One resort picked out on My days.

Answers "who's in Verbier in January": the resorts anyone (you, or a
friend on a day they haven't kept private) is at in the month, to choose
from; and for the chosen one, each person there and their days, as runs.
Being at a resort counts whether or not you're skiing; a run of days
there without skiing on any of them is marked "around", as everywhere
else.
"""

from __future__ import annotations

import datetime
from collections import Counter
from dataclasses import dataclass

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import PlanDay
from .people import visible_friend_plans


@dataclass(frozen=True)
class Stay:
    """Consecutive days one person is at the resort, and if they ski any."""

    first: datetime.date
    last: datetime.date
    skiing: bool

    @property
    def days(self) -> int:
        """Return how many days the stay is."""
        return (self.last - self.first).days + 1

    def to_string(self) -> str:
        """Return the stay in words: "5 Jan", "14–23 Jan", "30 Jan – 2 Feb (around)"."""
        first, last = self.first, self.last
        if first == last:
            text = f"{first.day} {first:%b}"
        elif first.month == last.month:
            text = f"{first.day}–{last.day} {last:%b}"
        else:
            text = f"{first.day} {first:%b} – {last.day} {last:%b}"
        return text if self.skiing else f"{text} (around)"

    def __str__(self) -> str:
        """Return :meth:`to_string`."""
        return self.to_string()


@dataclass(frozen=True)
class Visitor:
    """One person at the resort in the month, and when."""

    person: User
    is_me: bool
    stays: list[Stay]

    @property
    def days(self) -> int:
        """Return how many days in all."""
        return sum(stay.days for stay in self.stays)


def _resort_plans(viewer: User, dates: list[datetime.date]) -> list[PlanDay]:
    """Return the viewer's and friends' visible plans at a resort on ``dates``."""
    mine = PlanDay.objects.filter(user=viewer, date__in=dates).at_resorts()
    return [
        *mine.select_related("user", "resort"),
        *visible_friend_plans(viewer, dates).at_resorts(),
    ]


def resorts_in_play(viewer: User, dates: list[datetime.date]) -> list[Resort]:
    """Return the resorts anyone is at on ``dates``, most person-days first."""
    plans = _resort_plans(viewer, dates)
    counts = Counter(plan.resort_id for plan in plans)
    resorts = {plan.resort_id: plan.resort for plan in plans}
    return sorted(
        (r for r in resorts.values() if r is not None),
        key=lambda r: (-counts[r.pk], r.name.lower()),
    )


def _stays(plans: list[PlanDay]) -> list[Stay]:
    """Join one person's dated plans at the resort into runs of days."""
    stays: list[Stay] = []
    for plan in sorted(plans, key=lambda p: p.date):
        last = stays[-1] if stays else None
        if last is not None and plan.date - last.last == datetime.timedelta(days=1):
            stays[-1] = Stay(last.first, plan.date, last.skiing or plan.is_skiing)
        else:
            stays.append(Stay(plan.date, plan.date, plan.is_skiing))
    return stays


def visitors(viewer: User, resort: Resort, dates: list[datetime.date]) -> list[Visitor]:
    """Return who is at ``resort`` on ``dates``: you first, then most days."""
    by_person: dict[int, list[PlanDay]] = {}
    people: dict[int, User] = {}
    for plan in _resort_plans(viewer, dates):
        if plan.resort_id == resort.pk:
            by_person.setdefault(plan.user_id, []).append(plan)
            people[plan.user_id] = plan.user
    found = [
        Visitor(person=people[pk], is_me=pk == viewer.pk, stays=_stays(plans))
        for pk, plans in by_person.items()
    ]
    return sorted(
        found,
        key=lambda v: (not v.is_me, -v.days, v.person.to_string().lower()),
    )
