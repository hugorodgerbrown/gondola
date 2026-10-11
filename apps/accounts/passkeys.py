"""
apps/accounts/passkeys.py — Sign in with a passkey (WebAuthn).

A passkey sits alongside the emailed link, never instead of it: someone
signs in by link once, adds a passkey on the account page, and from then
on Face ID, Touch ID or their password manager signs them in on that
device. A passkey stands in for the email, so it must check who is
holding the device: user verification (Face ID, a PIN) is required, never
just a touch. Wraps py_webauthn in four steps, two per ceremony:

  registration_options / save_registration      add a passkey
  authentication_options / verify_authentication  sign in with one

Each "options" step stores its challenge in the session and the matching
"verify" step pops it, so a challenge is used at most once. The relying
party is this site: ``WEBAUTHN_RP_ID`` and ``WEBAUTHN_ORIGIN`` default to
``SITE_URL``'s host and origin.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, cast

import webauthn
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.utils import timezone
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import Passkey, User

logger = logging.getLogger(__name__)

REGISTRATION_CHALLENGE_KEY = "passkey_registration_challenge"
AUTHENTICATION_CHALLENGE_KEY = "passkey_authentication_challenge"


class PasskeyError(Exception):
    """A passkey could not be added or used to sign in."""


def _descriptors(user: User) -> list[PublicKeyCredentialDescriptor]:
    """Return ``user``'s passkeys in the form WebAuthn options expect."""
    return [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(key.credential_id))
        for key in Passkey.objects.for_user(user)
    ]


def _as_dict(options: Any) -> dict[str, Any]:
    """Return WebAuthn options as the JSON the browser parses."""
    return cast(dict[str, Any], json.loads(options_to_json(options)))


def registration_options(user: User, session: SessionBase) -> dict[str, Any]:
    """
    Return the options for adding a passkey to ``user``'s account.

    The user handle is a hash of the primary key: stable, and not the email.
    Existing passkeys are excluded, so a device that already has one says
    so instead of making a second.
    """
    options = webauthn.generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.SITE_NAME,
        user_id=hashlib.sha256(str(user.pk).encode()).digest(),
        user_name=user.email,
        user_display_name=user.to_string(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=_descriptors(user),
    )
    session[REGISTRATION_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
    return _as_dict(options)


def _default_name(backed_up: bool) -> str:
    """Name a new passkey by how it is kept: synced, or bound to one device."""
    return "Synced passkey" if backed_up else "Device passkey"


def save_registration(
    user: User, credential_json: str, session: SessionBase
) -> Passkey:
    """Verify the browser's new credential and store it for ``user``."""
    challenge = session.pop(REGISTRATION_CHALLENGE_KEY, None)
    if not challenge:
        raise PasskeyError("No passkey request is waiting. Try again.")
    try:
        result = webauthn.verify_registration_response(
            credential=credential_json,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            require_user_verification=True,
        )
    except Exception as exc:  # py_webauthn raises several unrelated types
        logger.info("Passkey registration did not verify: %s", exc)
        raise PasskeyError("That passkey could not be checked. Try again.") from exc
    credential_id = bytes_to_base64url(result.credential_id)
    if Passkey.objects.filter(credential_id=credential_id).exists():
        raise PasskeyError("That passkey is already on an account.")
    passkey = Passkey.objects.create(
        user=user,
        credential_id=credential_id,
        public_key=result.credential_public_key,
        sign_count=result.sign_count,
        backed_up=result.credential_backed_up,
        name=_default_name(result.credential_backed_up),
    )
    logger.info("Passkey added for user %s", user.pk)
    return passkey


def authentication_options(session: SessionBase) -> dict[str, Any]:
    """
    Return the options for signing in with any passkey for this site.

    No credentials are listed, so the browser offers every passkey it holds
    for this site, including in the email field's autofill.
    """
    options = webauthn.generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session[AUTHENTICATION_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
    return _as_dict(options)


def verify_authentication(credential_json: str, session: SessionBase) -> User:
    """Verify a passkey sign-in and return the account it belongs to."""
    challenge = session.pop(AUTHENTICATION_CHALLENGE_KEY, None)
    if not challenge:
        raise PasskeyError("No sign-in is waiting. Try again.")
    try:
        credential_id = str(json.loads(credential_json)["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise PasskeyError("That sign-in could not be read.") from exc
    passkey = (
        Passkey.objects.select_related("user")
        .filter(credential_id=credential_id)
        .first()
    )
    if passkey is None:
        raise PasskeyError(
            "That passkey isn't on any account. It may have been removed."
        )
    try:
        result = webauthn.verify_authentication_response(
            credential=credential_json,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:  # py_webauthn raises several unrelated types
        logger.info("Passkey sign-in did not verify: %s", exc)
        raise PasskeyError("That passkey could not be checked. Try again.") from exc
    if not passkey.user.is_active:
        raise PasskeyError("This account is switched off.")
    passkey.sign_count = result.new_sign_count
    passkey.backed_up = result.credential_backed_up
    passkey.last_used_at = timezone.now()
    passkey.save(
        update_fields=["sign_count", "backed_up", "last_used_at", "updated_at"]
    )
    return passkey.user
