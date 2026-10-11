"""apps/groups/converters.py — A ``date`` path converter for YYYY-MM-DD URLs."""

from __future__ import annotations

import datetime


class DateConverter:
    """Match an ISO date in a URL and hand the view a ``datetime.date``."""

    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value: str) -> datetime.date:
        """Parse the URL segment; an impossible date is a non-match."""
        return datetime.date.fromisoformat(value)

    def to_url(self, value: datetime.date) -> str:
        """Format a date for a URL."""
        return value.isoformat()
