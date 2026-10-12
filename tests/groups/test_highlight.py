"""Tests for one resort highlighted on the calendar (services/highlight.py, month.py)."""

import datetime

import pytest
from freezegun import freeze_time

from apps.groups.services import highlight, month, plans
from apps.resorts.models import Resort
from tests.factories import ResortFactory, UserFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
DEC = month.month_dates(datetime.date(2026, 12, 1))


def dec(day: int) -> datetime.date:
    """Return a December 2026 date."""
    return datetime.date(2026, 12, day)


@freeze_time("2026-10-11 09:00:00+02:00")
def test_resorts_in_play_are_where_friends_are(crew: Crew) -> None:
    # Your own days put nothing in play: the chips are where friends are.
    plans.set_plan(crew.sam, dec(4), crew.zermatt)
    plans.set_plan(crew.ben, dec(5), crew.zermatt)
    for day in (5, 6):
        plans.set_plan(crew.anna, dec(day), crew.verbier)
    # Outsiders' days put nothing in play.
    lone = UserFactory.create(display_name="Lone")
    hidden = ResortFactory.create(name="Hidden", code="HIDE")
    plans.set_plan(lone, dec(7), hidden)
    assert highlight.resorts_in_play(crew.sam, DEC) == [crew.verbier, crew.zermatt]


@freeze_time("2026-10-11 09:00:00+02:00")
def test_a_picked_resort_narrows_unsaid_days_only(crew: Crew) -> None:
    plans.set_plan(crew.sam, dec(5), crew.verbier)
    plans.set_plan(crew.anna, dec(5), crew.verbier)
    plans.set_plan(crew.ben, dec(5), crew.zermatt)
    plans.set_plan(crew.anna, dec(6), crew.zermatt)
    plans.set_plan(crew.ben, dec(6), crew.zermatt)
    plans.set_plan(crew.ben, dec(7), crew.verbier)

    def days(picked: Resort | None) -> dict[datetime.date, month.MonthDay]:
        """Return December's days for Sam, with ``picked`` highlighted."""
        weeks = month.build_month(crew.sam, dec(1), picked).weeks
        return {d.date: d for week in weeks for d in week}

    busiest = days(None)[dec(6)].crowd
    assert busiest is not None and busiest.resort == crew.zermatt
    lit = days(crew.verbier)
    # Your own day is untouched: Anna is still with you.
    assert lit[dec(5)].crowd is None and lit[dec(5)].count == 1
    # Nobody is at Verbier on the 6th, so it shows nothing.
    assert lit[dec(6)].crowd is None and lit[dec(6)].count == 0
    crowd = lit[dec(7)].crowd
    assert crowd is not None and crowd.names == "Ben"
    assert lit[dec(7)].summary.endswith("most at Verbier: Ben")
