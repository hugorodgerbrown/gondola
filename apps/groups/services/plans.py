"""
apps/groups/services/plans.py — Saying where you're skiing on a day.

A plan day belongs to a person, not a group. ``set_plan`` is the one place
a plan is written, whether from My days, the map or by joining a meet-up.
Saying nothing is different from "Not sure yet" or "Not skiing": clearing
a day deletes its row.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import PlanDay
from .people import visible_friend_plans

# How many days My days lists at once, and how far ahead a plan may be made.
MY_DAYS_SPAN = 14
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


def window_start(day: datetime.date) -> datetime.date:
    """Return where a My days window starting at ``day`` may actually start.

    Never before today, and never so late that the window runs past the
    last plannable day.
    """
    latest = last_plannable_day() - datetime.timedelta(days=MY_DAYS_SPAN - 1)
    return min(max(day, today()), latest)


def date_range(start: datetime.date, days: int) -> list[datetime.date]:
    """Return ``days`` consecutive dates from ``start``."""
    return [start + datetime.timedelta(days=n) for n in range(days)]


@transaction.atomic
def set_plan(
    user: User,
    day: datetime.date,
    status: str,
    *,
    resort: Resort | None = None,
    note: str = "",
    is_private: bool = False,
) -> PlanDay:
    """Create or replace ``user``'s plan for ``day``."""
    if status != PlanDay.Status.RESORT:
        resort = None
    elif resort is None:
        raise ValueError("A day at a resort needs a resort.")
    plan, _ = PlanDay.objects.update_or_create(
        user=user,
        date=day,
        defaults={
            "status": status,
            "resort": resort,
            "note": note.strip(),
            "is_private": is_private,
        },
    )
    return plan


def clear_plan(user: User, day: datetime.date) -> None:
    """Forget ``user``'s plan for ``day``, so it reads as unsaid."""
    PlanDay.objects.filter(user=user, date=day).delete()


def upcoming_plans(user: User) -> list[PlanDay]:
    """Return ``user``'s own plans from today on, soonest first."""
    return list(
        PlanDay.objects.filter(user=user, date__gte=today())
        .select_related("resort")
        .order_by("date")
    )


def plan_marks(plans: list[PlanDay]) -> dict[str, str]:
    """Return the calendar's dots: each planned day's ISO date and status."""
    return {plan.date.isoformat(): plan.status for plan in plans}


@dataclass
class ResortFriends:
    """Friends planned at one resort on one day."""

    resort: Resort
    friends: list[User] = field(default_factory=list)

    @property
    def names(self) -> str:
        """Return the friends' names as one phrase."""
        return join_names([f.to_string() for f in self.friends])


def friends_by_resort(viewer: User, day: datetime.date) -> list[ResortFriends]:
    """Return resorts where ``viewer``'s friends plan to be, busiest first."""
    groups: dict[int, ResortFriends] = {}
    for plan in visible_friend_plans(viewer, [day]).filter(
        status=PlanDay.Status.RESORT
    ):
        if plan.resort is None:  # pragma: no cover — the status constraint forbids it
            continue
        entry = groups.setdefault(plan.resort.pk, ResortFriends(resort=plan.resort))
        entry.friends.append(plan.user)
    return sorted(
        groups.values(), key=lambda g: (-len(g.friends), g.resort.name.lower())
    )


def friend_counts(viewer: User, day: datetime.date) -> dict[int, int]:
    """Return how many friends plan to be at each resort id on ``day``."""
    counts: dict[int, int] = defaultdict(int)
    for plan in visible_friend_plans(viewer, [day]).filter(
        status=PlanDay.Status.RESORT
    ):
        if plan.resort_id is not None:
            counts[plan.resort_id] += 1
    return dict(counts)


def join_names(names: list[str]) -> str:
    """Return names as English prose: "Anna", "Anna and Ben", "A, B and C"."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
