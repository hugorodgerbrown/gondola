"""
apps/groups/management/commands/seed_demo.py — A populated group to try.

Makes six friends in "Thursday crew" with a week of plans, so a tester
(or a screenshot) finds a busy board, map and calendar. The week starts
on a Saturday in mid-January, in the thick of the season, so screenshots
don't look like an autumn ski app (in season it starts today);
``--start`` picks another day. Needs the resorts imported first. A bare
run says what it would do; ``--commit`` writes it. Re-running rewrites
that week.

``--email`` makes that address the group's owner, so you can sign in as
yourself and see it. The other five are ``*@demo.invalid`` accounts that
can't receive email.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts.models import User, normalise_email
from apps.groups.models import Group, PlanDay
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.plans import is_plannable, set_plan, today
from apps.resorts.models import Resort

GROUP_NAME = "Thursday crew"
FRIENDS = ["Anna", "Ben", "Chloé", "Ella", "Felix"]
RESORTS = {
    "VERB": "Verbier",
    "SAASF": "Saas-Fee",
    "GRIME": "Grimentz",
    "CRA": "Crans-Montana",
    "CHAM": "Champéry",
}
# One row per person, one cell per day from today: a resort code or "" for
# unsaid.
WEEK = {
    "you": ["VERB", "VERB", "VERB", "", "", "CRA", "SAASF"],
    "Anna": ["VERB", "GRIME", "", "", "SAASF", "CRA", ""],
    "Ben": ["SAASF", "VERB", "VERB", "", "VERB", "", "SAASF"],
    "Chloé": ["VERB", "VERB", "VERB", "", "VERB", "CRA", ""],
    "Ella": ["CHAM", "CHAM", "CHAM", "CHAM", "CHAM", "", ""],
    "Felix": ["", "", "", "", "", "CRA", "CRA"],
}
# Out of season, the demo week starts on the first Saturday on or after
# this January day.
JANUARY_DAY = 9
SATURDAY = 5
SEASON_MONTHS = {12, 1, 2, 3, 4}


def demo_start(now: datetime.date) -> datetime.date:
    """Return when the demo week starts: today in season, else mid-January.

    In season (December to April) today already looks like a ski app, and
    a date that's passed can't be planned. Out of season it's the first
    Saturday on or after 9 January to come.
    """
    if now.month in SEASON_MONTHS:
        return now
    day = datetime.date(now.year + 1, 1, JANUARY_DAY)
    return day + datetime.timedelta(days=(SATURDAY - day.weekday()) % 7)


def parse_start(value: str) -> datetime.date:
    """Return ``--start`` as a date, or fail the command."""
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise CommandError(f"--start {value!r} isn't a YYYY-MM-DD date.") from None


class Command(BaseCommand):
    """Create or refresh the demo group."""

    help = "Create a demo group with a week of plans. Dry run unless --commit."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add --commit, --email and --start."""
        parser.add_argument("--commit", action="store_true", help="Write the data.")
        parser.add_argument(
            "--start",
            type=parse_start,
            help="The week's first day (YYYY-MM-DD). Default: mid-January "
            "(today in season).",
        )
        parser.add_argument(
            "--email",
            default="sam@demo.invalid",
            help="The owner's email: use yours to sign in and see it.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Seed the group, or say what would be seeded."""
        resorts = {r.name: r for r in Resort.objects.filter(name__in=RESORTS.values())}
        missing = set(RESORTS.values()) - set(resorts)
        if missing:
            raise CommandError(
                f"Missing resorts {sorted(missing)}: run import_resorts --commit first."
            )
        email = normalise_email(options["email"])
        start = options["start"] or demo_start(today())
        days = [start + datetime.timedelta(days=n) for n in range(len(WEEK["you"]))]
        if not all(is_plannable(day) for day in days):
            raise CommandError(
                f"{start:%d %b %Y} can't be planned: pick a week from today "
                "to a year ahead."
            )
        if not options["commit"]:
            self.stdout.write(
                f"Would create {GROUP_NAME} owned by {email} with "
                f"{len(FRIENDS)} friends, 7 days of plans from {start:%a %d %b %Y}. "
                "Dry run. Re-run with --commit to save."
            )
            return
        with transaction.atomic():
            self._seed(
                email, days, {code: resorts[name] for code, name in RESORTS.items()}
            )
        self.stdout.write(
            f"Seeded {GROUP_NAME} from {start:%a %d %b %Y}. Sign in as {email} "
            f"and open the calendar at {start:%B}, the board at ?start={start}, or "
            f"the map at ?date={start}."
        )

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
        self, email: str, days: list[datetime.date], resorts: dict[str, Resort]
    ) -> None:
        """Write the people, the group and the week."""
        owner = self._person(email, "Sam")
        people = {"you": owner}
        for name in FRIENDS:
            slug = normalise_email(f"{name.lower().replace('é', 'e')}@demo.invalid")
            people[name] = self._person(slug, name)
        group = Group.objects.filter(owner=owner, name=GROUP_NAME).first()
        if group is None:
            group = create_group(owner, GROUP_NAME)
        for person in people.values():
            join_group(group, person)
        PlanDay.objects.filter(user__in=people.values(), date__in=days).delete()
        for key, cells in WEEK.items():
            for index, cell in enumerate(cells):
                self._plan(people[key], days[index], cell, resorts)

    def _plan(
        self,
        user: User,
        day: datetime.date,
        cell: str,
        resorts: dict[str, Resort],
    ) -> None:
        """Write one cell of the demo week."""
        if cell:
            set_plan(user, day, resorts[cell])
