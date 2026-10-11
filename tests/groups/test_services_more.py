"""Tests for apps/groups/services/ (meetups, map, evening)."""

import datetime

import pytest
from django.core import mail

from apps.groups.models import MeetUp, PlanDay
from apps.groups.services import evening, meetups, plans, resort_map
from apps.groups.services.meetups import MeetUpError
from apps.groups.services.memberships import create_group, join_group
from tests.factories import PassFactory, ResortFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Status


# --- meetups --------------------------------------------------------------------


def test_propose_sets_organiser_day(crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, S.RESORT, resort=crew.verbier, note="kids")
    meetup = meetups.propose_meetup(
        crew.group, crew.sam, crew.day, crew.verbier, start_time=datetime.time(9)
    )
    assert meetups.is_going(meetup, crew.sam)
    plan = PlanDay.objects.get(user=crew.sam, date=crew.day)
    assert plan.resort == crew.verbier and plan.note == "kids"


def test_propose_refuses_bad_input(crew: Crew) -> None:
    past = plans.today() - datetime.timedelta(days=1)
    with pytest.raises(MeetUpError, match="later day"):
        meetups.propose_meetup(crew.group, crew.sam, past, crew.verbier)
    with pytest.raises(MeetUpError, match="both"):
        meetups.propose_meetup(
            crew.group, crew.sam, crew.day, crew.verbier, latitude=46.0
        )


def test_join_meetup_adds_to_group_and_sets_day(crew: Crew) -> None:
    plans.set_plan(crew.outsider, crew.day, S.RESORT, resort=crew.zermatt, note="x")
    meetup = meetups.propose_meetup(crew.group, crew.sam, crew.day, crew.verbier)
    assert meetups.join_meetup(meetup, crew.outsider) is True
    assert meetups.join_meetup(meetup, crew.outsider) is False
    plan = PlanDay.objects.get(user=crew.outsider, date=crew.day)
    assert plan.resort == crew.verbier and plan.note == ""


def test_passed_meetup_is_closed(crew: Crew) -> None:
    meetup = meetups.propose_meetup(crew.group, crew.sam, crew.day, crew.verbier)
    MeetUp.objects.filter(pk=meetup.pk).update(
        date=plans.today() - datetime.timedelta(days=1)
    )
    meetup.refresh_from_db()
    assert not meetups.is_open(meetup)
    with pytest.raises(MeetUpError, match="passed"):
        meetups.join_meetup(meetup, crew.anna)


def test_leave_and_cancel(crew: Crew) -> None:
    meetup = meetups.propose_meetup(crew.group, crew.anna, crew.day, crew.verbier)
    meetups.join_meetup(meetup, crew.ben)
    with pytest.raises(MeetUpError, match="Cancel it instead"):
        meetups.leave_meetup(meetup, crew.anna)
    meetups.leave_meetup(meetup, crew.ben)
    assert not meetups.is_going(meetup, crew.ben)
    with pytest.raises(MeetUpError, match="Only the organiser"):
        meetups.cancel_meetup(meetup, crew.ben)
    assert meetups.can_cancel(meetup, crew.sam)  # the group owner
    meetups.cancel_meetup(meetup, crew.sam)
    assert not MeetUp.objects.exists()


# --- map ----------------------------------------------------------------------


def test_map_pins_and_pass_filter(crew: Crew) -> None:
    magic = PassFactory.create(slug="magic-pass")
    crew.verbier.passes.add(magic)
    hidden = ResortFactory.create(name="Unplaced", latitude=None, longitude=None)
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.zermatt)
    plans.set_plan(crew.sam, crew.day, S.RESORT, resort=crew.verbier)
    meetups.propose_meetup(crew.group, crew.ben, crew.day, crew.zermatt)
    pins = {p["name"]: p for p in resort_map.map_pins(crew.sam, crew.day)}
    assert hidden.name not in pins
    assert pins["Zermatt"]["friends"] == 2 and pins["Zermatt"]["meetup"]
    assert pins["Verbier"]["mine"] and pins["Verbier"]["friends"] == 0
    other = ResortFactory.create(name="Elsewhere")
    on_pass = {p["name"] for p in resort_map.map_pins(crew.sam, crew.day, "magic-pass")}
    assert on_pass == {"Verbier", "Zermatt"}  # Zermatt kept: friends are there
    assert other.name not in on_pass


def test_resort_day(crew: Crew) -> None:
    second = create_group(crew.anna, "Uni friends")
    join_group(second, crew.sam)
    plans.set_plan(
        crew.anna, crew.day, S.RESORT, resort=crew.verbier, note="first lift"
    )
    plans.set_plan(crew.ben, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.sam, crew.day, S.NOT_SURE)
    meetups.propose_meetup(crew.group, crew.ben, crew.day, crew.verbier)
    info = resort_map.resort_day(crew.sam, crew.verbier, crew.day)
    assert [g.group.name for g in info.groups] == ["Thursday crew", "Uni friends"]
    assert info.friend_count == 2
    assert info.my_plan is not None and info.my_plan.status == S.NOT_SURE
    assert len(info.meetups) == 1


# --- evening email ----------------------------------------------------------------


def test_digest_and_send(crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, S.RESORT, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.RESORT, resort=crew.zermatt)
    meetup = meetups.propose_meetup(crew.group, crew.anna, crew.day, crew.verbier)
    assert crew.sam in evening.recipients(crew.day)
    digest = evening.build_digest(crew.sam, crew.day)
    assert not digest.is_empty
    assert digest.subject == "Tomorrow: meet-up at Verbier, 1 going"
    lines = {line.resort_name: line.people for line in digest.groups[0].lines}
    assert lines == {"Verbier": "Anna and you", "Zermatt": "Ben"}
    assert not digest.meetups[0].is_going
    evening.send_digest(digest)
    sent = mail.outbox[0]
    assert sent.to == [crew.sam.email]
    assert meetup.share_token in sent.body
    assert "/email/stop/" in sent.body


def test_digest_without_news(crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, S.NOT_SKIING)
    digest = evening.build_digest(crew.sam, crew.day)
    assert digest.is_empty
    assert digest.subject == "Tomorrow: who's where"


def test_recipients_respect_opt_out(crew: Crew) -> None:
    crew.sam.evening_email_enabled = False
    crew.sam.save()
    plans.set_plan(crew.sam, crew.day, S.NOT_SURE)
    meetups.propose_meetup(crew.group, crew.anna, crew.day, crew.verbier)
    assert set(evening.recipients(crew.day)) == {crew.anna, crew.ben}
