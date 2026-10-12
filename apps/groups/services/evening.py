"""
apps/groups/services/evening.py — The evening-before email.

Sent once a day, the evening before. A person gets it when they have said
something about tomorrow and there is something from friends to tell
them: who in each group is where tomorrow. Anyone can stop it with one
tap from the footer.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import make_unsubscribe_token

from ..models import Group, PlanDay
from .plans import join_names

logger = logging.getLogger(__name__)


@dataclass
class ResortLine:
    """Who from one group is at one resort tomorrow."""

    resort_name: str
    names: list[str]

    @property
    def people(self) -> str:
        """Return the names as prose."""
        return join_names(self.names)


@dataclass
class GroupSection:
    """One of the person's groups, tomorrow."""

    group: Group
    url: str
    lines: list[ResortLine] = field(default_factory=list)


@dataclass
class Digest:
    """Everything one person's evening email says."""

    user: User
    day: datetime.date
    groups: list[GroupSection]

    @property
    def is_empty(self) -> bool:
        """Return whether there is nothing from friends worth sending."""
        return not any(g.lines for g in self.groups)

    @property
    def subject(self) -> str:
        """Return the subject line."""
        return "Tomorrow: who's where"


def _absolute(path: str) -> str:
    """Return ``path`` on the public site."""
    return str(settings.SITE_URL).rstrip("/") + path


def build_digest(user: User, day: datetime.date) -> Digest:
    """Return what ``user``'s email for ``day`` would say."""
    groups = list(Group.objects.for_user(user).order_by("name"))
    shared = list(
        PlanDay.objects.filter(
            date=day,
            user__group_memberships__group__in=groups,
        )
        .select_related("user", "resort")
        .distinct()
    )
    sections = []
    for group in groups:
        member_ids = set(group.memberships.values_list("user_id", flat=True))
        by_resort: dict[str, list[str]] = {}
        for plan in shared:
            if plan.user_id in member_ids:
                name = "you" if plan.user_id == user.pk else plan.user.to_string()
                by_resort.setdefault(plan.resort.name, []).append(name)
        lines = [
            ResortLine(
                resort_name=resort, names=sorted(names, key=lambda n: n == "you")
            )
            for resort, names in sorted(by_resort.items(), key=lambda kv: -len(kv[1]))
            if any(n != "you" for n in names)
        ]
        board = reverse("planning:board", kwargs={"group_uuid": group.uuid})
        sections.append(
            GroupSection(
                group=group,
                url=_absolute(f"{board}?start={day.isoformat()}"),
                lines=lines,
            )
        )
    return Digest(user=user, day=day, groups=sections)


def recipients(day: datetime.date) -> list[User]:
    """Return who to consider: anyone with a plan for ``day``."""
    planned = PlanDay.objects.filter(date=day).values("user_id")
    return list(
        User.objects.wants_evening_email()
        .filter(pk__in=planned)
        .distinct()
        .order_by("-id")
    )


def send_digest(digest: Digest) -> None:
    """Send one evening email."""
    stop = reverse(
        "accounts:stop_email", kwargs={"token": make_unsubscribe_token(digest.user)}
    )
    context = {
        "digest": digest,
        "SITE_NAME": settings.SITE_NAME,
        "stop_url": _absolute(stop),
    }
    send_mail(
        subject=digest.subject,
        message=render_to_string("groups/email/evening.txt", context),
        html_message=render_to_string("groups/email/evening.html", context),
        from_email=None,
        recipient_list=[digest.user.email],
    )
