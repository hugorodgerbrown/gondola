"""Tests for one resort highlighted on My days (services/highlight.py, month.py)."""

import datetime

import pytest
from freezegun import freeze_time

from apps.groups.models import PlanDay
from apps.groups.services import highlight, month, plans
from tests.factories import ResortFactory, UserFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Skiing
DEC = month.month_dates(datetime.date(2026, 12, 1))


def dec(day: int) -> datetime.date:
    """Return a December 2026 date."""
    return datetime.date(2026, 12, day)


def test_month_dates_is_the_whole_month() -> None:
    assert DEC[0] == dec(1) and DEC[-1] == dec(31) and len(DEC) == 31
    assert len(month.month_dates(datetime.date(2027, 2, 1))) == 28


@freeze_time("2026-10-11 09:00:00+02:00")
def test_resorts_in_play_are_busiest_first(crew: Crew) -> None:
    plans.set_plan(crew.sam, dec(5), S.YES, resort=crew.zermatt)
    for day in (5, 6):
        plans.set_plan(crew.anna, dec(day), S.YES, resort=crew.verbier)
    # Private, outsider and no-resort days put nothing in play.
    lone = UserFactory.create(display_name="Lone")
    hidden = ResortFactory.create(name="Hidden", code="HIDE")
    plans.set_plan(crew.ben, dec(7), S.YES, resort=hidden, is_private=True)
    plans.set_plan(lone, dec(7), S.YES, resort=hidden)
    plans.set_plan(crew.ben, dec(8), S.YES)
    assert highlight.resorts_in_play(crew.sam, DEC) == [crew.verbier, crew.zermatt]


@freeze_time("2026-10-11 09:00:00+02:00")
def test_month_days_pick_out_the_highlighted_resort(crew: Crew) -> None:
    plans.set_plan(crew.sam, dec(5), S.YES, resort=crew.verbier)
    plans.set_plan(crew.anna, dec(5), S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, dec(5), S.YES, resort=crew.zermatt)
    plans.set_plan(crew.sam, dec(6), S.YES, resort=crew.zermatt)
    plans.set_plan(crew.ben, dec(7), S.NO, resort=crew.verbier)

    days = {
        d.date: d
        for week in month.build_month(crew.sam, dec(1), crew.verbier).weeks
        for d in week
    }
    assert (days[dec(5)].there, days[dec(5)].me_there, days[dec(5)].lit) == (
        ["Anna"],
        True,
        True,
    )
    assert not days[dec(6)].lit
    assert days[dec(7)].lit and days[dec(7)].there == ["Ben"]
    assert days[dec(7)].summary.endswith("at Verbier: Ben")
    # Without a highlight, nothing is lit.
    plain = month.build_month(crew.sam, dec(1))
    assert not any(d.lit for week in plain.weeks for d in week)
