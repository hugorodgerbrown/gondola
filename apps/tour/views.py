"""apps/tour/views.py — Starting, ending and finishing the tour.

* ``offer`` is chapter 0: the welcome, with Not now and Show me round.
  New accounts see it once, after their name and passkey screens; anyone
  can take the tour again from their account page.
* ``start`` makes the person's demo copy and opens the calendar (chapter 1).
* ``end`` is the demo bar's End tour, from any chapter.
* ``finish`` is the end of chapter 5: the copy goes and chapter 6, the
  hand-off, shows over the real calendar.

The chapters themselves are played by ``static/js/tour.js`` over the
real screens (see ``script.py`` and ``context_processors.py``).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.services import safe_next
from apps.core.analytics import record
from apps.groups.views.helpers import current_user

from . import session
from .demo import DemoUnavailable, create_demo
from .script import WELCOME, WELCOME_TITLE


@login_required
@require_GET
def offer(request: HttpRequest) -> HttpResponse:
    """Show the welcome and offer the tour."""
    next_url = safe_next(request.GET.get("next"), request)
    record(request, "Tour offered")
    return render(
        request,
        "tour/offer.html",
        {"next_url": next_url, "title": WELCOME_TITLE, "welcome": WELCOME},
    )


@login_required
@require_POST
def start(request: HttpRequest) -> HttpResponse:
    """Make the person's demo copy and open chapter 1."""
    user = current_user(request)
    next_url = safe_next(request.POST.get("next"), request)
    try:
        group = create_demo(user)
    except DemoUnavailable:
        messages.error(request, "The tour isn't available just now.")
        return redirect(next_url)
    session.begin(request, group, next_url)
    record(request, "Tour started", replay=user.toured_at is not None)
    return redirect("planning:calendar")


@login_required
@require_POST
def end(request: HttpRequest) -> HttpResponse:
    """End the tour early, from the demo bar."""
    session.stop(request, current_user(request))
    chapter = request.POST.get("chapter", "")
    record(request, "Tour ended", chapter=int(chapter) if chapter.isdigit() else 0)
    messages.success(request, "Tour ended. The demo group is gone.")
    return redirect("planning:calendar")


@login_required
@require_POST
def finish(request: HttpRequest) -> HttpResponse:
    """Finish the tour: delete the copy and hand over to the real calendar."""
    state = session.finish(request, current_user(request))
    record(request, "Tour finished", group=state)
    return redirect("planning:calendar")
