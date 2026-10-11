"""Tests for the send_evening_emails and seed_demo commands."""

import datetime
from io import StringIO
from unittest import mock

import pytest
from django.core import mail
from django.core.management import CommandError, call_command

from apps.groups.models import Group, MeetUp, PlanDay
from apps.groups.services import plans
from apps.resorts.services import import_sheets
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Status


def _tomorrow_plans(crew: Crew) -> datetime.date:
    tomorrow = plans.today() + datetime.timedelta(days=1)
    plans.set_plan(crew.sam, tomorrow, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.anna, tomorrow, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.ben, tomorrow, S.NOT_SKIING)
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
    assert PlanDay.objects.filter(status=S.NOT_SURE).exists()
    assert PlanDay.objects.filter(is_private=True).count() == 1
