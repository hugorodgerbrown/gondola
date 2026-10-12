"""Tests for apps/groups/services/ (people, plans, memberships, board)."""

import datetime

import pytest

from apps.groups.models import Membership, PlanDay
from apps.groups.services import board, memberships, people, plans
from apps.groups.services.memberships import MembershipError
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Skiing


# --- people ---------------------------------------------------------------


def test_friends_are_group_mates_only(crew: Crew) -> None:
    assert people.friend_ids(crew.sam) == {crew.anna.pk, crew.ben.pk}
    assert people.friend_ids(crew.outsider) == set()


def test_private_days_are_hidden_from_friends(crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.YES, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.outsider, crew.day, S.YES, resort=crew.verbier)
    seen = list(people.visible_friend_plans(crew.sam, [crew.day]))
    assert [p.user for p in seen] == [crew.anna]


def test_members_owner_first(crew: Crew) -> None:
    assert people.members_of(crew.group)[0] == crew.sam
    assert people.is_member(crew.group, crew.anna)
    assert not people.is_member(crew.group, crew.outsider)


# --- plans ----------------------------------------------------------------


def test_set_plan_upserts_and_clears(crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, S.YES, resort=crew.verbier, note=" first lift ")
    plan = plans.set_plan(crew.sam, crew.day, S.NO, resort=crew.verbier)
    # Where and skiing are separate: in Verbier, not skiing.
    assert plan.resort == crew.verbier and plan.note == ""
    assert PlanDay.objects.filter(user=crew.sam).count() == 1
    plans.clear_plan(crew.sam, crew.day)
    assert not PlanDay.objects.filter(user=crew.sam).exists()


def test_skiing_needs_no_resort(crew: Crew) -> None:
    plan = plans.set_plan(crew.sam, crew.day, S.YES)
    assert plan.describe() == "Skiing, not sure where"


def test_is_plannable() -> None:
    today = plans.today()
    assert plans.is_plannable(today)
    assert not plans.is_plannable(today - datetime.timedelta(days=1))
    assert not plans.is_plannable(today + datetime.timedelta(days=400))


def test_friends_by_resort_and_counts(crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.sam, crew.day, S.YES, resort=crew.zermatt)
    entries = plans.friends_by_resort(crew.sam, crew.day)
    assert [(e.resort, e.names) for e in entries] == [(crew.verbier, "Anna and Ben")]
    assert plans.friend_counts(crew.sam, crew.day) == {crew.verbier.pk: 2}
    assert plans.friend_counts(crew.anna, crew.day) == {
        crew.verbier.pk: 1,
        crew.zermatt.pk: 1,
    }


def test_friends_by_resort_over_several_days(crew: Crew) -> None:
    later = crew.day + datetime.timedelta(days=1)
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.anna, later, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, later, S.YES, resort=crew.zermatt)
    entries = plans.friends_by_resort(crew.sam, [crew.day, later])
    # Anna on both days at Verbier counts once.
    assert [(e.resort, e.names) for e in entries] == [
        (crew.verbier, "Anna"),
        (crew.zermatt, "Ben"),
    ]


def test_update_plans_changes_only_what_is_given(crew: Crew) -> None:
    days = [crew.day + datetime.timedelta(days=n) for n in range(4)]
    plans.set_plan(crew.sam, days[0], S.NO, note="spa", is_private=True)
    # Ten days in Verbier, then skiing on some of them.
    plans.update_plans(crew.sam, days, resort=crew.verbier, skiing=S.NO)
    made = plans.update_plans(crew.sam, days[:2], skiing=S.YES, note=" a ")
    assert [(p.date, p.resort, p.skiing, p.note) for p in made] == [
        (days[0], crew.verbier, S.YES, "a"),
        (days[1], crew.verbier, S.YES, "a"),
    ]
    first = PlanDay.objects.get(user=crew.sam, date=days[0])
    assert first.is_private  # untouched
    rest = PlanDay.objects.filter(user=crew.sam, date__in=days[2:])
    assert {(p.resort, p.skiing, p.note) for p in rest} == {(crew.verbier, S.NO, "")}
    # A new day starts out skiing, at no resort.
    (fresh,) = plans.update_plans(crew.sam, [days[0] + datetime.timedelta(9)])
    assert (fresh.skiing, fresh.resort, fresh.is_private) == (S.YES, None, False)
    plans.clear_plans(crew.sam, days)
    assert PlanDay.objects.filter(user=crew.sam).count() == 1


def test_friends_around_count_but_are_marked(crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.NO, resort=crew.verbier)
    plans.set_plan(
        crew.ben, crew.day + datetime.timedelta(1), S.YES, resort=crew.verbier
    )
    (entry,) = plans.friends_by_resort(crew.sam, crew.day)
    assert entry.names == "Anna and Ben (around)"
    assert plans.friend_counts(crew.sam, crew.day) == {crew.verbier.pk: 2}
    # Over two days Ben skis one of them, so he counts as skiing.
    (both,) = plans.friends_by_resort(
        crew.sam, [crew.day, crew.day + datetime.timedelta(1)]
    )
    assert both.names == "Anna and Ben"


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
    plans.set_plan(crew.sam, start, S.YES, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.anna, start, S.YES, resort=crew.verbier, note="first lift")
    plans.set_plan(
        crew.ben, start, S.YES
    )  # an older day, from before resorts were required
    plans.set_plan(crew.anna, start + datetime.timedelta(days=1), S.NO)
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


def test_board_cell_around_a_resort(crew: Crew) -> None:
    start = plans.today()
    plans.set_plan(crew.ben, start, S.NO, resort=crew.zermatt)
    rows = {row.person: row for row in board.build_board(crew.group, crew.sam).rows}
    cell = rows[crew.ben].cells[0]
    assert (cell.text, cell.title, cell.quiet) == ("ZERM", "Zermatt, not skiing", True)


def test_board_weeks(crew: Crew) -> None:
    start = datetime.date(2027, 1, 4)
    result = board.build_board(crew.group, crew.sam, start)
    assert result.previous_start == datetime.date(2026, 12, 28)
    assert result.next_start == datetime.date(2027, 1, 11)
    assert result.next_end == datetime.date(2027, 1, 17)
    assert result.end == datetime.date(2027, 1, 10)


# --- plans -------------------------------------------------------------------------


def test_upcoming_plans_and_marks(crew: Crew) -> None:
    today = plans.today()
    plans.set_plan(crew.sam, today - datetime.timedelta(days=1), S.NO)
    plans.set_plan(crew.sam, today + datetime.timedelta(days=40), S.NO)
    plans.set_plan(crew.sam, today, S.YES, resort=crew.verbier)
    plans.set_plan(crew.anna, today, S.NO, resort=crew.zermatt)
    upcoming = plans.upcoming_plans(crew.sam)
    assert [plan.date for plan in upcoming] == [
        today,
        today + datetime.timedelta(days=40),
    ]
    assert plans.plan_marks(upcoming) == {
        today.isoformat(): "skiing",
        (today + datetime.timedelta(days=40)).isoformat(): "not_skiing",
    }
