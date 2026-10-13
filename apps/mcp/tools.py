"""apps/mcp/tools.py — The MCP tools. Each is a function of (user, arguments).

Every tool runs as the token's user and sees exactly what the app shows
them: their own days, and the days of everyone they share a group with
(``friend_ids``, which goes through ``Group.objects.for_user`` so demo
groups never show). Writes only ever touch the user's own days, through
``update_plans`` and ``clear_plans`` like the calendar.

Add a tool by writing a function and listing it in TOOLS with its JSON
Schema. Raise ToolError for a mistake the model should see and correct.
The Tool shape is the Titan template's.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from apps.accounts.models import User
from apps.groups.models import Group, PlanDay
from apps.groups.services.people import friend_ids, members_of
from apps.groups.services.plans import (
    PLAN_HORIZON_DAYS,
    clear_plans,
    is_plannable,
    today,
    update_plans,
)
from apps.resorts.models import Resort
from apps.resorts.search import fold, search_resorts

# The most days one call may name, so a typo'd year can't write or read a decade.
MAX_DAYS = PLAN_HORIZON_DAYS + 1
# The most days whos_where answers for at once.
MAX_BOARD_DAYS = 31


class ToolError(Exception):
    """A problem with the call that the model can fix and retry."""


@dataclass(frozen=True)
class Tool:
    """One MCP tool: its name, description, input schema and implementation."""

    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[[Any, dict[str, Any]], dict[str, Any]]
    read_only: bool = True

    def describe(self) -> dict[str, Any]:
        """Return the tool as tools/list lists it."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {"readOnlyHint": self.read_only},
        }


# ---------------------------------------------------------------------------
# Reading the arguments
# ---------------------------------------------------------------------------


def _date(value: Any, key: str) -> datetime.date:
    """Return ``value`` as a date, or explain the format."""
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            pass
    raise ToolError(f"{key} must be a date written YYYY-MM-DD, not {value!r}.")


def _span(start: datetime.date, end: datetime.date, limit: int) -> list[datetime.date]:
    """Return every date from ``start`` to ``end``, at most ``limit`` of them."""
    if end < start:
        raise ToolError("to must be on or after from.")
    count = (end - start).days + 1
    if count > limit:
        raise ToolError(f"Ask for at most {limit} days at once.")
    return [start + datetime.timedelta(days=n) for n in range(count)]


def _dates(
    args: dict[str, Any], limit: int = MAX_DAYS, default: int | None = None
) -> list[datetime.date]:
    """Return the days a call names: ``dates``, or ``from`` (and ``to``).

    With neither, ``default`` days from today, or an error if there is none.
    """
    if "dates" in args:
        values = args["dates"]
        if not isinstance(values, list) or not values:
            raise ToolError("dates must be a non-empty list of YYYY-MM-DD dates.")
        if len(values) > limit:
            raise ToolError(f"Ask for at most {limit} days at once.")
        return sorted({_date(v, "dates") for v in values})
    if "from" in args:
        start = _date(args["from"], "from")
        end = _date(args["to"], "to") if "to" in args else start
        return _span(start, end, limit)
    if default is None:
        raise ToolError("Say which days: dates, or from and to.")
    return _span(today(), today() + datetime.timedelta(days=default - 1), limit)


def _text(args: dict[str, Any], key: str) -> str:
    """Return a required, non-blank string argument."""
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{key} is required.")
    return value.strip()


def _plannable(days: list[datetime.date], verb: str) -> list[datetime.date]:
    """Return ``days`` if all can be changed, else refuse the lot.

    Writes and clears share the calendar's window, so a wrong year can't
    touch a past day that no tool could then put back.
    """
    refused = [d.isoformat() for d in days if not is_plannable(d)]
    if refused:
        raise ToolError(
            f"Days can be changed from today up to {PLAN_HORIZON_DAYS} days ahead; "
            f"nothing was {verb}. Outside that: {', '.join(refused)}."
        )
    return days


