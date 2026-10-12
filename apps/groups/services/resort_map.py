"""
apps/groups/services/resort_map.py — What the map shows for a day.

Every placed resort is a pin; a pass filter narrows them to that pass's
resorts, but a resort with a friend, a meet-up or your own plan that day
always stays on the map. A pin counts every friend there, skiing or just
around. ``resort_day`` is what the resort sheet shows: who from each of
your groups is there (and who isn't skiing), and any meet-up.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import Group, MeetUp, PlanDay
from .meetups import MeetUpCard, meetups_for
from .people import visible_friend_plans
from .plans import friend_counts


def _meetup_resort_ids(viewer: User, day: datetime.date) -> set[int]:
    """Return resort ids with a meet-up that day in the viewer's groups."""
    groups = Group.objects.for_user(viewer)
    return set(
        MeetUp.objects.filter(group__in=groups, date=day).values_list(
            "resort_id", flat=True
        )
    )


def map_pins(
    viewer: User, day: datetime.date, pass_slug: str = ""
) -> list[dict[str, object]]:
    """Return one pin per placed resort, as plain data for the map script."""
    counts = friend_counts(viewer, day)
    meetups = _meetup_resort_ids(viewer, day)
    mine = (
        PlanDay.objects.filter(user=viewer, date=day)
        .at_resorts()
        .values_list("resort_id", flat=True)
    )
    mine_ids = set(mine)
    keep = set(counts) | meetups | mine_ids
    resorts = Resort.objects.placed().prefetch_related("passes")
    on_pass: set[int] | None = None
    if pass_slug:
        on_pass = set(resorts.on_pass(pass_slug).values_list("id", flat=True))
    pins: list[dict[str, object]] = []
    for resort in resorts:
        if on_pass is not None and resort.pk not in on_pass and resort.pk not in keep:
            continue
        pins.append(
            {
                "id": str(resort.uuid),
                "name": resort.name,
                "code": resort.display_code,
                "lng": resort.longitude,
                "lat": resort.latitude,
                "friends": counts.get(resort.pk, 0),
                "meetup": resort.pk in meetups,
                "mine": resort.pk in mine_ids,
                "passes": sorted(p.slug for p in resort.passes.all()),
            }
        )
    return pins


def resort_index() -> list[dict[str, object]]:
    """Return every placed resort, for the map's search box to match against."""
    return [
        {
            "id": str(resort.uuid),
            "name": resort.name,
            "code": resort.code,
            "canton": resort.canton,
            "lng": resort.longitude,
            "lat": resort.latitude,
        }
        for resort in Resort.objects.placed()
    ]


@dataclass
class GroupAtResort:
    """The friends from one of your groups planned at a resort on a day."""

    group: Group
    plans: list[PlanDay] = field(default_factory=list)


@dataclass
class ResortDay:
    """Everything the resort sheet shows."""

    resort: Resort
    day: datetime.date
    groups: list[GroupAtResort]
    my_plan: PlanDay | None
    meetups: list[MeetUpCard]

    @property
    def friend_count(self) -> int:
        """Return how many different friends are there."""
        return len({p.user_id for g in self.groups for p in g.plans})


def resort_day(viewer: User, resort: Resort, day: datetime.date) -> ResortDay:
    """Return who from the viewer's groups is at ``resort`` on ``day``."""
    plans = list(visible_friend_plans(viewer, [day]).filter(resort=resort))
    groups = []
    for group in Group.objects.for_user(viewer).order_by("name"):
        member_ids = set(group.memberships.values_list("user_id", flat=True))
        here = [p for p in plans if p.user_id in member_ids]
        if here:
            groups.append(GroupAtResort(group=group, plans=here))
    my_plan = (
        PlanDay.objects.filter(user=viewer, date=day).select_related("resort").first()
    )
    meetups = meetups_for(viewer, day, resort)
    return ResortDay(
        resort=resort, day=day, groups=groups, my_plan=my_plan, meetups=meetups
    )
