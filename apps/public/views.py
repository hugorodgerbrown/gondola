"""The public pages: the front page, terms, privacy and help.

They sit outside the installed app's /app/ scope, so the service worker
never caches them and they never show inside the installed app.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """The front page: what Gondola is, and the way in. Signed in, the map."""
    if request.user.is_authenticated:
        return redirect("planning:map")
    return render(request, "public/home.html")


@require_GET
def terms(request: HttpRequest) -> HttpResponse:
    """The terms of service."""
    return render(request, "public/terms.html")


@require_GET
def privacy(request: HttpRequest) -> HttpResponse:
    """The privacy notice."""
    return render(request, "public/privacy.html")


@require_GET
def help_page(request: HttpRequest) -> HttpResponse:
    """Help: signing in, passkeys, groups, days, installing the app, offline."""
    return render(request, "public/help.html")
