"""
apps/groups/services/meetups.py — Proposing, joining and leaving meet-ups.

A meet-up is a group's agreed resort on one day, with an optional time and
meeting pin, and one share link. The link opens a page anyone can read;
joining needs an account. Joining sets that day in the joiner's own days
to the meet-up resort, so the map and the board update for everyone. A
person who joins from the link and isn't in the group yet is added to it
(the button says so), because a meet-up link is sent to the same group
chat as the invite link. Once the day has passed the link is read-only.
"""

from __future__ import annotations

import datetime

from django.db import transaction

from apps.accounts.models import User
from apps.resorts.models import Resort

from ..models import Group, MeetUp, MeetUpParticipant, PlanDay
from .memberships import join_group
from .plans import set_plan, today


class MeetUpError(Exception):
    """A meet-up change isn't allowed."""


def is_open(meetup: MeetUp) -> bool:
    """Return whether people can still join: the day hasn't passed."""
    return meetup.date >= today()


def _plan_meetup_day(user: User, meetup: MeetUp) -> PlanDay:
    """Set ``user``'s day to the meet-up resort, keeping its note and privacy.

    A day belongs to the person, not the group, so a private day stays
    private: the meet-up page still lists them, but their other groups
    see nothing new.
    """
    existing = PlanDay.objects.filter(user=user, date=meetup.date).first()
    note = existing.note if existing and existing.resort_id == meetup.resort_id else ""
    return set_plan(
        user,
        meetup.date,
        PlanDay.Status.RESORT,
        resort=meetup.resort,
        note=note,
        is_private=existing.is_private if existing else False,
    )


def meetup_on(group: Group, day: datetime.date) -> MeetUp | None:
    """Return the group's meet-up on ``day``, if there is one."""
    return group.meetups.filter(date=day).first()


@transaction.atomic
def propose_meetup(
    group: Group,
    organiser: User,
    day: datetime.date,
    resort: Resort,
    *,
    start_time: datetime.time | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> MeetUp:
    """Create a meet-up; the organiser is its first participant.

    A group has at most one meet-up a day, so everyone agrees on one place.
    """
    if day < today():
        raise MeetUpError("Pick today or a later day.")
    if meetup_on(group, day):
        raise MeetUpError("This group already has a meet-up that day.")
    if (latitude is None) != (longitude is None):
        raise MeetUpError("A meeting pin needs both coordinates.")
    meetup = MeetUp.objects.create(
        group=group,
        organiser=organiser,
        date=day,
        resort=resort,
        start_time=start_time,
        meeting_latitude=latitude,
        meeting_longitude=longitude,
    )
    MeetUpParticipant.objects.create(meetup=meetup, user=organiser)
    _plan_meetup_day(organiser, meetup)
    return meetup


@transaction.atomic
def join_meetup(meetup: MeetUp, user: User) -> bool:
    """Add ``user`` to the meet-up; return whether they joined the group too."""
    if not is_open(meetup):
        raise MeetUpError("This meet-up has passed.")
    _, joined_group = join_group(meetup.group, user)
    MeetUpParticipant.objects.get_or_create(meetup=meetup, user=user)
    _plan_meetup_day(user, meetup)
    return joined_group


def leave_meetup(meetup: MeetUp, user: User) -> None:
    """Take ``user`` off the meet-up. Their day stays as it is."""
    if meetup.organiser_id == user.pk:
        raise MeetUpError("You organised this one. Cancel it instead.")
    meetup.participants.filter(user=user).delete()


def can_cancel(meetup: MeetUp, user: User) -> bool:
    """Return whether ``user`` may cancel: the organiser or the group owner."""
    return user.pk in (meetup.organiser_id, meetup.group.owner_id)


def cancel_meetup(meetup: MeetUp, user: User) -> None:
    """Delete the meet-up. People's days stay as they are."""
    if not can_cancel(meetup, user):
        raise MeetUpError("Only the organiser or the group owner can cancel.")
    meetup.delete()


def is_going(meetup: MeetUp, user: User) -> bool:
    """Return whether ``user`` is on the meet-up's list."""
    return meetup.participants.filter(user=user).exists()
