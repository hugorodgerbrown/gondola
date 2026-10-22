"""apps/core/http.py — Small helpers for HTMX-aware views.

A sheet (the bottom panel that opens over a page) is fetched by HTMX as a
fragment, and the same URL renders a whole page when opened directly, so
every screen still works without JavaScript and from a bookmark.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from apps.core.shortcuts import render


def is_htmx(request: HttpRequest) -> bool:
    """Return whether the request was made by HTMX."""
    return request.headers.get("HX-Request") == "true"


def render_sheet(request: HttpRequest, template: str, context: dict[str, object]) -> HttpResponse:
    """Render a sheet's fragment for HTMX, or the fragment inside a page.

    ``template`` is the fragment. A plain request gets ``core/sheet_page.html``
    wrapped around it, so the sheet works as a page of its own.
    """
    if is_htmx(request):
        return render(request, template, context)
    return render(request, "core/sheet_page.html", {**context, "fragment": template})


def refresh(request: HttpRequest, fallback_url: str) -> HttpResponse:
    """Finish a sheet that saved something.

    HTMX reloads the page underneath the sheet; a plain form post is sent
    on to ``fallback_url``.
    """
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
    return redirect(fallback_url)
