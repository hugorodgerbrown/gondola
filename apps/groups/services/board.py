"""
apps/groups/services/board.py — The who's-where board for one group.

People down the side, seven days across, a short resort code in each cell.
The viewer's own row comes first.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from apps.accounts.models import User

from ..models import Group, PlanDay
from .people import members_of
from .plans import date_range, today

BOARD_DAYS = 7


@dataclass(frozen=True)
class Cell:
    """One person on one day."""

    text: str
    title: str


@dataclass(frozen=True)
class BoardRow:
    """One person's week."""

    person: User
    is_me: bool
    cells: list[Cell]


@dataclass(frozen=True)
class BoardDay:
    """One column: a date, and whether it is today."""

    date: datetime.date
    is_today: bool


@dataclass(frozen=True)
class Board:
    """The whole board for one week."""

    group: Group
    start: datetime.date
    days: list[BoardDay]
    rows: list[BoardRow]

    @property
    def previous_start(self) -> datetime.date:
        """Return the start of the week before."""
        return self.start - datetime.timedelta(days=BOARD_DAYS)

    @property
    def next_start(self) -> datetime.date:
        """Return the start of the week after."""
        return self.start + datetime.timedelta(days=BOARD_DAYS)

    @property
    def next_end(self) -> datetime.date:
        """Return the last date of the week after."""
        return self.next_start + datetime.timedelta(days=BOARD_DAYS - 1)

    @property
    def end(self) -> datetime.date:
        """Return the last date shown."""
        return self.days[-1].date


EMPTY = Cell(text="", title="Hasn't said")


def cell_for(plan: PlanDay | None, *, mine: bool) -> Cell:
    """Return the cell for one plan, as the viewer may see it."""
    if plan is None:
        return EMPTY
    return Cell(text=plan.resort.display_code, title=plan.describe())


def build_board(
    group: Group, viewer: User, start: datetime.date | None = None
) -> Board:
    """Return ``group``'s board for the week from ``start`` (default today)."""
    start = start or today()
    days = date_range(start, BOARD_DAYS)
    people = members_of(group)
    plans = {
        (p.user_id, p.date): p
        for p in PlanDay.objects.filter(user__in=people, date__in=days).select_related(
            "resort"
        )
    }
    ordered = sorted(people, key=lambda u: u.pk != viewer.pk)
    rows = [
        BoardRow(
            person=person,
            is_me=person.pk == viewer.pk,
            cells=[
                cell_for(plans.get((person.pk, day)), mine=person.pk == viewer.pk)
                for day in days
            ],
        )
        for person in ordered
    ]
    now = today()
    return Board(
        group=group,
        start=start,
        days=[BoardDay(date=d, is_today=d == now) for d in days],
        rows=rows,
    )
