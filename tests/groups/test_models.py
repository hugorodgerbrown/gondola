"""Tests for apps/groups/models.py."""

import datetime

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.groups.models import Group, MeetUp, Membership, PlanDay
from tests.factories import (
    GroupFactory,
    MeetUpFactory,
    MeetUpParticipantFactory,
    MembershipFactory,
    PlanDayFactory,
    ResortFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

SATURDAY = datetime.date(2027, 1, 9)


# --- Group -----------------------------------------------------------------


def test_group_to_string_and_token() -> None:
    group = GroupFactory.create(name="Verbier crew")
    assert str(group) == "Verbier crew"
    assert len(group.invite_token) == 43


def test_reset_invite_token_replaces_it() -> None:
    group = GroupFactory.create()
    old = group.invite_token
    new = group.reset_invite_token()
    group.refresh_from_db()
    assert group.invite_token == new != old
    assert not Group.objects.filter(invite_token=old).exists()


def test_for_user_returns_groups_they_belong_to() -> None:
    anna = UserFactory.create()
    mine = MembershipFactory.create(user=anna).group
    GroupFactory.create()
    assert list(Group.objects.for_user(anna)) == [mine]


def test_deleting_the_owner_deletes_the_group() -> None:
    group = GroupFactory.create()
    MembershipFactory.create(group=group)
    MeetUpFactory.create(group=group)
    group.owner.delete()
    assert not Group.objects.exists()
    assert not Membership.objects.exists()
    assert not MeetUp.objects.exists()


# --- Membership ------------------------------------------------------------


def test_membership_to_string() -> None:
    member = MembershipFactory.create(
        user=UserFactory.create(display_name="Ben"),
        group=GroupFactory.create(name="Crew"),
    )
    assert str(member) == "Ben in Crew"


def test_one_membership_per_group_and_user() -> None:
    member = MembershipFactory.create()
    with pytest.raises(IntegrityError):
        MembershipFactory.create(group=member.group, user=member.user)


def test_one_owner_per_group() -> None:
    group = GroupFactory.create()
    owner = MembershipFactory.create(
        group=group, user=group.owner, role=Membership.Role.OWNER
    )
    MembershipFactory.create(group=group)
    assert list(Membership.objects.owners()) == [owner]
    with pytest.raises(IntegrityError):
        MembershipFactory.create(group=group, role=Membership.Role.OWNER)


# --- PlanDay ---------------------------------------------------------------


def test_planday_to_string() -> None:
    user = UserFactory.create(display_name="Cleo")
    at_resort = PlanDayFactory.create(
        user=user, date=SATURDAY, resort=ResortFactory.create(name="Zinal")
    )
    unsure = PlanDayFactory.create(
        user=user,
        date=SATURDAY + datetime.timedelta(1),
        status=PlanDay.Status.NOT_SURE,
        resort=None,
    )
    assert str(at_resort) == "Cleo · 2027-01-09 · Zinal"
    assert str(unsure) == "Cleo · 2027-01-10 · Not sure yet"


def test_one_plan_per_user_per_day() -> None:
    plan = PlanDayFactory.create(date=SATURDAY)
    with pytest.raises(IntegrityError):
        PlanDayFactory.create(user=plan.user, date=SATURDAY)


@pytest.mark.parametrize(
    ("status", "with_resort"),
    [
        (PlanDay.Status.RESORT, False),
        (PlanDay.Status.NOT_SURE, True),
        (PlanDay.Status.NOT_SKIING, True),
    ],
)
def test_resort_must_match_status(status: str, with_resort: bool) -> None:
    resort = ResortFactory.create() if with_resort else None
    with pytest.raises(IntegrityError):
        PlanDayFactory.create(status=status, resort=resort)


def test_planday_querysets() -> None:
    shared = PlanDayFactory.create(date=SATURDAY)
    private = PlanDayFactory.create(date=SATURDAY, is_private=True)
    earlier = PlanDayFactory.create(date=SATURDAY - datetime.timedelta(3))
    assert set(PlanDay.objects.on(SATURDAY)) == {shared, private}
    assert private not in PlanDay.objects.shared()
    assert earlier not in PlanDay.objects.from_date(SATURDAY)
    assert list(PlanDay.objects.from_date(earlier.date)) == [earlier, shared, private]


def test_a_planned_resort_cannot_be_deleted() -> None:
    plan = PlanDayFactory.create()
    assert plan.resort is not None
    with pytest.raises(ProtectedError):
        plan.resort.delete()


# --- MeetUp ----------------------------------------------------------------


def test_meetup_defaults() -> None:
    meetup = MeetUpFactory.create(resort=ResortFactory.create(name="Grimentz"))
    assert str(meetup) == "Grimentz · 2027-01-09"
    assert meetup.organiser == meetup.group.owner
    assert meetup.start_time is None
    assert not meetup.has_meeting_pin
    assert len(meetup.share_token) == 43


def test_meetup_with_time_and_pin() -> None:
    meetup = MeetUpFactory.create(
        start_time=datetime.time(9, 30),
        meeting_latitude=46.11,
        meeting_longitude=7.25,
    )
    assert meetup.has_meeting_pin


def test_meeting_pin_is_both_or_neither() -> None:
    with pytest.raises(IntegrityError):
        MeetUpFactory.create(meeting_latitude=46.11, meeting_longitude=None)


def test_meetup_from_date() -> None:
    upcoming = MeetUpFactory.create(date=SATURDAY)
    MeetUpFactory.create(date=SATURDAY - datetime.timedelta(1))
    assert list(MeetUp.objects.from_date(SATURDAY)) == [upcoming]


# --- MeetUpParticipant -----------------------------------------------------


def test_participant_to_string_and_roster() -> None:
    meetup = MeetUpFactory.create(resort=ResortFactory.create(name="Zinal"))
    going = MeetUpParticipantFactory.create(
        meetup=meetup, user=UserFactory.create(display_name="Dev")
    )
    assert str(going) == "Dev → Zinal · 2027-01-09"
    assert list(meetup.participants.all()) == [going]


def test_one_participation_per_user() -> None:
    going = MeetUpParticipantFactory.create()
    with pytest.raises(IntegrityError):
        MeetUpParticipantFactory.create(meetup=going.meetup, user=going.user)
