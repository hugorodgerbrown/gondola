"""
apps/tour/script.py — The tour's words, and what each frame points at.

The locked script lives in docs/onboarding-tour.md; this is it as data, so
``static/js/tour.js`` can play it and the tests can hold it to the doc.
Each chapter belongs to one or more pages (URL names). Every chapter opens
with a page intro (a card over the dimmed page, no target), zooms into one
element at a time (Next moves on), and most end on a real tap: ``tap`` is
the control the person taps, which leads to the next page.

``target`` lists CSS selectors to spotlight; with several, the spotlight
covers them all. ``{start}``, ``{meetup_day}`` and ``{resort}`` are filled
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
    "where this winter, and pick a place to meet. Let's take a quick look "
    "round a demo group: it's made up, so tap anything. Nothing is saved."
)

HANDOFF = (
    "That's the tour. The demo group is gone. This is your real calendar: "
    "tap a day you might ski, and your group will see it. The evening before "
    "you ski, we'll email you who's where."
)

# What a quiet group's Tell the group button shares with the invite link.
TELL_THE_GROUP = "My ski days are on Gondola, add yours"

DAY = '.mday[data-date="{start}"]'

CHAPTERS: tuple[Chapter, ...] = (
    Chapter(
        1,
        "Your calendar",
        ("my_days",),
        (
            Frame(
                "1.0",
                "This is your calendar. It shows the days you're skiing, and how "
                "many of your friends are skiing each day.",
            ),
            Frame(
                "1.1",
                "The number on a day is how many friends are skiing it.",
                (DAY + " .mday__friends",),
            ),
            Frame(
                "1.2",
                "An amber dot means a meet-up is planned that day.",
                ('.mday[data-date="{meetup_day}"] .mday__meetup',),
            ),
            Frame(
                "1.3",
                "Tap a resort to light up the days your friends will be there.",
                ("nav.month-resorts",),
            ),
            Frame(
                "1.4",
                "Your own days show in blue: solid when you're skiing, dashed "
                "when you're not sure.",
                (".month-key",),
            ),
            Frame(
                "1.5",
                "Tap and hold a day to start selecting, then tap more days. Plan "
                "sets them all at once.",
                (".month",),
            ),
            Frame("1.6", "Tap a day to plan it.", (DAY,), tap=DAY),
        ),
    ),
    Chapter(
        2,
        "A single day",
        ("my_days", "day"),
        (
            Frame(
                "2.0",
                "Planning a day. Here you tell your groups where you'll be and "
                "whether you're skiing. We show you where your friends are "
                "going first.",
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
                "Tell everyone whether you're on the slopes. Not sure is fine. "
                "Not skiing means you'll be around, off the slopes.",
                ("[data-day-form] fieldset.field",),
            ),
            Frame(
                "2.4",
                'Add a note for your groups, like "first lift".',
                ("[data-day-form] [name=note]",),
            ),
            Frame(
                "2.5",
                "Keep a day to yourself: friends see nothing for it.",
                ("[data-day-form] label.check",),
            ),
            Frame(
                "2.6",
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
                "Each code is a resort: VERB is Verbier. ? is not sure, – is not "
                "skiing, blank hasn't said.",
                (".board",),
            ),
            Frame(
                "4.2",
                "A black box is a meet-up. Tap it for the time and meeting point.",
                ("a.board__meetup--set",),
            ),
            Frame(
                "4.3",
                "Tap + to propose a meet-up that day.",
                ("a.board__meetup--add",),
                tap="a.board__meetup--add",
            ),
        ),
    ),
    Chapter(
        5,
        "A meet-up",
        ("meetup_new",),
        (
            Frame(
                "5.0",
                "Proposing a meet-up. Gondola suggests where to meet, based on "
                "where everyone already is. Add a time and a meeting point if "
                "you like, then share it.",
            ),
            Frame(
                "5.1",
                "The best fit comes first: most friends already there, fewest moves.",
                (".choices .choice:first-child",),
            ),
            Frame(
                "5.2",
                "Prefer somewhere else? Pick any resort.",
                ("#resort-search",),
            ),
            Frame(
                "5.3",
                "Both optional. Tap the map to drop a meeting point.",
                ("[data-tour=meetup-time]", "[data-tour=meetup-propose]"),
                tap="[data-tour=meetup-propose]",
                note=NOTHING_SAVED.format(action="Propose"),
            ),
        ),
    ),
    Chapter(
        6,
        "The map",
        ("map",),
        (
            Frame(
                "6.0",
                "The map shows where your friends are skiing, on any day you "
                "pick. It's where you'll land each time you open Gondola.",
            ),
            Frame(
                "6.1",
                "Change the day with the arrows, or tap the date for a calendar.",
                (".map-bar nav.float",),
            ),
            Frame(
                "6.2",
                "The number on a resort is how many friends are there that day.",
                ('.pin[data-resort="{resort}"] .pin__dot',),
            ),
            Frame(
                "6.3",
                "Show only the resorts on your pass.",
                ("nav.chips",),
            ),
            Frame(
                "6.4",
                "Tap a resort to see who's there.",
                ('.pin[data-resort="{resort}"]',),
                tap='.pin[data-resort="{resort}"]',
            ),
            Frame(
                "6.5",
                "Say you'll be here, or propose a meet-up, without leaving the map.",
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
        meetup_day=week.meetup_day.isoformat(),
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
