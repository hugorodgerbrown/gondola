"""Tests for a picked group's pale days: where its people are (month.py)."""

import datetime

import pytest
from freezegun import freeze_time

from apps.groups.services import month, plans
from apps.groups.services.memberships import join_group
from tests.factories import ResortFactory, UserFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db


def dec(day: int) -> datetime.date:
    """Return a December 2026 date."""
    return datetime.date(2026, 12, day)


def test_month_dates_is_the_whole_month() -> None:
    days = month.month_dates(dec(1))
    assert days[0] == dec(1) and days[-1] == dec(31) and len(days) == 31
    assert len(month.month_dates(datetime.date(2027, 2, 1))) == 28


@freeze_time("2026-10-11 09:00:00+02:00")
def test_an_unsaid_day_shows_where_most_friends_are(crew: Crew) -> None:
    chloe = UserFactory.create(display_name="Chloé")
    join_group(crew.group, chloe)
    # 5th: two in Zermatt beat one in Verbier.
    plans.set_plan(crew.anna, dec(5), crew.zermatt)
    plans.set_plan(chloe, dec(5), crew.zermatt)
    plans.set_plan(crew.ben, dec(5), crew.verbier)
    # 6th: a tie goes to the resort first by name.
    plans.set_plan(crew.anna, dec(6), crew.zermatt)
    plans.set_plan(crew.ben, dec(6), crew.verbier)
    # 7th: Sam has said, so no crowd, whatever friends do.
    plans.set_plan(crew.sam, dec(7), crew.verbier)
    plans.set_plan(crew.anna, dec(7), crew.zermatt)
    # Outsiders count for nothing.
    lone = UserFactory.create(display_name="Lone")
    plans.set_plan(lone, dec(8), ResortFactory.create(name="Hidden", code="HIDE"))

    # Just me shows no pale days at all.
    plain = month.build_month(crew.sam, dec(1)).weeks
    assert not any(d.crowd for week in plain for d in week)
    days = {
        d.date: d
        for week in month.build_month(crew.sam, dec(1), crew.group).weeks
        for d in week
    }
    crowd = days[dec(5)].crowd
    assert crowd is not None and crowd.resort == crew.zermatt
    assert crowd.names == "Anna and Chloé"
    assert days[dec(5)].count == 2 and days[dec(5)].more == 1
    assert days[dec(5)].summary.endswith("Anna and Chloé, others elsewhere")
    tie = days[dec(6)].crowd
    assert tie is not None and tie.resort == crew.verbier
    assert days[dec(7)].crowd is None and days[dec(7)].count == 0
    assert days[dec(8)].crowd is None