def _resort(query: str) -> Resort:
    """Return the one resort ``query`` names: its code, its name, or one match."""
    matches = search_resorts(query)
    folded = fold(query)
    exact = [r for r in matches if folded in {fold(r.code), fold(r.name)} - {""}] or matches
    if len(exact) == 1:
        return exact[0]
    if not exact:
        raise ToolError(f"No resort matches {query!r}. Try find_resort.")
    names = ", ".join(r.name for r in exact)
    raise ToolError(f"{query!r} could be {names}. Say which.")


# ---------------------------------------------------------------------------
# Shaping the results
# ---------------------------------------------------------------------------


def _resort_data(resort: Resort) -> dict[str, Any]:
    """Return a resort as the tools describe it."""
    return {
        "name": resort.name,
        "code": resort.display_code,
        "canton": resort.canton,
        "passes": [p.name for p in resort.passes.all()],
    }


def _day(plan: PlanDay) -> dict[str, str]:
    """Return one said day: its date, weekday and resort."""
    return {
        "date": plan.date.isoformat(),
        "weekday": f"{plan.date:%A}",
        "resort": plan.resort.name,
        "code": plan.resort.display_code,
    }


def _own_days(user: User, args: dict[str, Any]) -> Iterable[PlanDay]:
    """Return ``user``'s days in the range asked, or from today on."""
    plans = PlanDay.objects.filter(user=user).select_related("resort")
    if "dates" in args or "from" in args:
        return plans.filter(date__in=_dates(args))
    return plans.filter(date__gte=today())


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------


