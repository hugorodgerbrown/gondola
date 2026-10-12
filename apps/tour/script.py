"""
apps/tour/script.py — The tour's words, and what each frame points at.

The locked script lives in docs/onboarding-tour.md; this is it as data, so
``static/js/tour.js`` can play it and the tests can hold it to the doc.
Each chapter belongs to one or more pages (URL names). Every chapter opens
with a page intro (a card over the dimmed page, no target), zooms into one
element at a time (Next moves on), and most end on a real tap: ``tap`` is
the control the person taps, which leads to the next page.

``target`` lists CSS selectors to spotlight; with several, the spotlight
covers them all. ``{start}`` and ``{resort}`` are filled
in from the demo week, so a frame points at the demo's own days.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .demo import DemoWeek

# Shown under the coach mark of a frame whose tap would save something.
NOTHING_SAVED = "In the demo, {action} keeps nothing."


@dataclass(frozen=True)
class Frame:
    """One step: a coach mark, what it spotlights, and how it moves on."""

    id: str
    text: str
    target: tuple[str, ...] = ()
    tap: str = ""
    note: str = ""
    # The last frame of the tour finishes it rather than moving to Next.
    finish: bool = False


@dataclass(frozen=True)
class Chapter:
    """One page of the tour, its intro and its frames."""

    number: int
    name: str
    pages: tuple[str, ...]
    frames: tuple[Frame, ...] = field(default_factory=tuple)


WELCOME_TITLE = "Welcome to Gondola!"
WELCOME = (
    "Gondola helps you and your friends see who's skiing "
    "where this winter, so meeting up is easy. Let's take a quick look "
    "round a demo group: it's made up, so tap anything. Nothing is saved."
)

HANDOFF = (
    "That's the tour. The demo group is gone. This is your real calendar: "
    "tap a day you might ski, then Add plans, and your group will see it. "
    "The evening before you ski, we'll email you who's where."
)

# What a quiet group's Tell the group button shares with the invite link.
TELL_THE_GROUP = "My ski days are on Gondola, add yours"

# The selected day's Add plans (or Edit plans) under the month.
PLAN_DAY = "#day-panel [data-day-plan]"

CHAPTERS: tuple[Chapter, ...] = (
    Chapter(
        1,
        "Your calendar",
        ("calendar",),
        (
            Frame(
                "1.0",
                "This is your calendar. Blue days are the days you're in a "
                "resort, and the people mark shows friends will be there too.",
            ),
            Frame(
                "1.1",
                "A pale day is one you haven't said: it shows where most of your "
                "friends will be.",
                (".mday--friends",),
            ),
            Frame(
                "1.2",
                "Tap and hold a day to start selecting, then tap more days. Plan "
                "sets them all at once.",
                (".month",),
            ),
            Frame(
                "1.3",
                "Tap a day to see it here: your plans, and where each friend will be.",
                ("#day-panel",),
            ),
            Frame(
                "1.4",
                "Add plans tells your groups where you'll be.",
                (PLAN_DAY,),
                tap=PLAN_DAY,
            ),
        ),
    ),
    Chapter(
        2,
        "A single day",
        ("calendar", "day"),
        (
            Frame(
                "2.0",
                "Planning a day. Here you tell your groups where you'll be. "
                "We show you where your friends are going first.",
            ),
            Frame(
                "2.1",
                "We show you where friends will be that day. Tap one to join them.",
                ("[data-day-form] .choices",),
            ),
            Frame(
                "2.2",
                "Somewhere else? Look up any resort.",
                ("[data-day-form] #resort-search",),
            ),
            Frame(
                "2.3",
                "Save shares the day with your groups.",
                ("[data-day-form] button[type=submit]",),
                tap="[data-day-form] button[type=submit]",
                note=NOTHING_SAVED.format(action="Save"),
            ),
        ),
    ),
    Chapter(
        3,
        "Your group",
        ("group_detail",),
        (
            Frame(
                "3.0",
                "This is your group. Everyone in it sees each other's names and "
                "days. Invite friends here, and see the whole group's week in "
                "Who's where.",
            ),
            Frame(
                "3.1",
                "Share this link in your group chat. Friends join with one tap.",
                ("section[aria-labelledby=invite-heading]",),
            ),
            Frame(
                "3.2",
                "Everyone who's joined. They see your days, and you see theirs.",
                ("section[aria-labelledby=members-heading]",),
            ),
            Frame(
                "3.3",
                "Tap Who's where to see the group's week.",
                ("[data-tour=board-tile]",),
                tap="[data-tour=board-tile]",
            ),
        ),
    ),
    Chapter(
        4,
        "Who's where",
        ("board",),
        (
            Frame(
                "4.0",
                "The group's week at a glance. Everyone side by side, so you can "
                "see who overlaps where.",
            ),
            Frame(
                "4.1",
                "Each code is a resort: VER is Verbier. Blank hasn't said.",
                (".board",),
            ),
            Frame(
                "4.2",
                "Tap Map to see where your friends are on any day.",
                ('.tabbar a[href$="/map/"]',),
                tap='.tabbar a[href$="/map/"]',
            ),
        ),
    ),
    Chapter(
        5,
        "The map",
        ("map",),
        (
            Frame(
                "5.0",
                "The map shows where your friends are skiing, on any day you "
                "pick. It's where you'll land each time you open Gondola.",
            ),
            Frame(
                "5.1",
                "Change the day with the arrows, or tap the date for a calendar.",
                (".map-bar nav.float",),
            ),
            Frame(
                "5.2",
                "The number on a resort is how many friends are there that day.",
                ('.pin[data-resort="{resort}"] .pin__dot',),
            ),
            Frame(
                "5.3",
                "Show only the resorts on your pass.",
                ("nav.chips",),
            ),
            Frame(
                "5.4",
                "Tap a resort to see who's there.",
                ('.pin[data-resort="{resort}"]',),
                tap='.pin[data-resort="{resort}"]',
            ),
            Frame(
                "5.5",
                "Say you'll be here without leaving the map.",
                ("#sheet [data-tour=resort-actions]",),
                finish=True,
            ),
        ),
    ),
)


def _fill(text: str, week: DemoWeek) -> str:
    """Fill a selector's placeholders from the demo week."""
    return text.format(
        start=week.start.isoformat(),
        resort=week.resort.uuid,
    )


def chapters_for(page: str, week: DemoWeek) -> list[dict[str, object]]:
    """Return the chapters played on ``page`` (a URL name), as plain data."""
    played = []
    for chapter in CHAPTERS:
        if page not in chapter.pages:
            continue
        frames = []
        for frame in chapter.frames:
            data = asdict(frame)
            data["target"] = [_fill(s, week) for s in frame.target]
            data["tap"] = _fill(frame.tap, week)
            frames.append(data)
        played.append(
            {"number": chapter.number, "name": chapter.name, "frames": frames}
        )
    return played


def frame_count() -> int:
    """Return how many frames the tour has, the welcome and hand-off included."""
    return sum(len(chapter.frames) for chapter in CHAPTERS) + 2
