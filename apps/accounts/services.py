"""apps/accounts/services.py — The evening email's one-tap opt-out link.

The link is a signed token naming the account, so it works without
signing in. Signing in itself is ``sign_in.py``.
"""

from __future__ import annotations

from django.core import signing

from .models import User

UNSUBSCRIBE_SALT = "accounts.evening-email-stop"


class InvalidLink(Exception):
    """An opt-out link is malformed, or its account is gone."""


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
