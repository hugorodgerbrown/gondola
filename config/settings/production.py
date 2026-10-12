"""
config/settings/production.py — Production hardening.

``DJANGO_SECRET_KEY`` (or ``SECRET_KEY``) and ``DATABASE_URL`` must be set
in the environment; ``base`` reads them and works out the allowed hosts.
"""

from .base import *  # noqa: F403 — settings overlay pattern

DEBUG = False

# No SQLite fallback here: a missing DATABASE_URL stops the deploy rather
# than quietly writing to a throwaway file on the dyno.
DATABASES = {
    "default": dj_database_url.parse(  # noqa: F405 — from base
        config("DATABASE_URL"),  # noqa: F405
        conn_max_age=600,
    )
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Render's health check calls /livez over plain HTTP inside its network.
SECURE_REDIRECT_EXEMPT = [r"^livez$", r"^healthz$"]
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
