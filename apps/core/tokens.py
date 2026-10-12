"""
apps/core/tokens.py — Unguessable tokens for share and invite links.

One helper so every share and invite link mints tokens the same way.
"""

import secrets

# 32 bytes of entropy, URL-safe base64 encoded: 43 characters.
TOKEN_BYTES: int = 32
TOKEN_LENGTH: int = 43


def make_token() -> str:
    """Return a new URL-safe random token for a share or invite link."""
    return secrets.token_urlsafe(TOKEN_BYTES)
