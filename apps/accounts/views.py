"""apps/accounts/views.py — Signing in by emailed link or code, and the account page.

* ``sign_in`` asks for an email and sends a link and a six-digit code;
  ``sign_in_code`` says so and takes the code.
* ``sign_in_link`` is the link itself: a Continue button whose POST signs
  in. It asks for a click because mail scanners open links to check them,
  and would use the link up.
* Signing in the first time asks what friends should call them
  (``welcome``), then suggests a passkey (``passkey_welcome``), once.
* ``account_settings`` edits the name and the evening email; it also holds
  sign-out and account deletion.
* ``stop_evening_email`` is the one-tap opt-out from the email footer.
* ``admin_login`` sends the admin's password form to the normal sign-in.
* The ``passkey_*`` views back the browser's WebAuthn calls (see
  ``passkeys.py``, ported from Tally): JSON in, JSON out, except removing
  one, which is a form.

See docs/accounts.md.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from mcp_auth.policy import can_connect

from apps.core.decorators import login_required_json
from apps.core.ratelimit import client_ip, over_limit
from apps.core.redirects import safe_next
from apps.core.shortcuts import render
from apps.tour.session import after_welcome

from . import passkeys, sign_in
from .forms import CodeForm, NameForm, ProfileForm, SignInForm
from .models import Passkey, SignInRequest, User
from .services import InvalidLink, read_unsubscribe_token
from .tasks import send_sign_in_email

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

# The session remembers which request this browser started, so its code
# only works here.
SESSION_REQUEST = "accounts.sign_in_request"
SESSION_EMAIL = "accounts.sign_in_email"
# The last link, shown on the code page in DEBUG only.
DEBUG_LINK_KEY = "debug_sign_in_link"


def _minutes() -> int:
    """How long a sign-in email works, for the pages that say so."""
    return int(settings.SIGN_IN_MAX_AGE_SECONDS // 60)


def _link_invalid(request: HttpRequest) -> HttpResponse:
    """Say a sign-in link is used up or out of date."""
    return render(request, "accounts/link_invalid.html", {"minutes": _minutes()}, status=410)


def _after_sign_in(request: HttpRequest, user: User, next_url: str | None) -> str:
    """Return where a freshly signed-in user goes: their name first, if it's missing."""
    url = safe_next(request, next_url)
    if not user.display_name:
        return f"{reverse('accounts:welcome')}?{urlencode({'next': url})}"
    return url


def _complete_sign_in(request: HttpRequest, sign_in_request: SignInRequest) -> HttpResponse:
    """Sign in the account a redeemed request belongs to, and send it on."""
    user = sign_in.user_for(sign_in_request)
    if user is None:
        return render(request, "accounts/account_disabled.html", status=403)
    login(request, user, backend=MODEL_BACKEND)
    for key in (SESSION_REQUEST, SESSION_EMAIL, DEBUG_LINK_KEY):
        request.session.pop(key, None)
    return redirect(_after_sign_in(request, user, sign_in_request.next_url))


@never_cache
@require_http_methods(["GET", "POST"])
def sign_in_view(request: HttpRequest) -> HttpResponse:
    """Ask for an email address and send it a sign-in link and code."""
    next_url = safe_next(request, request.POST.get("next") or request.GET.get("next"))
    if request.user.is_authenticated and request.method == "GET":
        return redirect(next_url)
    form = SignInForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        if over_limit("sign-in-ip", client_ip(request), limit=10, window_seconds=600) or (
            over_limit("sign-in-email", email, limit=5, window_seconds=3600)
        ):
            form.add_error("email", "Too many sign-in emails. Wait a few minutes and try again.")
            status = 429
        else:
            sign_in_request, token, code = sign_in.issue(email, next_url)
            link = request.build_absolute_uri(reverse("accounts:sign_in_link", args=[token]))
            # A reviewer account has no inbox: the reviewer types its fixed code.
            if sign_in.reviewer_code(email) is None:
                send_sign_in_email.enqueue(email=email, link=link, code=code)
            request.session[SESSION_REQUEST] = str(sign_in_request.uuid)
            request.session[SESSION_EMAIL] = email
            if settings.DEBUG:
                request.session[DEBUG_LINK_KEY] = link
            return redirect("accounts:sign_in_code")
    elif request.method == "POST":
        status = 400
    return render(
        request, "accounts/sign_in.html", {"form": form, "next_url": next_url}, status=status
    )


@never_cache
@require_http_methods(["GET", "POST"])
def sign_in_code(request: HttpRequest) -> HttpResponse:
    """Tell the person to check their email, and take the code from it."""
    request_uuid = request.session.get(SESSION_REQUEST)
    if not request_uuid:
        return redirect("accounts:sign_in")
    form = CodeForm(request.POST or None)
    status = 200
    if request.method == "POST":
        status = 400
        if over_limit("sign-in-code-ip", client_ip(request), limit=20, window_seconds=600):
            form.add_error(None, "Too many attempts. Wait a few minutes, or use the link.")
            status = 429
        elif form.is_valid():
            redeemed = sign_in.redeem_code(request_uuid, form.cleaned_data["code"])
            if redeemed is not None:
                return _complete_sign_in(request, redeemed)
            form.add_error(
                "code", "That code didn't work. Check the newest email, or use its link."
            )
    context = {
        "form": form,
        "email": request.session.get(SESSION_EMAIL, ""),
        "minutes": _minutes(),
        "debug_link": request.session.get(DEBUG_LINK_KEY) if settings.DEBUG else "",
    }
    return render(request, "accounts/sign_in_code.html", context, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
def sign_in_link(request: HttpRequest, token: str) -> HttpResponse:
    """Show a Continue button for an emailed link; the POST signs in."""
    if request.method == "GET":
        pending = sign_in.find_by_token(token)
        if pending is None:
            return _link_invalid(request)
        return render(request, "accounts/sign_in_link.html", {"email": pending.email})
    redeemed = sign_in.redeem_token(token)
    if redeemed is None:
        return _link_invalid(request)
    return _complete_sign_in(request, redeemed)


def admin_login(request: HttpRequest) -> HttpResponse:
    """Send the admin's password form to the normal sign-in.

    Staff sign in like everyone else; a signed-in user who isn't staff is
    refused here rather than sent round in a loop.
    """
    if request.user.is_authenticated:
        raise PermissionDenied
    query = urlencode({"next": request.GET.get("next", reverse("admin:index"))})
    return redirect(f"{reverse('accounts:sign_in')}?{query}")


@login_required
def welcome(request: HttpRequest) -> HttpResponse:
    """Ask a new account what friends should call them."""
    next_url = safe_next(request, request.POST.get("next") or request.GET.get("next"))
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
    next_url = raw_next if isinstance(raw_next, str) else None
    return JsonResponse({"next": _after_sign_in(request, user, next_url)})


@login_required
@require_GET
def passkey_welcome(request: HttpRequest) -> HttpResponse:
    """Suggest a passkey to a new account, once; anyone with one goes straight on."""
    next_url = safe_next(request, request.GET.get("next"))
    if Passkey.objects.for_user(current_user(request)).exists():
        return redirect(next_url)
    return render(request, "accounts/passkey_welcome.html", {"next_url": next_url})


@require_POST
@login_required_json
def passkey_register_options(request: HttpRequest) -> JsonResponse:
    """Return a challenge for ``navigator.credentials.create()``."""
    if refusal := _wrong_host(request):
        return refusal
    return JsonResponse(passkeys.registration_options(current_user(request), request.session))


@require_POST
@login_required_json
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
