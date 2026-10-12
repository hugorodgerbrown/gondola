"""Tests for the calendar's month view: apps/groups/services/month.py."""

import datetime

import pytest
from freezegun import freeze_time

from apps.groups.models import PlanDay
from apps.groups.services import meetups, month, plans
from apps.groups.services.memberships import join_group
from tests.factories import UserFactory
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
    # Private days and people outside the group don't count.
    dana = UserFactory.create(display_name="Dana")
    join_group(crew.group, dana)
    plans.set_plan(dana, day, S.YES, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.outsider, day, S.YES, resort=crew.verbier)
    meetups.propose_meetup(crew.group, crew.anna, day, crew.verbier)

    entry = days_of(month.build_month(crew.sam, day))[day]
    assert entry.plan is not None and entry.plan.resort == crew.verbier
    assert entry.friends == ["Anna", "Ben"]
    assert entry.friends_out == 2
    assert entry.with_me == 1
    assert entry.meetup is not None and entry.meetup.resort == crew.verbier
    assert entry.summary == (
        "Sunday 20 December, Verbier, friends at resorts: Anna and Ben, 1 with you, "
        "meet-up at Verbier"
    )


@freeze_time("2026-10-11 09:00:00+02:00")
def test_month_day_summary_for_quiet_days(crew: Crew) -> None:
    today = datetime.date(2026, 10, 11)
    plans.set_plan(crew.sam, today, S.NOT_SURE, is_private=True)
    days = days_of(month.build_month(crew.sam, today))
    assert days[today].summary == "Sunday 11 October, today, Not sure yet, private"
    assert days[datetime.date(2026, 10, 12)].summary == "Monday 12 October, no plan"
