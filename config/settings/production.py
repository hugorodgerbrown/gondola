"""
config/settings/production.py — Production hardening.

``SECRET_KEY``, ``ALLOWED_HOSTS`` and ``DATABASE_URL`` must be set in the
environment; ``base`` reads them.
"""

from .base import *  # noqa: F403 — settings overlay pattern

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS: list[str] = config(  # noqa: F405 — from base
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=Csv(),  # noqa: F405
)
