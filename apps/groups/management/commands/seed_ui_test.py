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
- friends at your resort, friends elsewhere, a friend "around", and a
  friend whose days are all private.

A bare run prints the plan, day by day, without writing; ``--commit``
writes it. Re-running rewrites the made-up people's days from today, so the
cases move with the calendar. Needs the resorts imported first.

Everyone made up here is a ``*@ui-test.invalid`` account in the "Testers"
auth group. A real account joins "UI test" by being added to Testers in
the admin (see ``services/testers.py``), and keeps its own days.
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts.models import User
from apps.groups.models import PlanDay
from apps.groups.services.memberships import create_group
from apps.groups.services.plans import set_plan, today
from apps.groups.services.testers import (
    MADE_UP_DOMAIN,
    UI_TEST_GROUP,
    get_testers_group,
    sync_tester,
    ui_test_group,
)
from apps.resorts.models import Resort

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
# The day the tester says nothing about, while friends do.
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
        # Offset UNSAID is left out: friends out, nothing from you.
        Run(7, "Y", "VERB", private=True, label="At a resort, private"),
        Run(8, "N", private=True, label="No resort, private"),
        Run(9, "Y", "SAASF", note="First lift", label="Short note"),
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


class Command(BaseCommand):
    """Create or refresh the UI test group."""

    verbosity = 1

    help = (
        "Create a group whose tester covers every where/skiing case. "
        "Dry run unless --commit."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Add --commit."""
        parser.add_argument("--commit", action="store_true", help="Write the data.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Seed the group, or print what would be seeded."""
        resorts = {r.name: r for r in Resort.objects.filter(name__in=RESORTS.values())}
        missing = set(RESORTS.values()) - set(resorts)
        if missing:
            raise CommandError(
                f"Missing resorts {sorted(missing)}: run import_resorts --commit first."
            )
        self.verbosity = options["verbosity"]
        first = today()
        runs = tester_runs(first)
        self._legend(runs, first)
        if not options["commit"]:
            if self.verbosity >= 1:
                self.stdout.write(
                    f"Would create {UI_TEST_GROUP} with {TESTER} and "
                    f"{len(FRIENDS)} friends. Dry run. Re-run with --commit to save."
                )
            return
        by_code = {code: resorts[name] for code, name in RESORTS.items()}
        with transaction.atomic():
            joined = self._seed(first, runs, by_code)
        if self.verbosity >= 1:
            self.stdout.write(
                f"Seeded {UI_TEST_GROUP}. Real accounts in Testers: {joined}. "
                "Add yourself to Testers in the admin to join it."
            )

    def _legend(self, runs: list[Run], first: datetime.date) -> None:
        """Print each of the tester's days and the case it covers."""
        if self.verbosity < 1:
            return
        unsaid = first + datetime.timedelta(days=UNSAID)
        lines = [(unsaid, f"{unsaid:%a %d %b}", "Unsaid, friends out")]
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
        first: datetime.date,
        runs: list[Run],
        resorts: dict[str, Resort],
    ) -> int:
        """Write the people, the group and every plan.

        Returns how many real accounts in Testers are members.
        """
        people = {}
        for key, name in [("you", TESTER), *((f, f) for f in FRIENDS)]:
            slug = name.lower().replace("é", "e")
            people[key] = self._person(f"{slug}@{MADE_UP_DOMAIN}", name)
        get_testers_group().user_set.add(*people.values())
        group = ui_test_group() or create_group(people["you"], UI_TEST_GROUP)
        made_up = {person.pk for person in people.values()}
        real = 0
        for user in get_testers_group().user_set.all():
            sync_tester(user, group)
            real += user.pk not in made_up
        # Start clean from today, so a re-run leaves no stray days behind.
        PlanDay.objects.filter(user__in=people.values(), date__gte=first).delete()
        everyone = {"you": runs, **friend_runs()}
        for key, person_runs in everyone.items():
            for run in person_runs:
                self._write(people[key], run, first, resorts)
        return real

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
