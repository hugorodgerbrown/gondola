"""
apps/core/views.py — The front page and the installable-app plumbing.

* ``home`` explains the app to a signed-out visitor and sends a signed-in
  one to the map.
* ``manifest`` and ``service_worker`` make the site installable as an app
  on a phone. The worker is served from the root so it controls every page.
* ``offline`` is the page the worker shows when there is no signal and the
  page asked for was never cached.
* ``livez`` and ``healthz`` are the health checks: Render's (the process is
  up) and the one bin/titan and uptime monitors use (the database answers).
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """Show the front page, or the map once signed in."""
    if request.user.is_authenticated:
        return redirect("planning:map")
    return render(request, "core/home.html")


@require_GET
@cache_control(max_age=60 * 60)
def manifest(request: HttpRequest) -> JsonResponse:
    """Return the web app manifest."""
    return JsonResponse(
        {
            "name": settings.SITE_NAME,
            "short_name": settings.SITE_NAME,
            "description": "Who's skiing where, and where to meet.",
            "id": "/",
            "start_url": "/map/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f2f0ec",
            "theme_color": "#f2f0ec",
            "icons": [
                {
                    "src": static("img/icon-192.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("img/icon-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("img/icon-maskable-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        content_type="application/manifest+json",
    )


@require_GET
@cache_control(no_cache=True)
def service_worker(request: HttpRequest) -> HttpResponse:
    """Return the service worker script, from the site root."""
    return render(
        request,
        "core/sw.js",
        {
            "precache": json.dumps(
                [
                    "/offline/",
                    static("css/app.css"),
                    static("js/app.js"),
                    static("vendor/htmx-2.0.4.min.js"),
                ]
            )
        },
        content_type="application/javascript",
    )


@require_GET
def offline(request: HttpRequest) -> HttpResponse:
    """Say there's no signal."""
    return render(request, "core/offline.html")


@never_cache
def livez(request: HttpRequest) -> HttpResponse:
    """Answer 200 while the process can answer at all (Render's health check).

    It does no work and never reads ``request.user`` (a session lookup is a
    database query), so a database outage shows on /healthz without Render
    restarting a healthy web process over it.
    """
    return HttpResponse("ok", content_type="text/plain")


@never_cache
def healthz(request: HttpRequest) -> HttpResponse:
    """Answer 200 when the database answers a read, 503 otherwise.

    The error is logged, never returned: a driver's message can carry the
    database host and role.
    """
    try:
        get_user_model().objects.exists()
    except DatabaseError:
        logger.exception("healthz: database read failed")
        return HttpResponse("error", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
