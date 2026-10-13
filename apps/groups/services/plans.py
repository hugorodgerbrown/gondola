"""apps/groups/services/plans.py — Saying which resort you'll be in.

A plan day belongs to a person, not a group, and answers one question:
which resort they'll be in. ``update_plans`` is the one place plans are
written, whether from the calendar or the map. Clearing a day deletes its
row, and an unsaid day is the undecided one.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import PlanDay
from .people import visible_friend_plans

# How far ahead a plan may be made.
PLAN_HORIZON_DAYS = 365


def today() -> datetime.date:
    """Return today's date in Swiss wall-clock time."""
    return timezone.localdate()


def is_plannable(day: datetime.date) -> bool:
    """Return whether a plan can be made for ``day`` (today onwards)."""
    start = today()
    return start <= day <= start + datetime.timedelta(days=PLAN_HORIZON_DAYS)


def last_plannable_day() -> datetime.date:
    """Return the furthest day ahead a plan can be made for."""
    return today() + datetime.timedelta(days=PLAN_HORIZON_DAYS)


def date_range(start: datetime.date, days: int) -> list[datetime.date]:
    """Return ``days`` consecutive dates from ``start``."""
    return [start + datetime.timedelta(days=n) for n in range(days)]


@transaction.atomic
def update_plans(user: User, days: Iterable[datetime.date], resort: Resort) -> list[PlanDay]:
    """Put ``user`` in ``resort`` on each of ``days``."""
    dates = sorted(set(days))
    existing = {plan.date: plan for plan in PlanDay.objects.filter(user=user, date__in=dates)}
    saved = []
    for day in dates:
        plan = existing.get(day) or PlanDay(user=user, date=day)
        plan.resort = resort
        plan.save()
        saved.append(plan)
    return saved


def set_plan(user: User, day: datetime.date, resort: Resort) -> PlanDay:
    """Create or replace ``user``'s plan for ``day``."""
    (plan,) = update_plans(user, [day], resort)
    return plan


def clear_plan(user: User, day: datetime.date) -> None:
    """Forget ``user``'s plan for ``day``, so it reads as unsaid."""
    PlanDay.objects.filter(user=user, date=day).delete()


def clear_plans(user: User, days: Iterable[datetime.date]) -> None:
    """Forget ``user``'s plans on ``days``."""
    PlanDay.objects.filter(user=user, date__in=list(days)).delete()


def upcoming_plans(user: User) -> list[PlanDay]:
    """Return ``user``'s own plans from today on, soonest first."""
    return list(
        PlanDay.objects.filter(user=user, date__gte=today())
        .select_related("resort")
        .order_by("date")
    )


def plan_marks(plans: list[PlanDay]) -> dict[str, str]:
    """Return the calendar's dots: each planned day's ISO date and resort."""
    return {plan.date.isoformat(): plan.resort.name for plan in plans}


@dataclass
class ResortFriends:
    """Friends planned at one resort."""

    resort: Resort
    friends: list[User] = field(default_factory=list)

    @property
    def names(self) -> str:
        """Return the friends' names as one phrase."""
        return join_names([f.to_string() for f in self.friends])


def friends_by_resort(
    viewer: User, days: datetime.date | Iterable[datetime.date]
) -> list[ResortFriends]:
    """Return resorts where ``viewer``'s friends plan to be, busiest first.

    ``days`` is one date or several; over several, a friend at the same
    resort on more than one of them counts once.
    """
    dates = [days] if isinstance(days, datetime.date) else list(days)
    groups: dict[int, ResortFriends] = {}
    for plan in visible_friend_plans(viewer, dates).order_by("date"):
        entry = groups.setdefault(plan.resort.pk, ResortFriends(resort=plan.resort))
        if plan.user not in entry.friends:
            entry.friends.append(plan.user)
    return sorted(groups.values(), key=lambda g: (-len(g.friends), g.resort.name.lower()))


def friend_counts(viewer: User, day: datetime.date) -> dict[int, int]:
    """Return how many friends plan to be at each resort id on ``day``."""
    counts: dict[int, int] = defaultdict(int)
    for plan in visible_friend_plans(viewer, [day]):
        counts[plan.resort_id] += 1
    return dict(counts)


def join_names(names: list[str]) -> str:
    """Return names as English prose: "Anna", "Anna and Ben", "A, B and C"."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
