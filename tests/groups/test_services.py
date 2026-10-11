"""Tests for apps/groups/services/ (people, plans, memberships, board, suggestions)."""

import datetime

import pytest

from apps.groups.models import Membership, PlanDay
from apps.groups.services import board, memberships, people, plans, suggestions
from apps.groups.services.memberships import MembershipError
from tests.factories import UserFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Status


# --- people ---------------------------------------------------------------


def test_friends_are_group_mates_only(crew: Crew) -> None:
    assert people.friend_ids(crew.sam) == {crew.anna.pk, crew.ben.pk}
    assert people.friend_ids(crew.outsider) == set()


def test_private_days_are_hidden_from_friends(crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.RESORT, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.outsider, crew.day, S.RESORT, resort=crew.verbier)
    seen = list(people.visible_friend_plans(crew.sam, [crew.day]))
    assert [p.user for p in seen] == [crew.anna]


def test_members_owner_first(crew: Crew) -> None:
    assert people.members_of(crew.group)[0] == crew.sam
    assert people.is_member(crew.group, crew.anna)
    assert not people.is_member(crew.group, crew.outsider)


# --- plans ----------------------------------------------------------------


def test_set_plan_upserts_and_clears(crew: Crew) -> None:
    plans.set_plan(
        crew.sam, crew.day, S.RESORT, resort=crew.verbier, note=" first lift "
    )
    plan = plans.set_plan(crew.sam, crew.day, S.NOT_SURE, resort=crew.verbier)
    assert plan.resort is None and plan.note == ""
    assert PlanDay.objects.filter(user=crew.sam).count() == 1
    plans.clear_plan(crew.sam, crew.day)
    assert not PlanDay.objects.filter(user=crew.sam).exists()


def test_set_plan_needs_resort(crew: Crew) -> None:
    with pytest.raises(ValueError, match="needs a resort"):
        plans.set_plan(crew.sam, crew.day, S.RESORT)


def test_is_plannable() -> None:
    today = plans.today()
    assert plans.is_plannable(today)
    assert not plans.is_plannable(today - datetime.timedelta(days=1))
    assert not plans.is_plannable(today + datetime.timedelta(days=400))


def test_friends_by_resort_and_counts(crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.sam, crew.day, S.RESORT, resort=crew.zermatt)
    entries = plans.friends_by_resort(crew.sam, crew.day)
    assert [(e.resort, e.names) for e in entries] == [(crew.verbier, "Anna and Ben")]
    assert plans.friend_counts(crew.sam, crew.day) == {crew.verbier.pk: 2}
    assert plans.friend_counts(crew.anna, crew.day) == {
        crew.verbier.pk: 1,
        crew.zermatt.pk: 1,
    }


def test_friends_by_resort_over_several_days(crew: Crew) -> None:
    later = crew.day + datetime.timedelta(days=1)
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.anna, later, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.ben, later, S.RESORT, resort=crew.zermatt)
    entries = plans.friends_by_resort(crew.sam, [crew.day, later])
    # Anna on both days at Verbier counts once.
    assert [(e.resort, e.names) for e in entries] == [
        (crew.verbier, "Anna"),
        (crew.zermatt, "Ben"),
    ]


def test_set_and_clear_several_plans(crew: Crew) -> None:
    days = [crew.day, crew.day + datetime.timedelta(days=3)]
    plans.set_plan(crew.sam, days[0], S.NOT_SKIING)
    made = plans.set_plans(crew.sam, days, S.RESORT, resort=crew.verbier, note=" a ")
    assert [(p.date, p.resort, p.note) for p in made] == [
        (days[0], crew.verbier, "a"),
        (days[1], crew.verbier, "a"),
    ]
    plans.clear_plans(crew.sam, days)
    assert not PlanDay.objects.filter(user=crew.sam).exists()


def test_join_names() -> None:
    assert plans.join_names([]) == ""
    assert plans.join_names(["A"]) == "A"
    assert plans.join_names(["A", "B", "C"]) == "A, B and C"


# --- memberships ------------------------------------------------------------


