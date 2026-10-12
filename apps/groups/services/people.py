"""
apps/groups/services/people.py — Who can see whom.

Group members see each other's names and days: joining is the consent.
So a person's "friends" are everyone they share at least one group with,
and a friend's day is visible unless they marked it private.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterable

from apps.accounts.models import User

from ..models import Group, Membership, PlanDay, PlanDayQuerySet


def friend_ids(user: User) -> set[int]:
    """Return the ids of everyone who shares a group with ``user``.

    Only the groups ``user`` sees count: their real ones, or the demo copy
    while they tour (``GroupQuerySet.for_user``).
    """
    groups = Group.objects.for_user(user).values("pk")
    return set(
        Membership.objects.filter(group_id__in=groups)
        .exclude(user=user)
        .values_list("user_id", flat=True)
    )


def visible_friend_plans(
    viewer: User, dates: Iterable[datetime.date]
) -> PlanDayQuerySet:
    """Return friends' non-private plans on ``dates``, with user and resort."""
    return (
        PlanDay.objects.shared()
        .filter(user_id__in=friend_ids(viewer), date__in=list(dates))
        .select_related("user", "resort")
    )


def members_of(group: Group) -> list[User]:
    """Return a group's members, owner first, then by name."""
    memberships = group.memberships.select_related("user")
    people = [m.user for m in memberships]
    owner_first = sorted(
        people, key=lambda u: (u.pk != group.owner_id, u.to_string().lower())
    )
    return owner_first


def is_member(group: Group, user: User) -> bool:
    """Return whether ``user`` belongs to ``group``."""
    return group.memberships.filter(user=user).exists()
