"""Tests for the send_evening_emails, seed_demo and seed_ui_test commands."""

import datetime
from io import StringIO
from unittest import mock

import pytest
from django.core import mail
from django.core.management import CommandError, call_command

from apps.groups.management.commands.seed_ui_test import UNSAID
from apps.groups.models import Group, MeetUp, PlanDay
from apps.groups.services import plans
from apps.groups.services.people import is_member
from apps.groups.services.testers import get_testers_group
from apps.resorts.services import import_sheets
from tests.factories import UserFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Skiing


def _tomorrow_plans(crew: Crew) -> datetime.date:
    tomorrow = plans.today() + datetime.timedelta(days=1)
    plans.set_plan(crew.sam, tomorrow, S.YES, resort=crew.verbier)
    plans.set_plan(crew.anna, tomorrow, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, tomorrow, S.NO)
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
    plans.set_plan(crew.sam, day, S.NOT_SURE)
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
    with mock.patch(
        "apps.groups.management.commands.send_evening_emails.send_digest",
        side_effect=OSError("smtp down"),
    ):
        with pytest.raises(CommandError, match="3 evening emails failed"):
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
    call_command(
        "seed_demo", "--commit", "--email", "Me@Example.com", stdout=StringIO()
    )
    call_command(
        "seed_demo", "--commit", "--email", "me@example.com", stdout=StringIO()
    )
    group = Group.objects.get()
    assert group.owner.email == "me@example.com"
    assert group.memberships.count() == 6
    assert MeetUp.objects.get().participants.count() == 3
    assert PlanDay.objects.filter(skiing=S.NOT_SURE).exists()
    assert PlanDay.objects.filter(is_private=True).count() == 1


def test_seed_ui_test_needs_resorts() -> None:
    with pytest.raises(CommandError, match="import_resorts"):
        call_command("seed_ui_test", stdout=StringIO())


def test_seed_ui_test_dry_run_prints_the_cases() -> None:
    import_sheets(commit=True)
    out = StringIO()
    call_command("seed_ui_test", stdout=out)
    assert "Dry run" in out.getvalue()
    assert "No resort, not sure" in out.getvalue()
    assert "Unsaid, friends and a meet-up" in out.getvalue()
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
    assert MeetUp.objects.filter(group=group).count() == 3
    mine = PlanDay.objects.filter(user=tester)
    pairs = {(plan.resort_id is not None, plan.skiing) for plan in mine}
    assert pairs == {(at, s) for at in (True, False) for s in S.values}
    # Skiing with no resort, as a single day and a run.
    assert mine.filter(resort__isnull=True, skiing=S.YES).count() == 4
    assert mine.filter(is_private=True, resort__isnull=True).exists()
    assert mine.filter(is_private=True, resort__isnull=False).exists()
    assert mine.exclude(note="").count() == 2
    # Nothing from the tester on the unsaid day, but friends and a meet-up.
    unsaid = plans.today() + datetime.timedelta(days=UNSAID)
    assert not mine.filter(date=unsaid).exists()
    assert PlanDay.objects.filter(date=unsaid).exists()
    assert MeetUp.objects.filter(group=group, date=unsaid).exists()
    # Some run crosses a month end.
    months = {
        (plan.date.year, plan.date.month)
        for plan in mine.filter(resort__name="Champéry")
    }
    assert len(months) == 2
