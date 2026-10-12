"""
apps/groups/models.py — Groups of friends, their plans and their meet-ups.

* ``Group`` — friends who share plans. Joined through one invite link
  that joins at once; the owner can reset the link to kill the old one.
  A demo group (``is_demo``) is the onboarding tour's private copy of
  "Thursday crew": it only ever shows while its owner is touring.
* ``Membership`` — a person in a group, as its owner or a member. Group
  members see each other's names and days; joining is the consent.
* ``PlanDay`` — where one person is skiing on one date. It belongs to the
  person, not a group: say it once and every group they're in sees it.
* ``MeetUp`` — a group's agreed resort on a day, with an optional time and
  meeting pin, and its own share link.
* ``MeetUpParticipant`` — a person going to a meet-up.

``date`` and ``start_time`` are Swiss wall-clock, because every resort is
Swiss.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

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
        a demo group never shows: not on the map, the board, My days or in
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
    invite_token = models.CharField(
        max_length=64, unique=True, default=make_token, editable=False
    )
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

    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="memberships"
    )
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
            models.UniqueConstraint(
                fields=["group", "user"], name="membership_one_per_group_user"
            ),
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

    def shared(self) -> PlanDayQuerySet:
        """Return plans group-mates may see (not marked private)."""
        return self.filter(is_private=False)

    def from_date(self, day: datetime.date) -> PlanDayQuerySet:
        """Return plans on or after ``day``."""
        return self.filter(date__gte=day)

    def at_resorts(self) -> PlanDayQuerySet:
        """Return plans that name a resort, skiing or not."""
        return self.filter(resort__isnull=False)

    def skiing(self) -> PlanDayQuerySet:
        """Return plans at a resort where the person is skiing."""
        return self.filter(resort__isnull=False, skiing=PlanDay.Skiing.YES)


class PlanDay(BaseModel):
    """What one person said about one date: where they'll be, and if skiing.

    The two are separate: someone can be in Verbier for ten days and ski
    three of them, and friends still want to know they're around.
    """

    class Skiing(models.TextChoices):
        """Whether the person is skiing that day."""

        YES = "skiing", "Skiing"
        NOT_SURE = "not_sure", "Not sure yet"
        NO = "not_skiing", "Not skiing"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plan_days",
    )
    date = models.DateField()
    skiing = models.CharField(max_length=10, choices=Skiing, default=Skiing.YES)
    resort = models.ForeignKey(
        Resort,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="plan_days",
        help_text="Where they'll be, skiing or not. Empty: not at a resort.",
    )
    note = models.CharField(max_length=140, blank=True)
    is_private = models.BooleanField(
        default=False, help_text="Hidden from group-mates; looks unplanned."
    )

    objects = PlanDayQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="planday_one_per_user_date"
            ),
        ]

    def to_string(self) -> str:
        """Return who is where on which day."""
        return f"{self.user} · {self.date:%Y-%m-%d} · {self.describe()}"

    @property
    def is_skiing(self) -> bool:
        """Return whether the person said they're skiing."""
        return self.skiing == self.Skiing.YES

    def describe(self) -> str:
        """Return the day in words: "Verbier, not skiing", "Not sure yet"."""
        if self.resort is None:
            if self.skiing == self.Skiing.YES:
                return "Skiing, not sure where"
            return self.get_skiing_display()
        if self.skiing == self.Skiing.NO:
            return f"{self.resort.name}, not skiing"
        if self.skiing == self.Skiing.NOT_SURE:
            return f"{self.resort.name}, maybe skiing"
        return self.resort.name


# ---------------------------------------------------------------------------
# MeetUp
# ---------------------------------------------------------------------------


class MeetUpQuerySet(models.QuerySet["MeetUp"]):
    """Custom queryset for MeetUp."""

    def from_date(self, day: datetime.date) -> MeetUpQuerySet:
        """Return meet-ups on or after ``day``."""
        return self.filter(date__gte=day)


class MeetUp(BaseModel):
    """A group's agreed resort on one day, with an optional time and pin."""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="meetups")
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organised_meetups",
    )
    date = models.DateField()
    resort = models.ForeignKey(Resort, on_delete=models.PROTECT, related_name="meetups")
    start_time = models.TimeField(null=True, blank=True)
    meeting_latitude = models.FloatField(null=True, blank=True)
    meeting_longitude = models.FloatField(null=True, blank=True)
    share_token = models.CharField(
        max_length=64, unique=True, default=make_token, editable=False
    )

    objects = MeetUpQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        meeting_latitude__isnull=True, meeting_longitude__isnull=True
                    )
                    | models.Q(
                        meeting_latitude__isnull=False,
                        meeting_longitude__isnull=False,
                    )
                ),
                name="meetup_meeting_pin_pair",
            ),
            models.UniqueConstraint(
                fields=["group", "date"], name="meetup_one_per_group_day"
            ),
        ]

    def to_string(self) -> str:
        """Return the resort and day."""
        return f"{self.resort} · {self.date:%Y-%m-%d}"

    @property
    def has_meeting_pin(self) -> bool:
        """Return whether a meeting pin was dropped."""
        return self.meeting_latitude is not None


# ---------------------------------------------------------------------------
# MeetUpParticipant
# ---------------------------------------------------------------------------


class MeetUpParticipantQuerySet(models.QuerySet["MeetUpParticipant"]):
    """Custom queryset for MeetUpParticipant."""


class MeetUpParticipant(BaseModel):
    """One person going to one meet-up; ``created_at`` is when they joined."""

    meetup = models.ForeignKey(
        MeetUp, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meetup_participations",
    )

    objects = MeetUpParticipantQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["meetup", "user"], name="meetupparticipant_one_per_user"
            ),
        ]

    def to_string(self) -> str:
        """Return who is going to which meet-up."""
        return f"{self.user} → {self.meetup}"
