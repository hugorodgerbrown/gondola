"""apps/groups/views/board.py — The who's-where board for one group."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from apps.core.shortcuts import render

from ..services.board import build_board
from .helpers import current_user, member_group, parse_day


@login_required
@require_GET
def board(request: HttpRequest, group_uuid: str) -> HttpResponse:
    """Show a week of the group: people down the side, days across."""
    group = member_group(request, group_uuid)
    start = parse_day(request.GET.get("start"))
    return render(
        request,
        "groups/board.html",
        {"board": build_board(group, current_user(request), start)},
    )
