"""
apps/groups/management/commands/seed_demo.py — A populated group to try.

Makes six friends in "Thursday crew" with a week of plans and a meet-up,
starting today, so a tester (or a screenshot) lands on a busy board and
map. Needs the resorts imported first. A bare run says what it would do;
``--commit`` writes it. Re-running moves the plans to the new week.

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
from apps.groups.models import Group, MeetUp, PlanDay
from apps.groups.services.meetups import join_meetup, propose_meetup
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.plans import set_plan, today
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
# One row per person, one cell per day from today: a resort code (skiing
# there), "?" for not sure, "-" for not skiing, "" for unsaid. A code can
# take "-" (there, not skiing) or "?" (there, maybe skiing), and any cell a
# trailing "*" for private.
WEEK = {
    "you": ["VERB", "VERB", "-", "?", "", "CRA", "SAASF*"],
    "Anna": ["VERB", "GRIME", "?", "", "SAASF", "CRA", ""],
    "Ben": ["SAASF", "VERB", "VERB", "?", "VERB", "", "-"],
    "Chloé": ["VERB", "VERB", "VERB-", "", "VERB", "CRA", "?"],
    "Ella": ["CHAM", "CHAM-", "CHAM-", "CHAM", "CHAM?", "", "?"],
    "Felix": ["?", "", "", "", "", "CRA", "CRA"],
}
NOTES = {("Anna", 0): "First lift, then Mont Fort", ("you", 5): "With the kids"}
MEETUP_DAY = 5


class Command(BaseCommand):
    """Create or refresh the demo group."""

    help = "Create a demo group with a week of plans. Dry run unless --commit."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add --commit and --email."""
        parser.add_argument("--commit", action="store_true", help="Write the data.")
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
        if not options["commit"]:
            self.stdout.write(
                f"Would create {GROUP_NAME} owned by {email} with "
                f"{len(FRIENDS)} friends, 7 days of plans from {today():%d %b} "
                "and one meet-up. Dry run. Re-run with --commit to save."
            )
            return
        with transaction.atomic():
            self._seed(email, {code: resorts[name] for code, name in RESORTS.items()})
        self.stdout.write(f"Seeded {GROUP_NAME}. Sign in as {email} to see it.")

    def _person(self, email: str, name: str) -> User:
        """Return the user for ``email``, creating them if needed."""
        user, created = User.objects.get_or_create(
            email=email, defaults={"display_name": name}
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user

    def _seed(self, email: str, resorts: dict[str, Resort]) -> None:
        """Write the people, the group, the week and the meet-up."""
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
        start = today()
        days = [start + datetime.timedelta(days=n) for n in range(len(WEEK["you"]))]
        PlanDay.objects.filter(user__in=people.values(), date__in=days).delete()
        MeetUp.objects.filter(group=group, date__in=days).delete()
        for key, cells in WEEK.items():
            for index, cell in enumerate(cells):
                self._plan(
                    people[key], days[index], cell, resorts, NOTES.get((key, index), "")
                )
        meetup = propose_meetup(
            group,
            owner,
            days[MEETUP_DAY],
            resorts["CRA"],
            start_time=datetime.time(9, 0),
            latitude=46.3125,
            longitude=7.4795,
        )
        for name in ("Chloé", "Felix"):
            join_meetup(meetup, people[name])

    def _plan(
        self,
        user: User,
        day: datetime.date,
        cell: str,
        resorts: dict[str, Resort],
        note: str,
    ) -> None:
        """Write one cell of the demo week."""
        private = cell.endswith("*")
        code = cell.rstrip("*")
        if not code:
            return
        skiing = PlanDay.Skiing.YES
        if code[-1] in "?-":
            skiing = PlanDay.Skiing.NOT_SURE if code[-1] == "?" else PlanDay.Skiing.NO
            code = code[:-1]
        set_plan(
            user,
            day,
            skiing,
            resort=resorts[code] if code else None,
            note=note,
            is_private=private,
        )