def find_resort(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Return resorts matching part of a name or a code, best first."""
    return {"resorts": [_resort_data(r) for r in search_resorts(_text(args, "query"))]}


def my_days(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Return the user's said days, from today on unless a range is given."""
    return {"days": [_day(p) for p in _own_days(user, args)]}


def set_days(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Put the user in one resort on every day named, replacing what was there."""
    days = _plannable(_dates(args), "saved")
    resort = _resort(_text(args, "resort"))
    update_plans(user, days, resort)
    return {"resort": _resort_data(resort), "saved": [d.isoformat() for d in days]}


def clear_days(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Make the named days unsaid again, from today on (the past is kept)."""
    days = _plannable(_dates(args), "cleared")
    had = PlanDay.objects.filter(user=user, date__in=days).values_list("date", flat=True)
    cleared = sorted(had)
    clear_plans(user, days)
    return {"cleared": [d.isoformat() for d in cleared]}


def my_groups(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Return the user's groups and who is in each."""
    groups = Group.objects.for_user(user).select_related("owner").order_by("name")
    return {
        "groups": [
            {
                "name": g.name,
                "owner": g.owner.to_string(),
                "members": [m.to_string() for m in members_of(g)],
            }
            for g in groups
        ]
    }


def _group(user: User, query: str) -> Group:
    """Return the one group of the user's that ``query`` names."""
    groups = list(Group.objects.for_user(user))
    folded = fold(query)
    exact = [g for g in groups if fold(g.name) == folded]
    matches = exact or [g for g in groups if folded in fold(g.name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ToolError(f"You have no group called {query!r}. Try my_groups.")
    raise ToolError(f"{query!r} could be {', '.join(g.name for g in matches)}.")


def _people(user: User, args: dict[str, Any]) -> set[int]:
    """Return the ids whose days the call may show: the user and their friends."""
    if "group" in args:
        group = _group(user, _text(args, "group"))
        return set(group.memberships.values_list("user_id", flat=True))
    return friend_ids(user) | {user.pk}


def whos_where(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Return, day by day, which resort each of the user's people will be in."""
    days = _dates(args, limit=MAX_BOARD_DAYS, default=1)
    plans = PlanDay.objects.filter(user_id__in=_people(user, args), date__in=days).select_related(
        "user", "resort"
    )
    if "resort" in args:
        plans = plans.filter(resort=_resort(_text(args, "resort")))
    board: dict[datetime.date, dict[Resort, list[str]]] = defaultdict(lambda: defaultdict(list))
    for plan in plans.order_by("date", "resort__name"):
        name = "you" if plan.user_id == user.pk else plan.user.to_string()
        board[plan.date][plan.resort].append(name)
    return {
        "days": [
            {
                "date": day.isoformat(),
                "weekday": f"{day:%A}",
                "resorts": [
                    {"resort": r.name, "code": r.display_code, "people": people}
                    for r, people in board[day].items()
                ],
            }
            for day in days
            if day in board
        ]
    }


def _friend(user: User, query: str) -> User:
    """Return the one person in the user's groups that ``query`` names."""
    folded = fold(query)
    people = list(User.objects.filter(pk__in=friend_ids(user)))
    exact = [p for p in people if fold(p.to_string()) == folded]
    matches = exact or [p for p in people if folded in fold(p.to_string())]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ToolError(f"No one in your groups is called {query!r}.")
    names = ", ".join(p.to_string() for p in matches)
    raise ToolError(f"{query!r} could be {names}. Say which.")


def where_is(user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Return where one person in the user's groups will be, from today on."""
    friend = _friend(user, _text(args, "person"))
    return {
        "person": friend.to_string(),
        "days": [_day(p) for p in _own_days(friend, args)],
    }


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

DATE = {"type": "string", "format": "date", "description": "YYYY-MM-DD"}
DAYS = {
    "dates": {"type": "array", "items": DATE, "description": "Particular days."},
    "from": {**DATE, "description": "First day of a run of days (YYYY-MM-DD)."},
    "to": {**DATE, "description": "Last day of the run, inclusive; defaults to from."},
}
RESORT = {"type": "string", "description": "A resort's name or code, e.g. Verbier."}

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            name="find_resort",
            description=(
                "Find Swiss ski resorts by part of a name or a code. Accents "
                "don't matter. Returns name, code, canton and season passes."
            ),
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            func=find_resort,
        ),
        Tool(
            name="my_days",
            description=(
                "The user's own said days: which resort they'll be in on each. "
                "From today on, unless dates or from/to are given."
            ),
            input_schema={"type": "object", "properties": DAYS},
            func=my_days,
        ),
        Tool(
            name="set_days",
            description=(
                "Say the user will be in one resort on each of the given days, "
                "replacing anything already said for them. Days run from today "
                "to a year ahead. To move a day to another resort, set it again."
            ),
            input_schema={
                "type": "object",
                "properties": {**DAYS, "resort": RESORT},
                "required": ["resort"],
            },
            func=set_days,
            read_only=False,
        ),
        Tool(
            name="clear_days",
            description=(
                "Make the user's given days unsaid again (undecided). Days run "
                "from today to a year ahead; past days are kept."
            ),
            input_schema={"type": "object", "properties": DAYS},
            func=clear_days,
            read_only=False,
        ),
        Tool(
            name="my_groups",
            description="The user's groups, each with its owner and members.",
            input_schema={"type": "object", "properties": {}},
            func=my_groups,
        ),
        Tool(
            name="whos_where",
            description=(
                f"Who will be in which resort, day by day, among the user and "
                f"everyone in their groups ('you' is the user). Today unless "
                f"dates or from/to are given; at most {MAX_BOARD_DAYS} days. "
                f"Narrow it to one group or one resort."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    **DAYS,
                    "group": {"type": "string", "description": "A group's name."},
                    "resort": RESORT,
                },
            },
            func=whos_where,
        ),
        Tool(
            name="where_is",
            description=(
                "Where one person in the user's groups will be: their said days, "
                "from today on unless dates or from/to are given."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    **DAYS,
                    "person": {"type": "string", "description": "Their name."},
                },
                "required": ["person"],
            },
            func=where_is,
        ),
    ]
}
