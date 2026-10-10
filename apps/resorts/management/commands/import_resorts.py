"""
apps/resorts/management/commands/import_resorts.py — Load the resort sheets.

Read-only by default: a bare run reports what would change. ``--commit``
writes it. Exits non-zero if any row failed.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.resorts.services import import_sheets


class Command(BaseCommand):
    """Import passes and resorts from apps/resorts/data/."""

    help = "Import passes and resorts from the sheets. Dry run unless --commit."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the --commit flag."""
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Write the changes. Without it, nothing is saved.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the import and report what it did."""
        commit: bool = options["commit"]
        result = import_sheets(commit=commit)
        verb = "Imported" if commit else "Would import"
        if options["verbosity"] >= 1:
            self.stdout.write(
                f"{verb}: {result.passes_created} new passes, "
                f"{result.resorts_created} new resorts, "
                f"{result.resorts_updated} updated resorts."
            )
            if not commit:
                self.stdout.write("Dry run. Re-run with --commit to save.")
        for error in result.errors:
            self.stderr.write(error)
        if result.errors:
            raise CommandError(f"{len(result.errors)} resort rows failed.")
