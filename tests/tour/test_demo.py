"""Tests for apps/tour/demo.py."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.groups.models import Group, PlanDay
from apps.groups.services.plans import today
from apps.resorts.models import Resort
from apps.tour.demo import (
    DEMO_LIFETIME,
    FRIENDS,
    DemoUnavailable,
    create_demo,
    demo_week,
    discard_demos,
    discard_stale_demos,
    live_demo,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _age(group: Group, by: datetime.timedelta) -> None:
    """Make ``group`` look ``by`` older than it is."""
    Group.objects.filter(pk=group.pk).update(created_at=timezone.now() - by)


def test_create_demo_makes_a_private_copy(
    tourist: User, resorts: dict[str, Resort]
) -> None:
    group = create_demo(tourist)
    assert group.is_demo
    assert group.owner == tourist
    names = {m.user.to_string() for m in group.memberships.select_related("user")}
    assert names == {"Tess", *FRIENDS}
    friends = User.objects.filter(email__endswith="@tour.invalid")
    assert friends.count() == len(FRIENDS)
    assert not friends.filter(is_active=True).exists()
    assert not friends.filter(evening_email_enabled=True).exists()
    # Today is the busy day: Sam, Anna and Chloé in Verbier.
    verbier = PlanDay.objects.filter(date=today(), resort=resorts["VERB"])
    assert verbier.count() == 3
    # The tourist's own days are left alone.
    assert not PlanDay.objects.filter(user=tourist).exists()


def test_each_tourist_gets_their_own_copy(resorts: dict[str, Resort]) -> None:
    one, two = UserFactory.create(), UserFactory.create()
    first, second = create_demo(one), create_demo(two)
    assert first.pk != second.pk
    assert not second.memberships.filter(user=one).exists()
    # The made-up friends are shared, not duplicated.
    assert User.objects.filter(email__endswith="@tour.invalid").count() == len(FRIENDS)


def test_starting_again_replaces_the_copy(
    tourist: User, resorts: dict[str, Resort]
) -> None:
    first = create_demo(tourist)
    second = create_demo(tourist)
    assert not Group.objects.filter(pk=first.pk).exists()
    assert Group.objects.demos().get(owner=tourist) == second


def test_rewriting_the_week_clears_a_day_left_unsaid(
    tourist: User, resorts: dict[str, Resort]
) -> None:
    create_demo(tourist)
    felix = User.objects.get(email="felix@tour.invalid")
    tomorrow = today() + datetime.timedelta(days=1)
    PlanDay.objects.create(user=felix, date=tomorrow, resort=resorts["VERB"])
    create_demo(tourist)
    assert not PlanDay.objects.filter(user=felix, date=tomorrow).exists()


def test_missing_resorts_make_the_demo_unavailable(tourist: User) -> None:
    with pytest.raises(DemoUnavailable):
        create_demo(tourist)


def test_demo_week_points_at_today_and_verbier(resorts: dict[str, Resort]) -> None:
    week = demo_week()
    assert week.start == today()
    assert week.resort == resorts["VERB"]


def test_live_demo_returns_a_fresh_copy(
    tourist: User, resorts: dict[str, Resort]
) -> None:
    group = create_demo(tourist)
    assert live_demo(tourist, str(group.uuid)) == group
    assert live_demo(UserFactory.create(), str(group.uuid)) is None


def test_live_demo_deletes_a_stale_copy(
    tourist: User, resorts: dict[str, Resort]
) -> None:
    group = create_demo(tourist)
    _age(group, DEMO_LIFETIME + datetime.timedelta(minutes=1))
    assert live_demo(tourist, str(group.uuid)) is None
    assert not Group.objects.filter(pk=group.pk).exists()


def test_discard_demos_keeps_real_groups(
    tourist: User, resorts: dict[str, Resort]
) -> None:
    real = Group.objects.create(owner=tourist, name="Real")
    create_demo(tourist)
    assert discard_demos(tourist) == 1
    assert list(Group.objects.filter(owner=tourist)) == [real]


def test_discard_stale_demos_only_takes_old_copies(
    resorts: dict[str, Resort],
) -> None:
    old = create_demo(UserFactory.create())
    fresh = create_demo(UserFactory.create())
    _age(old, DEMO_LIFETIME * 2)
    assert discard_stale_demos() == 1
    assert list(Group.objects.demos()) == [fresh]
