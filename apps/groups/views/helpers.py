"""
apps/groups/views/helpers.py — Lookups the planning views share.

A group is only ever found for one of its members: anyone else gets a 404,
so a guessed uuid reveals nothing.
"""

from __future__ import annotations

import datetime

from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404

from apps.accounts.models import User

from ..models import Group
from ..services.plans import today


def current_user(request: HttpRequest) -> User:
    """Return the signed-in user, typed (views are behind ``login_required``)."""
    user = request.user
    if not isinstance(user, User):  # pragma: no cover — login_required runs first
        raise Http404
    return user


def member_group(request: HttpRequest, group_uuid: object) -> Group:
    """Return the group if the signed-in user belongs to it, else 404."""
    return get_object_or_404(
        Group.objects.for_user(current_user(request)).select_related("owner"),
        uuid=group_uuid,
    )


def parse_day(value: str | None, default: datetime.date | None = None) -> datetime.date:
    """Return the ISO date in ``value``, or ``default`` (today) if absent or bad."""
    if value:
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            pass
    return default or today()
