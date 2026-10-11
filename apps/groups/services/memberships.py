"""
apps/groups/services/memberships.py — Making, joining and leaving groups.

An invite link joins at once, but only when the person taps Join: opening
the link never joins by itself. The owner can reset the link, which kills
the old one. The owner can't leave their own group; they delete it.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User

from ..models import Group, Membership


class MembershipError(Exception):
    """A membership change isn't allowed."""


@transaction.atomic
def create_group(owner: User, name: str) -> Group:
    """Create a group with ``owner`` as its owner and first member."""
    group = Group.objects.create(owner=owner, name=name.strip())
    Membership.objects.create(group=group, user=owner, role=Membership.Role.OWNER)
    return group


def join_group(group: Group, user: User) -> tuple[Membership, bool]:
    """Add ``user`` to ``group``; return the membership and whether it's new."""
    return Membership.objects.get_or_create(
        group=group, user=user, defaults={"role": Membership.Role.MEMBER}
    )


def leave_group(group: Group, user: User) -> None:
    """Take ``user`` out of ``group``. The owner deletes the group instead."""
    if group.owner_id == user.pk:
        raise MembershipError("The owner can't leave. Delete the group instead.")
    group.memberships.filter(user=user).delete()


def remove_member(group: Group, by: User, member: User) -> None:
    """Let the owner remove someone else from the group."""
    if group.owner_id != by.pk:
        raise MembershipError("Only the owner can remove people.")
    if member.pk == by.pk:
        raise MembershipError("The owner can't remove themselves.")
    group.memberships.filter(user=member).delete()
