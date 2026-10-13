"""apps/accounts/views.py — Signing in by emailed link, and the account page.

* ``sign_in`` asks for an email and sends a link; ``check_email`` says so.
* ``verify`` is the link itself: it signs the person in and, the first
  time, asks what friends should call them (``welcome``).
* ``account_settings`` edits the name and the evening email; it also holds
  sign-out and account deletion.
* ``stop_evening_email`` is the one-tap opt-out from the email footer.
* ``welcome`` asks a new account its name, then ``passkey_welcome``
  suggests a passkey, once.
* The ``passkey_*`` views back the browser's WebAuthn calls (see
  ``passkeys.py``, ported from Tally): JSON in, JSON out, except removing
  one, which is a form.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from mcp_auth.policy import can_connect

from apps.core.ratelimit import client_ip, over_limit
from apps.tour.session import after_welcome

from . import passkeys
from .forms import NameForm, ProfileForm, SignInForm
from .models import Passkey, User
from .services import (
    InvalidLink,
    read_sign_in_token,
    read_unsubscribe_token,
    safe_next,
    send_sign_in_email,
    sign_in_allowed,
    sign_in_url,
)

logger = logging.getLogger(__name__)


def current_user(request: HttpRequest) -> User:
    """Return the signed-in user, typed (callers are behind login_required)."""
    user = request.user
    if not isinstance(user, User):  # pragma: no cover — login_required runs first
        raise PermissionDenied
    return user


MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"
# Passkey requests per address per ten minutes, as in Tally.
PASSKEY_LIMIT = 30

# Session key holding the last link, shown on the page in DEBUG only.
DEBUG_LINK_KEY = "debug_sign_in_link"


def sign_in(request: HttpRequest) -> HttpResponse:
    """Ask for an email address and send a sign-in link to it."""
    next_url = safe_next(request.POST.get("next") or request.GET.get("next"), request)
    if request.user.is_authenticated:
        return redirect(next_url)
    form = SignInForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        if not sign_in_allowed(email):
            form.add_error("email", "Too many links sent to this address. Try again later.")
        else:
            link = sign_in_url(request, email, next_url)
            send_sign_in_email(email, link)
            request.session["sign_in_email"] = email
            if settings.DEBUG:
                request.session[DEBUG_LINK_KEY] = link
            return redirect("accounts:check_email")
    return render(request, "accounts/sign_in.html", {"form": form, "next_url": next_url})


def check_email(request: HttpRequest) -> HttpResponse:
    """Tell the person to open the link in their email."""
    return render(
        request,
        "accounts/check_email.html",
        {
            "email": request.session.get("sign_in_email", ""),
            "debug_link": request.session.get(DEBUG_LINK_KEY) if settings.DEBUG else "",
        },
    )


def verify(request: HttpRequest, token: str) -> HttpResponse:
    """Sign in with an emailed link, creating the account the first time."""
    try:
        result = read_sign_in_token(token)
    except InvalidLink as exc:
        return render(request, "accounts/link_invalid.html", {"reason": str(exc)}, status=400)
    login(request, result.user, backend=MODEL_BACKEND)
    request.session.pop(DEBUG_LINK_KEY, None)
    next_url = safe_next(result.next_url, request)
    if not result.user.display_name:
        query = urlencode({"next": next_url})
        return redirect(f"{reverse('accounts:welcome')}?{query}")
    return redirect(next_url)


@login_required
def welcome(request: HttpRequest) -> HttpResponse:
    """Ask a new account what friends should call them."""
    next_url = safe_next(request.POST.get("next") or request.GET.get("next"), request)
    form = NameForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        # The tour is offered next, once (apps/tour/session.py).
        query = urlencode({"next": after_welcome(request, next_url)})
        return redirect(f"{reverse('accounts:passkey_welcome')}?{query}")
    return render(request, "accounts/welcome.html", {"form": form, "next_url": next_url})


@login_required
def account_settings(request: HttpRequest) -> HttpResponse:
    """Edit the name friends see and the evening email."""
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("accounts:settings")
    return render(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "passkeys": Passkey.objects.for_user(current_user(request)),
            "can_connect_apps": can_connect(request.user),
        },
    )


@require_POST
def sign_out(request: HttpRequest) -> HttpResponse:
    """Sign out and go to the front page.

    The page drops the service worker's cached pages before the form posts
    (``data-sign-out`` in pwa.js). There is no ``Clear-Site-Data: "cache"``
    here: Chrome on Android held the redirect while it cleared the cache,
    so the button looked dead until the page was refreshed.
    """
    logout(request)
    return redirect("public:home")


@login_required
def delete_account(request: HttpRequest) -> HttpResponse:
    """Confirm, then delete the account and everything it owns."""
    if request.method == "POST":
        user = current_user(request)
        logout(request)
        user.delete()
        messages.success(request, "Your account and your plans are deleted.")
        return redirect("public:home")
    return render(request, "accounts/delete.html")


def stop_evening_email(request: HttpRequest, token: str) -> HttpResponse:
    """Turn the evening email off from its footer link (POST to confirm)."""
    try:
        user = read_unsubscribe_token(token)
    except InvalidLink as exc:
        return render(request, "accounts/link_invalid.html", {"reason": str(exc)}, status=400)
    done = request.method == "POST"
    if done and user.evening_email_enabled:
        user.evening_email_enabled = False
        user.save(update_fields=["evening_email_enabled", "updated_at"])
    return render(request, "accounts/stop_evening_email.html", {"done": done, "person": user})


def _json_body(request: HttpRequest) -> dict[str, Any] | None:
    """Return the request's JSON object, or None if it isn't one."""
    try:
        data = json.loads(request.body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _login_required_json(
    view: Callable[..., JsonResponse],
) -> Callable[..., HttpResponse]:
    """Answer a signed-out request with 401 JSON instead of a redirect."""

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "signed_out"}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


def _wrong_host(request: HttpRequest) -> JsonResponse | None:
    """Refuse passkey options the browser would reject for this page's host.

    Without this the browser fails the ceremony on its own and the server
    never hears of it; here the misconfiguration lands in the log.
    """
    host = request.get_host().partition(":")[0]
    if passkeys.serves_host(host):
        return None
    logger.error(
        "passkeys.wrong_host host=%s rp_id=%s: set SITE_URL to this site's address",
        host,
        settings.WEBAUTHN_RP_ID,
    )
    return JsonResponse({"error": "wrong_host"}, status=409)


def _passkey_rate_limited(request: HttpRequest) -> bool:
    """Count a passkey request from this address; True once over the limit."""
    return over_limit("passkey-ip", client_ip(request), limit=PASSKEY_LIMIT, window_seconds=600)


@require_POST
def passkey_sign_in_options(request: HttpRequest) -> JsonResponse:
    """Return a challenge for ``navigator.credentials.get()``."""
    if _passkey_rate_limited(request):
        return JsonResponse({"error": "rate_limited"}, status=429)
    if refusal := _wrong_host(request):
        return refusal
    return JsonResponse(passkeys.sign_in_options(request.session))


@require_POST
def passkey_sign_in(request: HttpRequest) -> JsonResponse:
    """Verify a passkey and sign its owner in.

    The body is ``{"credential": <the credential's JSON>, "next": <path>}``.
    An unknown passkey answers 404 with its id, so the page can tell the
    browser to forget it (``PublicKeyCredential.signalUnknownCredential``).
    """
    data = _json_body(request)
    if data is None or not isinstance(data.get("credential"), dict):
        return JsonResponse({"error": "bad_request"}, status=400)
    try:
        user = passkeys.authenticate(json.dumps(data["credential"]), request.session)
    except passkeys.UnknownPasskeyError as exc:
        return JsonResponse(
            {"error": "unknown_passkey", "credentialId": exc.credential_id}, status=404
        )
    except passkeys.PasskeyError as exc:
        logger.info("passkeys.sign_in_failed %s", exc)
        return JsonResponse({"error": "not_verified"}, status=400)
    if not user.is_active:
        return JsonResponse({"error": "account_disabled"}, status=403)
    login(request, user, backend=MODEL_BACKEND)
    raw_next = data.get("next")
    next_url = safe_next(raw_next if isinstance(raw_next, str) else None, request)
    if not user.display_name:
        next_url = f"{reverse('accounts:welcome')}?{urlencode({'next': next_url})}"
    return JsonResponse({"next": next_url})


@login_required
@require_GET
def passkey_welcome(request: HttpRequest) -> HttpResponse:
    """Suggest a passkey to a new account, once; anyone with one goes straight on."""
    next_url = safe_next(request.GET.get("next"), request)
    if Passkey.objects.for_user(current_user(request)).exists():
        return redirect(next_url)
    return render(request, "accounts/passkey_welcome.html", {"next_url": next_url})


@require_POST
@_login_required_json
def passkey_register_options(request: HttpRequest) -> JsonResponse:
    """Return a challenge for ``navigator.credentials.create()``."""
    if refusal := _wrong_host(request):
        return refusal
    return JsonResponse(passkeys.registration_options(current_user(request), request.session))


@require_POST
@_login_required_json
def passkey_register(request: HttpRequest) -> JsonResponse:
    """Verify a new passkey and save it. The body is the credential's JSON."""
    if _passkey_rate_limited(request):
        return JsonResponse({"error": "rate_limited"}, status=429)
    if _json_body(request) is None:
        return JsonResponse({"error": "bad_request"}, status=400)
    name = passkeys.default_name(request.headers.get("User-Agent", ""))
    try:
        passkey = passkeys.register(
            request.body.decode(), request.session, current_user(request), name
        )
    except passkeys.PasskeyError as exc:
        logger.info("passkeys.register_failed %s", exc)
        return JsonResponse({"error": "not_verified"}, status=400)
    return JsonResponse({"uuid": str(passkey.uuid), "name": passkey.name}, status=201)


@login_required
@require_POST
def passkey_delete(request: HttpRequest, passkey_uuid: str) -> HttpResponse:
    """Remove one of the signed-in person's passkeys."""
    passkey = get_object_or_404(Passkey.objects.for_user(current_user(request)), uuid=passkey_uuid)
    passkey.delete()
    messages.success(
        request,
        "Passkey removed. Also delete it from your password manager or device.",
    )
    return redirect("accounts:settings")
