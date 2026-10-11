"""
apps/accounts/views.py — Signing in by emailed link, and the account page.

* ``sign_in`` asks for an email and sends a link; ``check_email`` says so.
* ``verify`` is the link itself: it signs the person in and, the first
  time, asks what friends should call them (``welcome``).
* ``account_settings`` edits the name and the evening email; it also holds
  sign-out and account deletion.
* ``stop_evening_email`` is the one-tap opt-out from the email footer.
* The ``passkey_*`` views back the browser's WebAuthn calls (see
  ``passkeys.py``): JSON in, JSON out, except removing one, which is a form.
"""

from __future__ import annotations

import json
import logging
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
            form.add_error(
                "email", "Too many links sent to this address. Try again later."
            )
        else:
            link = sign_in_url(request, email, next_url)
            send_sign_in_email(email, link)
            request.session["sign_in_email"] = email
            if settings.DEBUG:
                request.session[DEBUG_LINK_KEY] = link
            return redirect("accounts:check_email")
    return render(
        request, "accounts/sign_in.html", {"form": form, "next_url": next_url}
    )


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
        return render(
            request, "accounts/link_invalid.html", {"reason": str(exc)}, status=400
        )
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
        return redirect(next_url)
    return render(
        request, "accounts/welcome.html", {"form": form, "next_url": next_url}
    )


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
        },
    )


@require_POST
def sign_out(request: HttpRequest) -> HttpResponse:
    """Sign out, wipe this device's cached pages, and go to the front page."""
    logout(request)
    response = redirect("core:home")
    response["Clear-Site-Data"] = '"cache"'
    return response


@login_required
def delete_account(request: HttpRequest) -> HttpResponse:
    """Confirm, then delete the account and everything it owns."""
    if request.method == "POST":
        user = current_user(request)
        logout(request)
        user.delete()
        messages.success(request, "Your account and your plans are deleted.")
        return redirect("core:home")
    return render(request, "accounts/delete.html")


def stop_evening_email(request: HttpRequest, token: str) -> HttpResponse:
    """Turn the evening email off from its footer link (POST to confirm)."""
    try:
        user = read_unsubscribe_token(token)
    except InvalidLink as exc:
        return render(
            request, "accounts/link_invalid.html", {"reason": str(exc)}, status=400
        )
    done = request.method == "POST"
    if done and user.evening_email_enabled:
        user.evening_email_enabled = False
        user.save(update_fields=["evening_email_enabled", "updated_at"])
    return render(
        request, "accounts/stop_evening_email.html", {"done": done, "person": user}
    )


def _json_body(request: HttpRequest) -> dict[str, object]:
    """Return the request's JSON object body, or an empty dict if it isn't one."""
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


@require_GET
def passkey_sign_in_options(request: HttpRequest) -> JsonResponse:
    """Start a passkey sign-in: return the browser's request options."""
    return JsonResponse(passkeys.authentication_options(request.session))


@require_POST
def passkey_sign_in(request: HttpRequest) -> JsonResponse:
    """Finish a passkey sign-in and say where to go next."""
    body = _json_body(request)
    raw_next = body.get("next")
    next_url = safe_next(raw_next if isinstance(raw_next, str) else None, request)
    try:
        user = passkeys.verify_authentication(
            json.dumps(body.get("credential")), request.session
        )
    except passkeys.PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    login(request, user, backend=MODEL_BACKEND)
    if not user.display_name:
        next_url = f"{reverse('accounts:welcome')}?{urlencode({'next': next_url})}"
    return JsonResponse({"next": next_url})


@login_required
@require_GET
def passkey_add_options(request: HttpRequest) -> JsonResponse:
    """Start adding a passkey: return the browser's creation options."""
    return JsonResponse(
        passkeys.registration_options(current_user(request), request.session)
    )


@login_required
@require_POST
def passkey_add(request: HttpRequest) -> JsonResponse:
    """Finish adding a passkey to the signed-in account."""
    body = _json_body(request)
    try:
        passkey = passkeys.save_registration(
            current_user(request), json.dumps(body.get("credential")), request.session
        )
    except passkeys.PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    messages.success(request, "Passkey added. Next time, sign in with it.")
    return JsonResponse({"name": passkey.name})


@login_required
@require_POST
def passkey_remove(request: HttpRequest, passkey_uuid: str) -> HttpResponse:
    """Remove one of the signed-in person's passkeys."""
    passkey = get_object_or_404(
        Passkey.objects.for_user(current_user(request)), uuid=passkey_uuid
    )
    passkey.delete()
    messages.success(
        request,
        "Passkey removed. Also delete it from your password manager or device.",
    )
    return redirect("accounts:settings")
