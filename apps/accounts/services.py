"""
apps/accounts/services.py — Emailed sign-in links and email opt-outs.

Nobody has a password. Signing in asks for an email address and sends a
link; opening the link signs the person in, creating their account the
first time. The link is a signed token that carries the email, where to
go next, and the account's last sign-in time, so it stops working as soon
as it (or any other link) has been used, and after ``SIGN_IN_LINK_MAX_AGE``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import User, normalise_email

logger = logging.getLogger(__name__)

SIGN_IN_SALT = "accounts.sign-in"
UNSUBSCRIBE_SALT = "accounts.evening-email-stop"
# At most this many sign-in emails per address per window.
SIGN_IN_LIMIT = 5
SIGN_IN_WINDOW_SECONDS = 60 * 60


class InvalidLink(Exception):
    """A sign-in or opt-out link is malformed, expired or already used."""


@dataclass(frozen=True)
class SignIn:
    """What a valid sign-in link resolves to."""

    user: User
    next_url: str
    created: bool


def safe_next(next_url: str | None, request: HttpRequest) -> str:
    """Return ``next_url`` if it stays on this site, else the default page."""
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse(settings.LOGIN_REDIRECT_URL)


def _last_login_stamp(user: User | None) -> str:
    """Return the value that ties a link to the account's current state."""
    if user is None or user.last_login is None:
        return ""
    return user.last_login.isoformat()


def make_sign_in_token(email: str, next_url: str) -> str:
    """Return a signed token for a sign-in link to ``email``."""
    email = normalise_email(email)
    user = User.objects.filter(email=email).first()
    payload = {"e": email, "n": next_url, "l": _last_login_stamp(user)}
    return signing.dumps(payload, salt=SIGN_IN_SALT)


def read_sign_in_token(token: str) -> SignIn:
    """
    Resolve a sign-in token to its account, creating the account if needed.

    Raises ``InvalidLink`` when the token is bad, expired or already used.
    """
    try:
        payload = signing.loads(
            token, salt=SIGN_IN_SALT, max_age=settings.SIGN_IN_LINK_MAX_AGE
        )
        email = normalise_email(payload["e"])
        next_url = str(payload["n"])
        stamp = str(payload["l"])
    except (signing.BadSignature, KeyError, TypeError) as exc:
        raise InvalidLink("This sign-in link is not valid.") from exc
    user = User.objects.filter(email=email).first()
    if stamp != _last_login_stamp(user):
        raise InvalidLink("This sign-in link has already been used.")
    if user is not None and not user.is_active:
        raise InvalidLink("This account is switched off.")
    created = user is None
    if user is None:
        user = User.objects.create_user(email=email)
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return SignIn(user=user, next_url=next_url, created=created)


def sign_in_allowed(email: str) -> bool:
    """Count a sign-in email to ``email``; return False once over the limit."""
    key = f"sign-in-count:{normalise_email(email)}"
    cache.add(key, 0, SIGN_IN_WINDOW_SECONDS)
    try:
        count = cache.incr(key)
    except ValueError:  # the key expired between add and incr
        cache.set(key, 1, SIGN_IN_WINDOW_SECONDS)
        count = 1
    return count <= SIGN_IN_LIMIT


def sign_in_url(request: HttpRequest, email: str, next_url: str) -> str:
    """Return the absolute sign-in link for ``email``."""
    token = make_sign_in_token(email, next_url)
    path = reverse("accounts:verify", kwargs={"token": token})
    return request.build_absolute_uri(path)


def send_sign_in_email(email: str, link: str) -> None:
    """Email the sign-in link to ``email``."""
    context = {"link": link, "SITE_NAME": settings.SITE_NAME}
    send_mail(
        subject=f"Your sign-in link for {settings.SITE_NAME}",
        message=render_to_string("accounts/email/sign_in.txt", context),
        html_message=render_to_string("accounts/email/sign_in.html", context),
        from_email=None,
        recipient_list=[normalise_email(email)],
    )
    logger.info("Sent a sign-in link")


def make_unsubscribe_token(user: User) -> str:
    """Return a signed token that turns ``user``'s evening email off."""
    return signing.dumps(str(user.uuid), salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token: str) -> User:
    """Return the user an opt-out token names, or raise ``InvalidLink``."""
    try:
        key = signing.loads(token, salt=UNSUBSCRIBE_SALT)
        return User.objects.get(uuid=key)
    except (signing.BadSignature, User.DoesNotExist, ValueError) as exc:
        raise InvalidLink("This link is not valid.") from exc
