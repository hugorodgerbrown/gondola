"""Tests for apps/groups/models.py."""

import datetime

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.groups.models import Group, Membership, PlanDay
from tests.factories import (
    GroupFactory,
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
    group.owner.delete()
    assert not Group.objects.exists()
    assert not Membership.objects.exists()


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
        skiing=PlanDay.Skiing.NOT_SURE,
        resort=None,
    )
    assert str(at_resort) == "Cleo · 2027-01-09 · Zinal"
    assert str(unsure) == "Cleo · 2027-01-10 · Not sure yet"


def test_one_plan_per_user_per_day() -> None:
    plan = PlanDayFactory.create(date=SATURDAY)
    with pytest.raises(IntegrityError):
        PlanDayFactory.create(user=plan.user, date=SATURDAY)


@pytest.mark.parametrize(
    ("skiing", "named", "words"),
    [
        (PlanDay.Skiing.YES, True, "Zinal"),
        (PlanDay.Skiing.NOT_SURE, True, "Zinal, maybe skiing"),
        (PlanDay.Skiing.NO, True, "Zinal, not skiing"),
        (PlanDay.Skiing.YES, False, "Skiing, not sure where"),
        (PlanDay.Skiing.NOT_SURE, False, "Not sure yet"),
        (PlanDay.Skiing.NO, False, "Not skiing"),
    ],
)
def test_where_and_skiing_are_separate(skiing: str, named: bool, words: str) -> None:
    resort = ResortFactory.create(name="Zinal") if named else None
    plan = PlanDayFactory.create(skiing=skiing, resort=resort)
    assert plan.describe() == words
    assert plan.is_skiing == (skiing == PlanDay.Skiing.YES)
    assert PlanDay.objects.at_resorts().contains(plan) == named
    assert PlanDay.objects.skiing().contains(plan) == (named and plan.is_skiing)


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
