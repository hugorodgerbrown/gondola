"""apps/tour/middleware.py — Scope every screen to the demo while someone tours.

While the session says the person is touring, ``request.tour`` holds the
tour and ``request.user.tour_group_id`` names their demo copy, which
``GroupQuerySet.for_user`` then returns as their only group. A copy past
its lifetime ends the tour.

Nothing is saved in the demo: plan days belong to a person, not a group,
so a day saved in the demo would show in their real groups. Any form
posted to the planning screens is answered here instead of by its view.
Saving a day moves the tour on to the group (chapter 3), and anything
else stays where it was, saying nothing was saved.

Someone not touring who still has a demo copy (a closed tab, a sign-out,
another device) has it deleted on their next page load.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.models import User
from apps.core.http import is_htmx

from .demo import discard_demos, live_demo
from .session import TOUR_KEY, Tour, tour_state

# Where a post that would have saved goes instead: the next chapter's page.
SAVES_DAY = {"day", "several_days"}


def go(request: HttpRequest, url: str) -> HttpResponse:
    """Send the browser to ``url``, from a plain post or an HTMX one."""
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return HttpResponseRedirect(url)


def _back(request: HttpRequest) -> str:
    """Return the page the post came from, if it's ours, else the calendar."""
    referer = request.headers.get("Referer", "")
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return referer
    return reverse("planning:calendar")


def guard(request: HttpRequest, tour: Tour, url_name: str) -> HttpResponse:
    """Answer a planning post during the tour, without saving anything."""
    if url_name in SAVES_DAY:
        return go(
            request,
            reverse("planning:group_detail", kwargs={"group_uuid": tour.group.uuid}),
        )
    messages.info(request, "That's the demo: nothing was saved.")
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
    return HttpResponseRedirect(_back(request))


class TourMiddleware:
    """Scope the request to the demo copy while touring; tidy up after."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Keep the next handler."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Attach the tour, if any, before the view runs."""
        request.tour = None  # type: ignore[attr-defined]
        user = request.user
        if isinstance(user, User):
            state = tour_state(request)
            if state is not None:
                group = live_demo(user, state["group"])
                if group is None:
                    request.session.pop(TOUR_KEY, None)
                else:
                    user.tour_group_id = group.pk  # type: ignore[attr-defined]
                    request.tour = Tour(group=group, next_url=state.get("next", ""))  # type: ignore[attr-defined]
            elif request.method == "GET" and not is_htmx(request):
                discard_demos(user)
        return self.get_response(request)

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., HttpResponse],
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> HttpResponse | None:
        """Answer planning posts during the tour instead of their views."""
        tour = getattr(request, "tour", None)
        match = request.resolver_match
        if tour is None or request.method != "POST" or match is None:
            return None
        if match.namespace != "planning":
            return None
        return guard(request, tour, match.url_name or "")