def test_create_group_makes_owner_member(crew: Crew) -> None:
    owner = crew.group.memberships.get(user=crew.sam)
    assert owner.role == Membership.Role.OWNER


def test_join_is_idempotent(crew: Crew) -> None:
    _, created = memberships.join_group(crew.group, crew.anna)
    assert not created


def test_owner_cannot_leave(crew: Crew) -> None:
    with pytest.raises(MembershipError):
        memberships.leave_group(crew.group, crew.sam)
    memberships.leave_group(crew.group, crew.anna)
    assert not people.is_member(crew.group, crew.anna)


def test_remove_member_rules(crew: Crew) -> None:
    with pytest.raises(MembershipError, match="Only the owner"):
        memberships.remove_member(crew.group, crew.anna, crew.ben)
    with pytest.raises(MembershipError, match="themselves"):
        memberships.remove_member(crew.group, crew.sam, crew.sam)
    memberships.remove_member(crew.group, crew.sam, crew.ben)
    assert not people.is_member(crew.group, crew.ben)


# --- board ----------------------------------------------------------------


def test_board_cells(crew: Crew) -> None:
    start = plans.today()
    plans.set_plan(crew.sam, start, S.RESORT, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.anna, start, S.RESORT, resort=crew.verbier, note="first lift")
    plans.set_plan(crew.ben, start, S.NOT_SURE)
    plans.set_plan(crew.anna, start + datetime.timedelta(days=1), S.NOT_SKIING)
    result = board.build_board(crew.group, crew.anna)
    assert len(result.days) == 7 and result.days[0].is_today
    rows = {row.person: row for row in result.rows}
    assert result.rows[0].person == crew.anna and result.rows[0].is_me
    assert rows[crew.sam].cells[0] == board.EMPTY  # private, seen by Anna
    assert rows[crew.anna].cells[0].text == "VERB"
    assert rows[crew.anna].cells[0].title == "Verbier · first lift"
    assert rows[crew.anna].cells[1].text == "–"
    assert rows[crew.ben].cells[0].text == "?"
    own = board.build_board(crew.group, crew.sam).rows[0].cells[0]
    assert own.text == "VERB" and own.private


def test_board_weeks(crew: Crew) -> None:
    start = datetime.date(2027, 1, 4)
    result = board.build_board(crew.group, crew.sam, start)
    assert result.previous_start == datetime.date(2026, 12, 28)
    assert result.next_start == datetime.date(2027, 1, 11)
    assert result.next_end == datetime.date(2027, 1, 17)
    assert result.end == datetime.date(2027, 1, 10)


# --- suggestions --------------------------------------------------------------


def test_suggestions_rank_by_people_then_moves(crew: Crew) -> None:
    dana = UserFactory.create(display_name="Dana")
    memberships.join_group(crew.group, dana)
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(dana, crew.day, S.RESORT, resort=crew.zermatt, is_private=True)
    plans.set_plan(crew.sam, crew.day, S.RESORT, resort=crew.zermatt, is_private=True)
    plans.set_plan(crew.outsider, crew.day, S.RESORT, resort=crew.zermatt)
    result = suggestions.suggest_resorts(crew.group, crew.day, crew.sam)
    assert [(s.resort, len(s.here), s.moves) for s in result] == [
        (crew.verbier, 2, 1),
        (crew.zermatt, 1, 2),
    ]
    assert result[0].names == "Anna and Ben"
    assert result[1].here == [crew.sam]


def test_upcoming_plans_and_marks(crew: Crew) -> None:
    today = plans.today()
    plans.set_plan(crew.sam, today - datetime.timedelta(days=1), S.NOT_SURE)
    plans.set_plan(crew.sam, today + datetime.timedelta(days=40), S.NOT_SKIING)
    plans.set_plan(crew.sam, today, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.anna, today, S.NOT_SURE)
    upcoming = plans.upcoming_plans(crew.sam)
    assert [plan.date for plan in upcoming] == [
        today,
        today + datetime.timedelta(days=40),
    ]
    assert plans.plan_marks(upcoming) == {
        today.isoformat(): "resort",
        (today + datetime.timedelta(days=40)).isoformat(): "not_skiing",
    }
