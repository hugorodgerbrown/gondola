"""
apps/groups/services/suggestions.py — Rank resorts for a meet-up.

Resorts are ranked by how many of the group are already planned there,
ties broken by how few people would have to change plan (members with a
different resort that day). "Not sure yet", "not skiing" and unsaid days
never count as a move. Private days count as unsaid.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import Group, PlanDay
from .plans import join_names


@dataclass(frozen=True)
class Suggestion:
    """A resort the group could meet at, and what it would take."""

    resort: Resort
    here: list[User]
    moves: int

    @property
    def names(self) -> str:
        """Return who is already there, as prose."""
        return join_names([u.to_string() for u in self.here])


def suggest_resorts(group: Group, day: datetime.date, viewer: User) -> list[Suggestion]:
    """Return resorts the group's members plan to be at on ``day``, best first."""
    plans = list(
        PlanDay.objects.filter(
            user__group_memberships__group=group,
            date=day,
            status=PlanDay.Status.RESORT,
        )
        .filter(is_private=False)
        .select_related("user", "resort")
    )
    # The viewer's own private day still counts for the viewer.
    own = PlanDay.objects.filter(
        user=viewer, date=day, status=PlanDay.Status.RESORT, is_private=True
    ).select_related("user", "resort")
    plans.extend(own)
    by_resort: dict[int, tuple[Resort, list[User]]] = {}
    for plan in plans:
        if plan.resort is not None:
            entry = by_resort.setdefault(plan.resort.pk, (plan.resort, []))
            entry[1].append(plan.user)
    planned_somewhere = len(plans)
    suggestions = [
        Suggestion(
            resort=resort,
            here=sorted(
                people, key=lambda u: (u.pk != viewer.pk, u.to_string().lower())
            ),
            moves=planned_somewhere - len(people),
        )
        for resort, people in by_resort.values()
    ]
    return sorted(
        suggestions,
        key=lambda s: (-len(s.here), s.moves, s.resort.name.lower()),
    )
