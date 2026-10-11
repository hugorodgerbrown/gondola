"""
apps/groups/management/commands/send_evening_emails.py — The nightly email.

Scheduled once each evening. A bare run lists who would get tomorrow's
email and sends nothing; ``--commit`` sends. ``--date`` picks another day
(for a re-run or a test). Exits non-zero if any email failed to send.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.groups.services.evening import (
    Digest,
    build_digest,
    recipients,
    send_digest,
)
from apps.groups.services.plans import today

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Send the evening-before email for tomorrow."""

    help = "Send tomorrow's evening email. Dry run unless --commit."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add --commit and --date."""
        parser.add_argument(
            "--commit", action="store_true", help="Send. Without it, nothing is sent."
        )
        parser.add_argument(
            "--date",
            type=datetime.date.fromisoformat,
            help="The day the email is about (YYYY-MM-DD). Default: tomorrow.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Build each person's digest and send the ones with news."""
        day: datetime.date = options["date"] or today() + datetime.timedelta(days=1)
        commit: bool = options["commit"]
        verbosity: int = options["verbosity"]
        people = recipients(day)
        sent = skipped = failed = 0
        for remaining, user in zip(range(len(people), 0, -1), people, strict=True):
            digest = build_digest(user, day)
            label = f"{remaining} · {user.pk} {user.email}"
            if digest.is_empty:
                skipped += 1
                self._say(verbosity, 2, f"{label}: nothing new")
                continue
            self._say(verbosity, 1, f"{label}: {digest.subject}")
            if commit:
                if self._send(digest):
                    sent += 1
                else:
                    failed += 1
        verb = "Sent" if commit else "Would send"
        count = sent if commit else len(people) - skipped
        self._say(
            verbosity,
            1,
            f"{verb} {count} evening emails for {day:%a %d %b}; "
            f"{skipped} people had nothing new.",
        )
        if not commit:
            self._say(verbosity, 1, "Dry run. Re-run with --commit to send.")
        if failed:
            raise CommandError(f"{failed} evening emails failed.")

    def _say(self, verbosity: int, level: int, message: str) -> None:
        """Write ``message`` when the run is at least this verbose."""
        if verbosity >= level:
            self.stdout.write(message)

    def _send(self, digest: Digest) -> bool:
        """Send one digest; log and return False if it fails."""
        try:
            send_digest(digest)
        except Exception:  # one bad address must not stop the rest
            logger.exception("Evening email to user %s failed", digest.user.pk)
            return False
        return True
