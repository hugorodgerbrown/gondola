"""Tests for the send_evening_emails, seed_demo and seed_ui_test commands."""

import datetime
from io import StringIO
from unittest import mock

import pytest
from django.core import mail
from django.core.management import CommandError, call_command
from freezegun import freeze_time

from apps.groups.management.commands.seed_demo import demo_start
from apps.groups.management.commands.seed_ui_test import UNSAID
from apps.groups.models import Group, PlanDay
from apps.groups.services import plans
from apps.groups.services.people import is_member
from apps.groups.services.testers import get_testers_group
from apps.resorts.services import import_sheets
from tests.factories import UserFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db


def _tomorrow_plans(crew: Crew) -> datetime.date:
    tomorrow = plans.today() + datetime.timedelta(days=1)
    plans.set_plan(crew.sam, tomorrow, crew.verbier)
    plans.set_plan(crew.anna, tomorrow, crew.verbier)
    plans.set_plan(crew.ben, tomorrow, crew.zermatt)
    return tomorrow


def test_dry_run_sends_nothing(crew: Crew) -> None:
    _tomorrow_plans(crew)
    out = StringIO()
    call_command("send_evening_emails", "-v", "2", stdout=out)
    assert mail.outbox == []
    assert "Would send 3 evening emails" in out.getvalue()
    assert "Dry run" in out.getvalue()


def test_commit_sends(crew: Crew) -> None:
    _tomorrow_plans(crew)
    out = StringIO()
    call_command("send_evening_emails", "--commit", stdout=out)
    assert {m.to[0] for m in mail.outbox} == {
        crew.sam.email,
        crew.anna.email,
        crew.ben.email,
    }
    assert "Sent 3" in out.getvalue()


def test_nothing_new_is_skipped(crew: Crew) -> None:
    day = plans.today() + datetime.timedelta(days=5)
    plans.set_plan(crew.sam, day, crew.zermatt)
    out = StringIO()
    call_command(
        "send_evening_emails",
        "--commit",
        "--date",
        day.isoformat(),
        "-v",
        "2",
        stdout=out,
    )
    assert mail.outbox == []
    assert "nothing new" in out.getvalue()


def test_failure_exits_non_zero(crew: Crew) -> None:
    _tomorrow_plans(crew)
    with (
        mock.patch(
            "apps.groups.management.commands.send_evening_emails.send_digest",
            side_effect=OSError("smtp down"),
        ),
        pytest.raises(CommandError, match="3 evening emails failed"),
    ):
        call_command("send_evening_emails", "--commit", stdout=StringIO())


def test_seed_demo_needs_resorts() -> None:
    with pytest.raises(CommandError, match="import_resorts"):
        call_command("seed_demo", stdout=StringIO())


def test_seed_demo_dry_run_then_commit_twice() -> None:
    import_sheets(commit=True)
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert "Dry run" in out.getvalue()
    assert not Group.objects.exists()
    call_command("seed_demo", "--commit", "--email", "Me@Example.com", stdout=StringIO())
    call_command("seed_demo", "--commit", "--email", "me@example.com", stdout=StringIO())
    group = Group.objects.get()
    assert group.owner.email == "me@example.com"
    assert group.memberships.count() == 6
    assert PlanDay.objects.filter(user=group.owner).exists()


@freeze_time("2026-10-12 09:00:00+02:00")
def test_seed_demo_lands_in_january() -> None:
    import_sheets(commit=True)
    out = StringIO()
    call_command("seed_demo", "--commit", stdout=out)
    days = sorted({plan.date for plan in PlanDay.objects.all()})
    assert days[0] == datetime.date(2027, 1, 9)  # a Saturday
    assert days[-1] <= datetime.date(2027, 1, 15)
    assert "Sat 09 Jan 2027" in out.getvalue()
    assert "?start=2027-01-09" in out.getvalue()


def test_demo_start_is_mid_january_or_today_in_season() -> None:
    assert demo_start(datetime.date(2026, 10, 12)) == datetime.date(2027, 1, 9)
    assert demo_start(datetime.date(2027, 5, 1)) == datetime.date(2028, 1, 15)
    # In season, today.
    for day in (datetime.date(2026, 12, 20), datetime.date(2027, 4, 30)):
        assert demo_start(day) == day


@freeze_time("2026-10-12 09:00:00+02:00")
def test_seed_demo_start_option() -> None:
    import_sheets(commit=True)
    call_command("seed_demo", "--commit", "--start", "2026-12-26", stdout=StringIO())
    assert min(p.date for p in PlanDay.objects.all()) == datetime.date(2026, 12, 26)
    with pytest.raises(CommandError, match="YYYY-MM-DD"):
        call_command("seed_demo", "--start", "soon", stdout=StringIO())
    with pytest.raises(CommandError, match="can't be planned"):
        call_command("seed_demo", "--start", "2026-01-01", stdout=StringIO())


def test_seed_ui_test_needs_resorts() -> None:
    with pytest.raises(CommandError, match="import_resorts"):
        call_command("seed_ui_test", stdout=StringIO())


def test_seed_ui_test_dry_run_prints_the_cases() -> None:
    import_sheets(commit=True)
    out = StringIO()
    call_command("seed_ui_test", stdout=out)
    assert "Dry run" in out.getvalue()
    assert "Alone, four days" in out.getvalue()
    assert "Unsaid, friends out" in out.getvalue()
    assert not Group.objects.exists()
    quiet = StringIO()
    call_command("seed_ui_test", "-v", "0", stdout=quiet)
    assert quiet.getvalue() == ""


def test_seed_ui_test_covers_every_case_and_reruns() -> None:
    import_sheets(commit=True)
    me = UserFactory.create()
    me.groups.add(get_testers_group())
    out = StringIO()
    for _ in range(2):
        call_command("seed_ui_test", "--commit", stdout=out)
    assert "Real accounts in Testers: 1" in out.getvalue()
    group = Group.objects.get(name="UI test")
    tester = group.owner
    assert tester.email == "tess@ui-test.invalid"
    # The five made up, plus the real account already in Testers.
    assert group.memberships.count() == 6
    assert is_member(group, me)
    assert get_testers_group().user_set.count() == 6
    mine = PlanDay.objects.filter(user=tester)
    assert mine.exists()
    # Nothing from the tester on the unsaid day, but friends out.
    unsaid = plans.today() + datetime.timedelta(days=UNSAID)
    assert not mine.filter(date=unsaid).exists()
    assert PlanDay.objects.filter(date=unsaid).exists()
    # Some run crosses a month end.
    months = {
        (plan.date.year, plan.date.month)
        for plan in mine.filter(
            resort__name="Champéry", date__gte=plans.today() + datetime.timedelta(40)
        )
    }
    assert len(months) == 2
