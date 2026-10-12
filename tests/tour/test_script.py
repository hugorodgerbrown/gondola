"""Tests for apps/tour/script.py: the script as data matches the locked doc."""

from __future__ import annotations

import pytest
from django.conf import settings

from apps.resorts.models import Resort
from apps.tour.demo import demo_week
from apps.tour.script import (
    CHAPTERS,
    HANDOFF,
    WELCOME,
    WELCOME_TITLE,
    chapters_for,
    frame_count,
)

DOC = (settings.BASE_DIR / "docs" / "onboarding-tour.md").read_text()


def test_the_tour_has_twenty_five_frames() -> None:
    assert frame_count() == 25


@pytest.mark.parametrize(
    "frame", [f for c in CHAPTERS for f in c.frames], ids=lambda f: f.id
)
def test_every_coach_mark_is_the_locked_copy(frame: object) -> None:
    assert f"| {frame.id} |" in DOC  # type: ignore[attr-defined]
    assert frame.text in DOC  # type: ignore[attr-defined]


def test_welcome_and_handoff_are_the_locked_copy() -> None:
    assert f"{WELCOME_TITLE} {WELCOME}" in DOC
    assert HANDOFF in DOC


def test_every_chapter_opens_with_an_intro_and_numbers_its_frames() -> None:
    for chapter in CHAPTERS:
        assert chapter.frames[0].target == ()
        ids = [frame.id for frame in chapter.frames]
        assert ids == [f"{chapter.number}.{n}" for n in range(len(ids))]


def test_only_the_last_frame_finishes() -> None:
    finishing = [f.id for c in CHAPTERS for f in c.frames if f.finish]
    assert finishing == ["5.5"]


@pytest.mark.django_db
def test_chapters_for_a_page_fill_in_the_demo_week(
    resorts: dict[str, Resort],
) -> None:
    week = demo_week()
    played = chapters_for("calendar", week)
    assert [c["number"] for c in played] == [1, 2]
    tap = played[0]["frames"][-1]["tap"]  # type: ignore[index]
    assert tap == "#day-panel [data-day-plan]"
    pins = chapters_for("map", week)[0]["frames"][-2]["tap"]  # type: ignore[index]
    assert str(resorts["VERB"].uuid) in pins
    assert chapters_for("account", week) == []
