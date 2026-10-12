"""
apps/tour/demo.py — The onboarding tour's demo group, and its lifetime.

Starting the tour makes a "Thursday crew" for that person alone: they own
it, and six made-up friends (Sam, Anna, Ben, Chloé, Ella, Felix) fill a
week of days from today. The friends are shared by every
copy; they are inactive ``@tour.invalid`` accounts that can't sign in or
receive email, and are only ever in demo groups. Nobody touring sees
anyone else, because each copy holds only its owner and the friends.

A copy lives while its owner tours and no longer than ``DEMO_LIFETIME``.
Finishing or ending the tour deletes it; the middleware deletes one left
behind (a closed tab, a sign-out, another device) on the next page load,
since the app runs no scheduled jobs. See docs/onboarding-tour.md.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.groups.models import Group, Membership, PlanDay
from apps.groups.services.memberships import join_group
from apps.groups.services.plans import set_plan, today
from apps.resorts.models import Resort

GROUP_NAME = "Thursday crew"
FRIENDS = ["Sam", "Anna", "Ben", "Chloé", "Ella", "Felix"]
FRIEND_DOMAIN = "tour.invalid"
RESORTS = {
    "VERB": "Verbier",
    "SAASF": "Saas-Fee",
    "GRIME": "Grimentz",
    "CRA": "Crans-Montana",
    "CHAM": "Champéry",
}
# One row per friend, one cell per day from today: a resort code (skiing
# there) or "" for unsaid. A code can take "-" (there, not skiing). Today
# is the day the tour opens, so it is the busiest: three in Verbier.
WEEK = {
    "Sam": ["VERB", "VERB", "VERB-", "", "", "CRA", "SAASF"],
    "Anna": ["VERB", "GRIME", "", "", "SAASF", "CRA", ""],
    "Ben": ["SAASF", "VERB", "VERB", "", "VERB", "", "SAASF-"],
    "Chloé": ["VERB", "VERB", "VERB-", "", "VERB", "CRA", ""],
    "Ella": ["CHAM", "CHAM-", "CHAM-", "CHAM", "CHAM-", "", ""],
    "Felix": ["", "", "", "", "", "CRA", "CRA"],
}
NOTES = {("Anna", 0): "First lift, then Mont Fort"}
# The tour's own resort: the one opened on the map.
TOUR_RESORT = "VERB"
# Longer than anyone takes; past it, the copy is stale and deleted.
DEMO_LIFETIME = datetime.timedelta(hours=1)


class DemoUnavailable(Exception):
    """The demo can't be built: its resorts aren't imported."""


@dataclass(frozen=True)
class DemoWeek:
    """What the tour points at: the week's first day, and Verbier."""

    start: datetime.date
    resort: Resort


def demo_resorts() -> dict[str, Resort]:
    """Return the demo's resorts by code, or raise if any are missing."""
    found = {r.name: r for r in Resort.objects.filter(name__in=RESORTS.values())}
    missing = set(RESORTS.values()) - set(found)
    if missing:
        raise DemoUnavailable(f"Missing resorts: {sorted(missing)}")
    return {code: found[name] for code, name in RESORTS.items()}


def demo_week() -> DemoWeek:
    """Return the dates and resort the tour's frames point at."""
    start = today()
    return DemoWeek(
        start=start,
        resort=demo_resorts()[TOUR_RESORT],
    )


def _friend(name: str) -> User:
    """Return the made-up friend called ``name``, creating them if needed."""
    slug = name.lower().replace("é", "e")
    user, created = User.objects.get_or_create(
        email=f"{slug}@{FRIEND_DOMAIN}",
        defaults={
            "display_name": name,
            "is_active": False,
            "evening_email_enabled": False,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _write_cell(
    user: User, day: datetime.date, cell: str, resorts: dict[str, Resort], note: str
) -> None:
    """Write one friend's day: a code, a code with ? or -, or nothing."""
    if not cell:
        PlanDay.objects.filter(user=user, date=day).delete()
        return
    skiing = PlanDay.Skiing.YES
    code = cell
    if code[-1] == "-":
        skiing = PlanDay.Skiing.NO
        code = code[:-1]
    set_plan(user, day, skiing, resort=resorts[code] if code else None, note=note)


@transaction.atomic
def create_demo(owner: User) -> Group:
    """Make ``owner`` a fresh demo group, replacing any copy they had.

    The friends are shared by every copy, so their week is rewritten from
    today each time: the same days, whoever starts the tour.
    """
    resorts = demo_resorts()
    discard_demos(owner)
    friends = {name: _friend(name) for name in FRIENDS}
    start = today()
    days = [start + datetime.timedelta(days=n) for n in range(len(WEEK["Sam"]))]
    for name, cells in WEEK.items():
        for index, cell in enumerate(cells):
            _write_cell(
                friends[name],
                days[index],
                cell,
                resorts,
                NOTES.get((name, index), ""),
            )
    group = Group.objects.create(owner=owner, name=GROUP_NAME, is_demo=True)
    Membership.objects.create(group=group, user=owner, role=Membership.Role.OWNER)
    for friend in friends.values():
        join_group(group, friend)
    return group


def live_demo(owner: User, group_uuid: str) -> Group | None:
    """Return ``owner``'s demo group named ``group_uuid``, if it's still live.

    A copy past its lifetime is deleted and ``None`` returned.
    """
    group = Group.objects.demos().filter(owner=owner, uuid=group_uuid).first()
    if group is None:
        return None
    if group.created_at < timezone.now() - DEMO_LIFETIME:
        group.delete()
        return None
    return group


def discard_demos(owner: User) -> int:
    """Delete every demo group ``owner`` has; return how many there were."""
    count = 0
    for group in Group.objects.demos().filter(owner=owner):
        group.delete()
        count += 1
    return count


def discard_stale_demos() -> int:
    """Delete everyone's demo groups past their lifetime; return how many."""
    stale = Group.objects.demos().filter(created_at__lt=timezone.now() - DEMO_LIFETIME)
    count = 0
    for group in stale:
        group.delete()
        count += 1
    return count
