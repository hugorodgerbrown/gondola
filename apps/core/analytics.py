"""apps/core/analytics.py — Visitor counts and goals by fivebar (https://fiveb.ar).

On under SITE_URL's host unless that is local; ``FIVEBAR_DOMAIN`` overrides
it, and empty turns it off (config/settings.py). Then every page carries
fivebar's tag (``templates/includes/_analytics.html``): the script counts each page by
itself, with no cookies. Ported from the Titan template.

A page whose address holds a secret or an id (an invite token, a group's
uuid) is counted under its route instead, with the values named, e.g.
``/i/:token/``, so nothing private reaches fivebar.

Every event is a goal in fivebar. The server records one with ``record``:
it waits in the session until the next full page, which hands it to
``static/js/analytics.js`` to send, so an event recorded before a redirect
isn't lost. A click that is itself the event carries ``data-tally`` in the
template instead. Event data is a few plain words or flags: never anything
about the person.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    # Only for annotations: config/settings.py imports this module.
    from django.http import HttpRequest

# Where the script loads from.
ORIGIN = "https://fiveb.ar"
SCRIPT = f"{ORIGIN}/js/tally.js"
# The session key holding events waiting for the next full page.
SESSION_KEY = "analytics_events"
# fivebar keeps at most 8 data names an event.
MAX_DATA = 8

# A route's converters, "<str:token>" or "<token>": each becomes ":token".
_CONVERTER = re.compile(r"<(?:\w+:)?(\w+)>")


def csp_sources(domain: str) -> list[str]:
    """Return the sources script-src and connect-src add for fivebar: none while it is off."""
    return [ORIGIN] if domain else []


def record(request: HttpRequest, name: str, **data: str | int | bool) -> None:
    """Queue the event ``name`` for the next full page to send, while fivebar is on."""
    if not settings.FIVEBAR_DOMAIN:
        return
    if len(data) > MAX_DATA:
        raise ValueError(f"fivebar keeps at most {MAX_DATA} data names.")
    events = list(request.session.get(SESSION_KEY, []))
    events.append([name, data])
    request.session[SESSION_KEY] = events


def pending(request: HttpRequest) -> list[list[object]]:
    """Return the queued events and forget them: they're sent once."""
    return list(request.session.pop(SESSION_KEY, []))


def counted_path(request: HttpRequest) -> str:
    """Return the path to count a page under when its address holds values, else "".

    ``/i/abc123/`` is counted as ``/i/:token/``. A page whose route takes
    no values is counted under its own path, so this is empty and the tag
    carries no ``data-path``.
    """
    match = getattr(request, "resolver_match", None)
    if match is None or not (match.kwargs or match.args):
        return ""
    return "/" + _CONVERTER.sub(r":\1", match.route)


def analytics(request: HttpRequest) -> dict[str, dict[str, object]]:
    """Expose fivebar's settings to every template as ``analytics``.

    ``events`` is a function, so only the template that reads it (the full
    page, not an HTMX fragment) takes the queued events.
    """
    domain = settings.FIVEBAR_DOMAIN

    def events() -> list[list[object]]:
        """Return the queued events, when the page asks for them."""
        return pending(request)

    return {
        "analytics": {
            "domain": domain,
            "script": SCRIPT,
            "path": counted_path(request) if domain else "",
            "events": events,
        }
    }
