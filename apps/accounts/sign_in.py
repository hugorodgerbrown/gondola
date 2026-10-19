"""apps/accounts/sign_in.py — Issue an emailed link and code, redeem either once.

There is no separate sign-up. The first redeemed link or code for an
address creates its account; until then nothing is stored about it beyond
the pending request. See docs/accounts.md. Ported from the Titan template,
with the account found by email (Gondola's ``User`` has no username).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
<<<<<<< before updating
from django.db import IntegrityError, transaction
from django.db.models import F
=======
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F, Q
>>>>>>> after updating
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.accounts.models import ReviewerAccount, SignInRequest, User, normalise_email
from apps.core.tokens import make_token

logger = logging.getLogger(__name__)

CODE_DIGITS = 6
# Tries at storing a request when others for the address land at once.
ISSUE_ATTEMPTS = 5


def _hash_token(token: str) -> str:
    """Hash a link token for storage (it is random, so no salt is needed)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_code(request_uuid: str, code: str) -> str:
    """Hash a code with the server's secret, so the stored hash can't be brute-forced."""
    return salted_hmac(
        "accounts.sign_in.code", f"{request_uuid}:{code}", algorithm="sha256"
    ).hexdigest()


def reviewer_code(email: str) -> str | None:
    """Return the fixed code if ``email`` is a reviewer account's, else None.

    Reviewers have no inbox to read, so their address is sent no email and
    signs in with the code staff set up in the admin (see docs/accounts.md).
    """
    return ReviewerAccount.objects.for_email(email).values_list("code", flat=True).first()


def issue(email: str, next_url: str = "") -> tuple[SignInRequest, str, str]:
    """Create a sign-in request for ``email``; return it with its link token and code.

    Earlier unused requests for the same address stop working, so only the
    newest email in someone's inbox signs them in. The database allows one
    unused request per address: when two are issued at once, the loser of
    that race retries, closing the winner's request in turn. A reviewer
    account's address gets its fixed code (``reviewer_code``).
    """
    email = normalise_email(email)
    token = make_token()
    code = reviewer_code(email) or f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
<<<<<<< before updating
    for attempt in range(3):
        now = timezone.now()
=======
    # The database allows one unused request per address. Requests at the
    # same moment all find nothing to retire; each one that collides tries
    # again and retires the winner, so the newest still wins.
    for attempt in range(ISSUE_ATTEMPTS):
        try:
            request = _replace_request(email, token, code, next_url)
            break
        except IntegrityError:
            if attempt == ISSUE_ATTEMPTS - 1:
                raise
    return request, token, code


def _replace_request(email: str, token: str, code: str, next_url: str) -> SignInRequest:
    """Retire ``email``'s unused requests and store a new one, in one transaction."""
    now = timezone.now()
    with transaction.atomic():
        SignInRequest.objects.for_email(email).unused().update(used_at=now)
>>>>>>> after updating
        request = SignInRequest(
            email=email,
            token_hash=_hash_token(token),
            next_url=next_url[:2048],
            expires_at=now + timedelta(seconds=settings.SIGN_IN_MAX_AGE_SECONDS),
        )
        request.code_hash = _hash_code(str(request.uuid), code)
<<<<<<< before updating
        try:
            with transaction.atomic():
                SignInRequest.objects.for_email(email).filter(used_at__isnull=True).update(
                    used_at=now, updated_at=now
                )
                request.save()
        except IntegrityError:
            if attempt == 2:
                raise
            logger.info("accounts.sign_in.issue_race retry=%s", attempt + 1)
            continue
        return request, token, code
    raise AssertionError("unreachable")  # pragma: no cover
=======
        request.save()
    return request
>>>>>>> after updating


def _claim(request: SignInRequest) -> bool:
    """Mark ``request`` used, unless another redemption got there first."""
    claimed = (
        SignInRequest.objects.live()
        .filter(pk=request.pk)
        .update(used_at=timezone.now(), updated_at=timezone.now())
    )
    return claimed == 1


def find_by_token(token: str) -> SignInRequest | None:
    """Return the live request a link token belongs to, without using it up."""
    return SignInRequest.objects.live().filter(token_hash=_hash_token(token)).first()


def redeem_token(token: str) -> SignInRequest | None:
    """Use up a link token; return its request, or None if it is unknown, used or expired."""
    request = find_by_token(token)
    if request is None or not _claim(request):
        return None
    return request


def redeem_code(request_uuid: str, code: str) -> SignInRequest | None:
    """Use up a code typed in the browser that asked for it.

    Each code tried counts; after ``SIGN_IN_MAX_CODE_ATTEMPTS`` the request
    stops accepting codes (its link still works).
    """
    # Spend an attempt before checking: one conditional update, so parallel
    # guesses can't all read the same count and slip past the limit.
    spent = (
        SignInRequest.objects.live()
        .filter(uuid=request_uuid, code_attempts__lt=settings.SIGN_IN_MAX_CODE_ATTEMPTS)
        .update(code_attempts=F("code_attempts") + 1)
    )
    if not spent:
        return None
    request = SignInRequest.objects.get(uuid=request_uuid)
    expected = _hash_code(str(request.uuid), code.strip())
    if not hmac.compare_digest(expected, request.code_hash):
        return None
    if not _claim(request):
        return None
    return request


def user_for(request: SignInRequest) -> User | None:
    """Return the account for a redeemed request, creating it on first sign-in.

    Returns None for a switched-off account: it can't be signed back in by
    email.
    """
    user = User.objects.filter(email=normalise_email(request.email)).first()
    if user is None:
        user = User.objects.create_user(email=request.email)
        logger.info("accounts.created user=%s", user.pk)
    if not user.is_active:
        return None
    return user
