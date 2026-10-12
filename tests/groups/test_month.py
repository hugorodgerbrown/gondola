"""Tests for the calendar's month view: apps/groups/services/month.py."""

import datetime

import pytest
from freezegun import freeze_time

from apps.groups.models import PlanDay
from apps.groups.services import month, plans
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Skiing


def days_of(cal: month.Month) -> dict[datetime.date, month.MonthDay]:
    """Return the month's days by date."""
    return {day.date: day for week in cal.weeks for day in week}


@freeze_time("2026-10-11 09:00:00+02:00")
def test_month_has_monday_weeks_and_stays_plannable(crew: Crew) -> None:
    cal = month.build_month(crew.sam, datetime.date(2026, 12, 25))
    assert cal.first == datetime.date(2026, 12, 1)
    assert all(len(week) == 7 for week in cal.weeks)
    assert cal.weeks[0][0].date == datetime.date(2026, 11, 30)  # a Monday
    assert not cal.weeks[0][0].in_month
    assert (cal.previous, cal.next) == (
        datetime.date(2026, 11, 1),
        datetime.date(2027, 1, 1),
    )
    # This month has no way back; past days are shown but can't be planned.
    october = month.build_month(crew.sam, datetime.date(2026, 10, 11))
    assert october.previous is None
    days = days_of(october)
    assert not days[datetime.date(2026, 10, 10)].plannable
    assert days[datetime.date(2026, 10, 11)].is_today
    # A month past the horizon is pulled back to the last plannable one.
    last = month.build_month(crew.sam, datetime.date(2030, 1, 1))
    assert last.first == plans.last_plannable_day().replace(day=1)
    assert last.next is None
    assert month.month_start(datetime.date(2020, 5, 5)) == datetime.date(2026, 10, 1)


@freeze_time("2026-10-11 09:00:00+02:00")
def test_month_day_shows_plan_and_group_activity(crew: Crew) -> None:
    day = datetime.date(2026, 12, 20)
    plans.set_plan(crew.sam, day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.anna, day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, day, S.YES, resort=crew.zermatt)
    # People outside the group don't count.
    plans.set_plan(crew.outsider, day, S.YES, resort=crew.verbier)

    entry = days_of(month.build_month(crew.sam, day))[day]
    assert entry.plan is not None and entry.plan.resort == crew.verbier
    assert entry.friends == ["Anna", "Ben"]
    assert entry.friends_out == 2
    assert entry.with_me == 1
    assert entry.summary == (
        "Sunday 20 December, Verbier, friends at resorts: Anna and Ben, 1 with you"
    )


@freeze_time("2026-10-11 09:00:00+02:00")
def test_month_day_summary_for_quiet_days(crew: Crew) -> None:
    today = datetime.date(2026, 10, 11)
    plans.set_plan(crew.sam, today, S.NO)
    days = days_of(month.build_month(crew.sam, today))
    assert days[today].summary == "Sunday 11 October, today, Not skiing"
    assert days[datetime.date(2026, 10, 12)].summary == "Monday 12 October, no plan"


@pytest.mark.parametrize(
    ("skiing", "at_resort", "words"),
    [
        (S.YES, True, "Skiing at Verbier"),
        (S.YES, False, "Skiing, not sure where"),
        (S.NO, True, "At Verbier, not skiing"),
        (S.NO, False, "Not skiing"),
    ],
)
def test_month_day_plan_words(
    crew: Crew, skiing: str, at_resort: bool, words: str
) -> None:
    plan = plans.set_plan(
        crew.sam, crew.day, skiing, resort=crew.verbier if at_resort else None
    )
    day = month.MonthDay(
        date=crew.day, in_month=True, is_today=False, plannable=True, plan=plan
    )
    assert day.plan_words == words
    assert (
        month.MonthDay(
            date=crew.day, in_month=True, is_today=False, plannable=True
        ).plan_words
        == ""
    )


def test_month_day_count_is_friends_with_you_or_at_the_highlight(crew: Crew) -> None:
    day = month.MonthDay(
        date=crew.day, in_month=True, is_today=False, plannable=True, with_me=2
    )
    assert day.count == 2
    day.highlight = "Verbier"
    day.there = ["Anna"]
    assert day.count == 1
