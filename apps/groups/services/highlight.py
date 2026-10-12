"""
apps/groups/services/highlight.py — One resort picked out on the calendar.

Answers "when are friends in Verbier in January" from the calendar: the
chips list the resorts friends are in during the month. The month itself
(``build_month``) then shows, on the days you haven't said, only the
friends at the chosen one.
"""

from __future__ import annotations

import datetime
from collections import Counter

from apps.accounts.models import User
from apps.resorts.models import Resort

from .people import visible_friend_plans


def resorts_in_play(viewer: User, dates: list[datetime.date]) -> list[Resort]:
    """Return the resorts friends are at on ``dates``, most friend-days first."""
    plans = visible_friend_plans(viewer, dates)
    counts = Counter(plan.resort_id for plan in plans)
    resorts = {plan.resort_id: plan.resort for plan in plans}
    return sorted(
        resorts.values(),
        key=lambda r: (-counts[r.pk], r.name.lower()),
    )
