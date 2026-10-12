"""Tests for apps/groups/services/ (map, evening)."""

import pytest
from django.core import mail

from apps.groups.models import PlanDay
from apps.groups.services import evening, plans, resort_map
from apps.groups.services.memberships import create_group, join_group
from tests.factories import PassFactory, ResortFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Skiing


# --- map ----------------------------------------------------------------------


def test_map_pins_and_pass_filter(crew: Crew) -> None:
    magic = PassFactory.create(slug="magic-pass")
    crew.verbier.passes.add(magic)
    hidden = ResortFactory.create(name="Unplaced", latitude=None, longitude=None)
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.zermatt)
    plans.set_plan(crew.sam, crew.day, S.YES, resort=crew.verbier)
    pins = {p["name"]: p for p in resort_map.map_pins(crew.sam, crew.day)}
    assert hidden.name not in pins
    assert pins["Zermatt"]["friends"] == 1 and "meetup" not in pins["Zermatt"]
    assert pins["Verbier"]["mine"] and pins["Verbier"]["friends"] == 0
    assert pins["Verbier"]["passes"] == ["magic-pass"]
    assert pins["Zermatt"]["passes"] == []
    other = ResortFactory.create(name="Elsewhere")
    on_pass = {p["name"] for p in resort_map.map_pins(crew.sam, crew.day, "magic-pass")}
    assert on_pass == {"Verbier", "Zermatt"}  # Zermatt kept: friends are there
    assert other.name not in on_pass


def test_resort_day(crew: Crew) -> None:
    second = create_group(crew.anna, "Uni friends")
    join_group(second, crew.sam)
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier, note="first lift")
    plans.set_plan(crew.ben, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.sam, crew.day, S.NO, resort=crew.zermatt)
    info = resort_map.resort_day(crew.sam, crew.verbier, crew.day)
    assert [g.group.name for g in info.groups] == ["Thursday crew", "Uni friends"]
    assert info.friend_count == 2
    assert info.my_plan is not None and info.my_plan.skiing == S.NO


# --- evening email ----------------------------------------------------------------


def test_digest_and_send(crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, S.YES, resort=crew.verbier, is_private=True)
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier)
    plans.set_plan(crew.ben, crew.day, S.NO, resort=crew.zermatt)
    assert crew.sam in evening.recipients(crew.day)
    digest = evening.build_digest(crew.sam, crew.day)
    assert not digest.is_empty
    assert digest.subject == "Tomorrow: who's where"
    lines = {line.resort_name: line.people for line in digest.groups[0].lines}
    assert lines == {"Verbier": "Anna and you", "Zermatt": "Ben (around)"}
    evening.send_digest(digest)
    sent = mail.outbox[0]
    assert sent.to == [crew.sam.email]
    assert "Anna and you" in sent.body
    assert "/email/stop/" in sent.body


def test_digest_without_news(crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, S.NO)
    digest = evening.build_digest(crew.sam, crew.day)
    assert digest.is_empty
    assert digest.subject == "Tomorrow: who's where"


def test_recipients_respect_opt_out(crew: Crew) -> None:
    crew.sam.evening_email_enabled = False
    crew.sam.save()
    plans.set_plan(crew.sam, crew.day, S.NO, resort=crew.zermatt)
    plans.set_plan(crew.anna, crew.day, S.YES, resort=crew.verbier)
    assert set(evening.recipients(crew.day)) == {crew.anna}


def test_resort_index_lists_placed_resorts(crew: Crew) -> None:
    ResortFactory.create(name="Unplaced", latitude=None, longitude=None)
    index = {r["name"]: r for r in resort_map.resort_index()}
    assert "Unplaced" not in index
    assert index["Verbier"]["id"] == str(crew.verbier.uuid)
    assert index["Verbier"]["lat"] == crew.verbier.latitude
