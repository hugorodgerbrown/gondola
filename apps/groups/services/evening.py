"""
apps/groups/services/evening.py — The evening-before email.

Sent once a day, the evening before. A person gets it when they have said
something about tomorrow (any status), or one of their groups has a
meet-up tomorrow, and there is something from friends to tell them: who
in each group is where tomorrow, and the meet-ups. Private days are left
out, as everywhere. Anyone can stop it with one tap from the footer.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import make_unsubscribe_token

from ..models import Group, MeetUp, PlanDay
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
class MeetUpLine:
    """A meet-up tomorrow in one of the person's groups."""

    meetup: MeetUp
    going: int
    is_going: bool
    url: str


@dataclass
class Digest:
    """Everything one person's evening email says."""

    user: User
    day: datetime.date
    meetups: list[MeetUpLine]
    groups: list[GroupSection]

    @property
    def is_empty(self) -> bool:
        """Return whether there is nothing from friends worth sending."""
        return not self.meetups and not any(g.lines for g in self.groups)

    @property
    def subject(self) -> str:
        """Return the subject line."""
        if self.meetups:
            first = self.meetups[0]
            return f"Tomorrow: meet-up at {first.meetup.resort}, {first.going} going"
        return "Tomorrow: who's where"


def _absolute(path: str) -> str:
    """Return ``path`` on the public site."""
    return str(settings.SITE_URL).rstrip("/") + path


def build_digest(user: User, day: datetime.date) -> Digest:
    """Return what ``user``'s email for ``day`` would say."""
    groups = list(Group.objects.for_user(user).order_by("name"))
    shared = list(
        PlanDay.objects.shared()
        .filter(
            date=day,
            status=PlanDay.Status.RESORT,
            user__group_memberships__group__in=groups,
        )
        .select_related("user", "resort")
        .distinct()
    )
    own = PlanDay.objects.filter(user=user, date=day).select_related("resort").first()
    sections = []
    for group in groups:
        member_ids = set(group.memberships.values_list("user_id", flat=True))
        by_resort: dict[str, list[str]] = {}
        for plan in shared:
            if plan.user_id in member_ids and plan.resort is not None:
                name = "you" if plan.user_id == user.pk else plan.user.to_string()
                by_resort.setdefault(plan.resort.name, []).append(name)
        if own and own.is_private and own.resort is not None:
            by_resort.setdefault(own.resort.name, []).append("you")
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
    meetups = [
        MeetUpLine(
            meetup=meetup,
            going=meetup.participants.count(),
            is_going=meetup.participants.filter(user=user).exists(),
            url=_absolute(
                reverse("planning:meetup", kwargs={"token": meetup.share_token})
            ),
        )
        for meetup in MeetUp.objects.filter(group__in=groups, date=day).select_related(
            "resort", "organiser", "group"
        )
    ]
    return Digest(user=user, day=day, meetups=meetups, groups=sections)


def recipients(day: datetime.date) -> list[User]:
    """Return who to consider: a plan for ``day``, or a group meet-up then."""
    planned = PlanDay.objects.filter(date=day).values("user_id")
    meetup_groups = MeetUp.objects.filter(date=day).values("group_id")
    return list(
        User.objects.wants_evening_email()
        .filter(Q(pk__in=planned) | Q(group_memberships__group_id__in=meetup_groups))
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
