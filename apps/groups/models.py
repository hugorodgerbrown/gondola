"""apps/groups/models.py — Groups of friends and their plans.

* ``Group`` — friends who share plans. Joined through one invite link
  that joins at once; the owner can reset the link to kill the old one.
  A demo group (``is_demo``) is the onboarding tour's private copy of
  "Thursday crew": it only ever shows while its owner is touring.
* ``Membership`` — a person in a group, as its owner or a member. Group
  members see each other's names and days; joining is the consent.
* ``PlanDay`` — the resort one person will be in on one date. It belongs
  to the person, not a group: say it once and every group they're in sees
  it. Whether they ski that day is left to the group chat.
``date`` is Swiss wall-clock, because every resort is Swiss.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.core.tokens import make_token
from apps.resorts.models import Resort

if TYPE_CHECKING:
    from apps.accounts.models import User

# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


class GroupQuerySet(models.QuerySet["Group"]):
    """Custom queryset for Group."""

    def for_user(self, user: User) -> GroupQuerySet:
        """Return the groups ``user`` sees: their real ones, or the tour's.

        While someone tours, ``apps.tour.middleware`` sets
        ``user.tour_group_id`` and their only group is the demo copy, so
        every screen shows the made-up friends and nothing real. Otherwise
        a demo group never shows: not on the map, the board, the calendar or in
        the evening email, which runs with no request at all.
        """
        mine = self.filter(memberships__user=user)
        tour_group_id = getattr(user, "tour_group_id", None)
        if tour_group_id is not None:
            return mine.filter(pk=tour_group_id)
        return mine.filter(is_demo=False)

    def real(self) -> GroupQuerySet:
        """Return the groups that aren't the tour's demo copies."""
        return self.filter(is_demo=False)

    def demos(self) -> GroupQuerySet:
        """Return the tour's demo copies."""
        return self.filter(is_demo=True)


class Group(BaseModel):
    """A group of friends who share their plans with each other."""

    name = models.CharField(max_length=60)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # Deleting the owner's account deletes the group.
        on_delete=models.CASCADE,
        related_name="owned_groups",
    )
    invite_token = models.CharField(max_length=64, unique=True, default=make_token, editable=False)
    is_demo = models.BooleanField(
        default=False,
        editable=False,
        help_text="The onboarding tour's private copy; deleted when the tour ends.",
    )

    objects = GroupQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]

    def to_string(self) -> str:
        """Return the group name."""
        return self.name

    def reset_invite_token(self) -> str:
        """Replace the invite token, so the old link stops working."""
        self.invite_token = make_token()
        self.save(update_fields=["invite_token", "updated_at"])
        return self.invite_token


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


class MembershipQuerySet(models.QuerySet["Membership"]):
    """Custom queryset for Membership."""

    def owners(self) -> MembershipQuerySet:
        """Return owner memberships."""
        return self.filter(role=Membership.Role.OWNER)


class Membership(BaseModel):
    """One person in one group; ``created_at`` is when they joined."""

    class Role(models.TextChoices):
        """A member's role in their group."""

        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(max_length=10, choices=Role, default=Role.MEMBER)

    objects = MembershipQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="membership_one_per_group_user"),
            models.UniqueConstraint(
                fields=["group"],
                condition=models.Q(role="owner"),
                name="membership_one_owner_per_group",
            ),
        ]

    def to_string(self) -> str:
        """Return who is in which group."""
        return f"{self.user} in {self.group}"


# ---------------------------------------------------------------------------
# PlanDay
# ---------------------------------------------------------------------------


class PlanDayQuerySet(models.QuerySet["PlanDay"]):
    """Custom queryset for PlanDay."""

    def on(self, day: datetime.date) -> PlanDayQuerySet:
        """Return plans for one date."""
        return self.filter(date=day)

    def from_date(self, day: datetime.date) -> PlanDayQuerySet:
        """Return plans on or after ``day``."""
        return self.filter(date__gte=day)


class PlanDay(BaseModel):
    """Which resort one person will be in on one date.

    Gondola answers "who's in town": a day is said (in Verbier) or unsaid.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plan_days",
    )
    date = models.DateField()
    resort = models.ForeignKey(
        Resort,
        on_delete=models.PROTECT,
        related_name="plan_days",
        help_text="Where they'll be.",
    )
    said_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the person chose this resort: for a write queued offline, "
        "when they made it, not when it arrived.",
    )

    objects = PlanDayQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="planday_one_per_user_date"),
        ]

    def to_string(self) -> str:
        """Return who is where on which day."""
        return f"{self.user} · {self.date:%Y-%m-%d} · {self.describe()}"

    def describe(self) -> str:
        """Return the day in words: the resort's name."""
        return self.resort.name
