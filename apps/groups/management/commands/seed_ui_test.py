"""
apps/groups/management/commands/seed_ui_test.py — A group for testing the UI.

Makes "UI test" with a tester and four friends, and fills the tester's
next couple of months with every case the calendar, the day sheet, the map
and the board have to draw:

- each where × skiing pair (a resort or none; skiing, not sure, not
  skiing), as single days and as runs of days;
- days left unsaid, private days, days with a note (one long);
- a ten-day run in one resort with mixed skiing, a run that crosses a
  month end, and a private run;
- friends at your resort, friends elsewhere, a friend "around", a friend
  whose days are all private, and meet-ups on days you've planned and on
  one you haven't.

A bare run prints the plan, day by day, without writing; ``--commit``
writes it. Re-running rewrites everything from today, so the cases move
with the calendar. Needs the resorts imported first. ``--email`` makes that
address the tester, so you can sign in as them; the friends are
``*@ui-test.invalid`` accounts that can't receive email.
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts.models import User, normalise_email
from apps.groups.models import Group, MeetUp, PlanDay
from apps.groups.services.meetups import join_meetup, propose_meetup
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.plans import set_plan, today
from apps.resorts.models import Resort

GROUP_NAME = "UI test"
TESTER = "Tess"
FRIENDS = ["Anna", "Ben", "Chloé", "Dan"]
RESORTS = {
    "VERB": "Verbier",
    "SAASF": "Saas-Fee",
    "GRIME": "Grimentz",
    "CRA": "Crans-Montana",
    "CHAM": "Champéry",
}
# One letter a day for skiing: Y skiing, ? not sure, N not skiing.
SKIING = {"Y": PlanDay.Skiing.YES, "?": PlanDay.Skiing.NOT_SURE, "N": PlanDay.Skiing.NO}
# The day the tester says nothing about, while friends and a meet-up do.
UNSAID = 6
LONG_NOTE = (
    "Meeting the ski school at the Médran lift, then lunch at Chez Dany if "
    "the weather holds"
)


@dataclass(frozen=True)
class Run:
    """Some consecutive days a person said the same place about.

    ``skiing`` holds one letter per day, so a run can keep its resort while
    skiing changes. ``where`` is a resort code, or "" for no resort.
    """

    start: int
    skiing: str
    where: str = ""
    private: bool = False
    note: str = ""
    label: str = ""

    def days(self, first: datetime.date) -> list[datetime.date]:
        """Return the run's dates, counting ``start`` days from ``first``."""
        return [
            first + datetime.timedelta(days=self.start + n)
            for n in range(len(self.skiing))
        ]


def month_end_offset(first: datetime.date) -> int:
    """Return the offset of two days before the month end, 50+ days out.

    A run from there crosses into the next month, wherever today falls.
    """
    later = first + datetime.timedelta(days=50)
    last = calendar.monthrange(later.year, later.month)[1]
    return (later.replace(day=last) - first).days - 1


def tester_runs(first: datetime.date) -> list[Run]:
    """Return the tester's days, each labelled with the case it covers."""
    edge = month_end_offset(first)
    return [
        # Single days: every where × skiing pair, today first.
        Run(0, "Y", "VERB", label="At a resort, skiing (today)"),
        Run(1, "?", "VERB", label="At a resort, not sure"),
        Run(2, "N", "VERB", label="At a resort, not skiing (around)"),
        Run(3, "Y", label="No resort, skiing"),
        Run(4, "?", label="No resort, not sure"),
        Run(5, "N", label="No resort, not skiing"),
        # Offset UNSAID is left out: friends and a meet-up, nothing from you.
        Run(7, "Y", "VERB", private=True, label="At a resort, private"),
        Run(8, "N", private=True, label="No resort, private"),
        Run(9, "Y", "SAASF", note="First lift", label="Short note, meet-up"),
        Run(10, "?", "GRIME", note=LONG_NOTE, label="Long note"),
        # Runs.
        Run(14, "YY?NYYY?YN", "VERB", label="Ten days in one resort, mixed skiing"),
        Run(26, "YYYYY", "CRA", label="Five days alike"),
        Run(33, "NNNN", label="No resort, not skiing, four days"),
        Run(38, "???", label="No resort, not sure, three days"),
        Run(42, "YYY", "GRIME", private=True, label="Private run"),
        Run(45, "YYY", label="No resort, skiing, three days"),
        Run(edge, "YYYY", "CHAM", label="Run across a month end"),
    ]


