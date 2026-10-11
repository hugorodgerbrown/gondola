"""
apps/groups/services/testers.py — Who is in the "UI test" group.

Membership of the "UI test" planning group follows one Django auth group,
"Testers". The seed_ui_test command puts its made-up people in Testers; a
real account joins by being added to Testers in the admin, and leaves by
being taken out of it. ``sync_tester`` is the one place that rule is
applied, called inline from the admin and the seed command.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import Group as AuthGroup

from apps.accounts.models import User

from ..models import Group
from .memberships import join_group, leave_group

TESTERS = "Testers"
UI_TEST_GROUP = "UI test"
# The made-up people's email domain; the group's owner is always one.
MADE_UP_DOMAIN = "ui-test.invalid"


def get_testers_group() -> AuthGroup:
    """Return the Testers auth group, creating it if needed."""
    group, _ = AuthGroup.objects.get_or_create(name=TESTERS)
    return group


def ui_test_group() -> Group | None:
    """Return the "UI test" planning group, or None before it's seeded."""
    return (
        Group.objects.filter(
            name=UI_TEST_GROUP, owner__email__endswith=f"@{MADE_UP_DOMAIN}"
        )
        .order_by("created_at")
        .first()
    )


def is_tester(user: User) -> bool:
    """Return whether ``user`` is in the Testers auth group."""
    return user.groups.filter(name=TESTERS).exists()


def sync_tester(user: User, group: Group | None = None) -> None:
    """Join ``user`` to "UI test" if they're a tester, or take them out.

    Does nothing before the group is seeded, and never removes its owner.
    """
    group = group or ui_test_group()
    if group is None:
        return
    if is_tester(user):
        join_group(group, user)
    elif group.owner_id != user.pk:
        leave_group(group, user)


def set_testers(users: Iterable[User], *, on: bool) -> None:
    """Add ``users`` to Testers (or take them out), and sync each."""
    auth_group = get_testers_group()
    group = ui_test_group()
    for user in users:
        if on:
            user.groups.add(auth_group)
        else:
            user.groups.remove(auth_group)
        sync_tester(user, group)
