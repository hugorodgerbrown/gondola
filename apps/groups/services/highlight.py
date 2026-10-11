"""
apps/groups/services/highlight.py — One resort picked out on My days.

Answers "who's in Verbier in January" from the calendar: the chips list
the resorts anyone (you, or a friend on a day they haven't kept private)
is at in the month, whether or not they're skiing. The month itself
(``build_month``) then picks out the days someone is at the chosen one.
"""

from __future__ import annotations

import datetime
from collections import Counter

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import PlanDay
from .people import visible_friend_plans


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