def friend_runs() -> dict[str, list[Run]]:
    """Return what the friends said, offset from today."""
    return {
        # Often with you: the calendar's "friends with me" mark.
        "Anna": [
            Run(0, "YY", "VERB"),
            Run(3, "Y", "VERB"),
            Run(6, "Y", "SAASF"),
            Run(9, "Y", "SAASF"),
            Run(14, "YYYYYYYYYY", "VERB"),
            Run(26, "YYY", "CRA"),
        ],
        # Elsewhere: friends skiing, but not with you.
        "Ben": [
            Run(0, "Y", "SAASF"),
            Run(4, "YY", "CHAM"),
            Run(6, "Y", "SAASF"),
            Run(9, "Y", "SAASF"),
            Run(20, "??", "GRIME"),
        ],
        # Around: at your resort but not skiing, and unsure days with no resort.
        "Chloé": [
            Run(0, "N", "VERB"),
            Run(2, "N", "VERB"),
            Run(5, "??"),
            Run(16, "NNNN", "VERB"),
        ],
        # Everything private but one day: only that day should ever show.
        "Dan": [
            Run(0, "YYYYYYY", "VERB", private=True),
            Run(14, "YYYYY", "VERB", private=True),
            Run(26, "Y", "CRA"),
        ],
    }


# (offset, resort code, organiser, others going)
MEETUPS = [
    (UNSAID, "SAASF", "Ben", ["Anna"]),
    (9, "SAASF", "you", ["Anna", "Ben"]),
    (17, "VERB", "Anna", ["you"]),
]


class Command(BaseCommand):
    """Create or refresh the UI test group."""

    verbosity = 1

    help = (
        "Create a group whose tester covers every where/skiing case. "
        "Dry run unless --commit."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Add --commit and --email."""
        parser.add_argument("--commit", action="store_true", help="Write the data.")
        parser.add_argument(
            "--email",
            default="tester@ui-test.invalid",
            help="The tester's email: use one you can sign in with.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Seed the group, or print what would be seeded."""
        resorts = {r.name: r for r in Resort.objects.filter(name__in=RESORTS.values())}
        missing = set(RESORTS.values()) - set(resorts)
        if missing:
            raise CommandError(
                f"Missing resorts {sorted(missing)}: run import_resorts --commit first."
            )
        self.verbosity = options["verbosity"]
        email = normalise_email(options["email"])
        first = today()
        runs = tester_runs(first)
        self._legend(runs, first)
        if not options["commit"]:
            if self.verbosity >= 1:
                self.stdout.write(
                    f"Would create {GROUP_NAME} with {email} as the tester and "
                    f"{len(FRIENDS)} friends. Dry run. Re-run with --commit to save."
                )
            return
        by_code = {code: resorts[name] for code, name in RESORTS.items()}
        with transaction.atomic():
            self._seed(email, first, runs, by_code)
        if self.verbosity >= 1:
            self.stdout.write(f"Seeded {GROUP_NAME}. Sign in as {email} to see it.")

    def _legend(self, runs: list[Run], first: datetime.date) -> None:
        """Print each of the tester's days and the case it covers."""
        if self.verbosity < 1:
            return
        unsaid = first + datetime.timedelta(days=UNSAID)
        lines = [(unsaid, f"{unsaid:%a %d %b}", "Unsaid, friends and a meet-up")]
        for run in runs:
            days = run.days(first)
            span = f"{days[0]:%a %d %b}"
            if len(days) > 1:
                span += f" to {days[-1]:%a %d %b}"
            lines.append((days[0], span, run.label))
        for _, span, label in sorted(lines):
            self.stdout.write(f"{span:<24} {label}")

    def _person(self, email: str, name: str) -> User:
        """Return the user for ``email``, creating them if needed."""
        user, created = User.objects.get_or_create(
            email=email, defaults={"display_name": name}
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user

    def _seed(
        self,
        email: str,
        first: datetime.date,
        runs: list[Run],
        resorts: dict[str, Resort],
    ) -> None:
        """Write the people, the group, the meet-ups and every plan."""
        tester = self._person(email, TESTER)
        people = {"you": tester}
        for name in FRIENDS:
            slug = name.lower().replace("é", "e")
            people[name] = self._person(f"{slug}@ui-test.invalid", name)
        group = Group.objects.filter(owner=tester, name=GROUP_NAME).first()
        if group is None:
            group = create_group(tester, GROUP_NAME)
        for person in people.values():
            join_group(group, person)
        # Start clean from today, so a re-run leaves no stray days behind.
        PlanDay.objects.filter(user__in=people.values(), date__gte=first).delete()
        MeetUp.objects.filter(group=group, date__gte=first).delete()
        # Meet-ups first: joining one plans the day, which the runs then set.
        for offset, code, organiser, going in MEETUPS:
            meetup = propose_meetup(
                group,
                people[organiser],
                first + datetime.timedelta(days=offset),
                resorts[code],
                start_time=datetime.time(9, 0),
            )
            for name in going:
                join_meetup(meetup, people[name])
        PlanDay.objects.filter(user__in=people.values(), date__gte=first).delete()
        everyone = {"you": runs, **friend_runs()}
        for key, person_runs in everyone.items():
            for run in person_runs:
                self._write(people[key], run, first, resorts)

    def _write(
        self,
        user: User,
        run: Run,
        first: datetime.date,
        resorts: dict[str, Resort],
    ) -> None:
        """Write one run's days."""
        for day, letter in zip(run.days(first), run.skiing, strict=True):
            set_plan(
                user,
                day,
                SKIING[letter],
                resort=resorts[run.where] if run.where else None,
                note=run.note,
                is_private=run.private,
            )
