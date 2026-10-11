"""
apps/core/views.py — The front page and the installable-app plumbing.

* ``home`` explains the app to a signed-out visitor and sends a signed-in
  one to the map.
* ``manifest`` and ``service_worker`` make the site installable as an app
  on a phone. The worker is served from the root so it controls every page.
* ``offline`` is the page the worker shows when there is no signal and the
  page asked for was never cached.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET


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
                },
                {
                    "src": static("img/icon-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
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
