"""
apps/groups/services/plans.py — Saying where you'll be, and if you're skiing.

A plan day belongs to a person, not a group, and answers two separate
questions: where they'll be (a resort, or none) and whether they're
skiing (yes, not sure, no). Someone at a resort who isn't skiing is still
"around" for friends. ``update_plans`` is the one place plans are written,
whether from the calendar or the map: over several days it changes only
the answers given and keeps the rest, so ten days in Verbier stay in
Verbier when three of them are then marked as skiing. Saying
nothing is different from "Not sure yet" or "Not skiing": clearing a day
deletes its row.
"""

from __future__ import annotations

import datetime
import enum
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


class Keep(enum.Enum):
    """Leave this answer as each day already has it."""

    KEEP = "keep"


KEEP = Keep.KEEP


@transaction.atomic
def update_plans(
    user: User,
    days: Iterable[datetime.date],
    *,
    skiing: str | Keep = KEEP,
    resort: Resort | None | Keep = KEEP,
    note: str | Keep = KEEP,
    is_private: bool | Keep = KEEP,
) -> list[PlanDay]:
    """Set the answers given on each of ``days``, keeping the ones left out.

    A day with no plan yet starts from skiing, at no resort, shared.
    """
    dates = sorted(set(days))
    existing = {
        plan.date: plan for plan in PlanDay.objects.filter(user=user, date__in=dates)
    }
    saved = []
    for day in dates:
        plan = existing.get(day) or PlanDay(user=user, date=day)
        if not isinstance(skiing, Keep):
            plan.skiing = skiing
        if not isinstance(resort, Keep):
            plan.resort = resort
        if not isinstance(note, Keep):
            plan.note = note.strip()
        if not isinstance(is_private, Keep):
            plan.is_private = is_private
        plan.save()
        saved.append(plan)
    return saved


def set_plan(
    user: User,
    day: datetime.date,
    skiing: str,
    *,
    resort: Resort | None = None,
    note: str = "",
    is_private: bool = False,
) -> PlanDay:
    """Create or replace ``user``'s whole plan for ``day``."""
    (plan,) = update_plans(
        user, [day], skiing=skiing, resort=resort, note=note, is_private=is_private
    )
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
    """Return the calendar's dots: each planned day's ISO date and skiing."""
    return {plan.date.isoformat(): plan.skiing for plan in plans}


@dataclass
class ResortFriends:
    """Friends planned at one resort, and which of them aren't skiing."""

    resort: Resort
    friends: list[User] = field(default_factory=list)
    skiers: set[int] = field(default_factory=set)

    @property
    def names(self) -> str:
        """Return the friends' names as one phrase, marking who's just around."""
        return join_names(
            [
                f.to_string() + ("" if f.pk in self.skiers else " (around)")
                for f in self.friends
            ]
        )


def friends_by_resort(
    viewer: User, days: datetime.date | Iterable[datetime.date]
) -> list[ResortFriends]:
    """Return resorts where ``viewer``'s friends plan to be, busiest first.

    ``days`` is one date or several; over several, a friend at the same
    resort on more than one of them counts once, and counts as skiing if
    they ski any of them. Friends there but not skiing count too.
    """
    dates = [days] if isinstance(days, datetime.date) else list(days)
    groups: dict[int, ResortFriends] = {}
    for plan in visible_friend_plans(viewer, dates).at_resorts().order_by("date"):
        if plan.resort is None:  # pragma: no cover — at_resorts() rules it out
            continue
        entry = groups.setdefault(plan.resort.pk, ResortFriends(resort=plan.resort))
        if plan.user not in entry.friends:
            entry.friends.append(plan.user)
        if plan.is_skiing:
            entry.skiers.add(plan.user.pk)
    return sorted(
        groups.values(), key=lambda g: (-len(g.friends), g.resort.name.lower())
    )


def friend_counts(viewer: User, day: datetime.date) -> dict[int, int]:
    """Return how many friends plan to be at each resort id on ``day``."""
    counts: dict[int, int] = defaultdict(int)
    for plan in visible_friend_plans(viewer, [day]).at_resorts():
        if plan.resort_id is not None:
            counts[plan.resort_id] += 1
    return dict(counts)


def join_names(names: list[str]) -> str:
    """Return names as English prose: "Anna", "Anna and Ben", "A, B and C"."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
