"""
config/settings/base.py — Settings shared by every environment.

Environment overlays (``development``, ``production``) import from here and
override what differs. Secrets come from the environment via
``python-decouple``; nothing sensitive is hard-coded.
"""

from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# The DJANGO_* names are the ones titan (the Titan provisioner) writes;
# the bare names are what the first deployment set, and still work.
SECRET_KEY = config("DJANGO_SECRET_KEY", default="") or config("SECRET_KEY")
DEBUG = config(
    "DJANGO_DEBUG", default=config("DEBUG", default=False, cast=bool), cast=bool
)
ALLOWED_HOSTS: list[str] = [
    *config("ALLOWED_HOSTS", default="", cast=Csv()),
    *config("DJANGO_ALLOWED_HOSTS", default="", cast=Csv()),
]
# Render sets this to the service's onrender.com name, so the service always
# answers there, before and after a custom domain is added.
if RENDER_EXTERNAL_HOSTNAME := config("RENDER_EXTERNAL_HOSTNAME", default=""):
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.resorts",
    "apps.groups",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

# SQLite unless DATABASE_URL is set (production sets it to Postgres).
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

_VALIDATORS = "django.contrib.auth.password_validation"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"{_VALIDATORS}.UserAttributeSimilarityValidator"},
    {"NAME": f"{_VALIDATORS}.MinimumLengthValidator"},
    {"NAME": f"{_VALIDATORS}.CommonPasswordValidator"},
    {"NAME": f"{_VALIDATORS}.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
# Every resort is Swiss, so plan dates and meet-up times are Swiss wall-clock.
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# The product name shown in the header, page titles and emails.
SITE_NAME = config("SITE_NAME", default="Gondola")
# Absolute origin for links in emails sent outside a request (the evening
# email runs from a scheduled command), e.g. https://planner.example.com
SITE_URL = config("SITE_URL", default="http://localhost:8000")
# Whatever address SITE_URL names, when set, is one the site answers on.
_site_host = urlsplit(config("SITE_URL", default="")).hostname
if _site_host and _site_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_site_host)

# Signing in is an emailed link; there are no passwords for people.
LOGIN_URL = "accounts:sign_in"
LOGIN_REDIRECT_URL = "planning:map"
# How long an emailed sign-in link works, in seconds.
SIGN_IN_LINK_MAX_AGE = 60 * 30

# Passkeys (WebAuthn), as in Tally. The relying party is this site's host
# name; a passkey only works on the host it was made for. Both default to
# SITE_URL, so SITE_URL must be the address people use.
WEBAUTHN_RP_ID: str = config(
    "WEBAUTHN_RP_ID", default=urlsplit(SITE_URL).hostname or "localhost"
)
WEBAUTHN_RP_NAME = SITE_NAME
WEBAUTHN_ORIGINS: list[str] = config(
    "WEBAUTHN_ORIGINS",
    default=f"{urlsplit(SITE_URL).scheme}://{urlsplit(SITE_URL).netloc}",
    cast=Csv(),
)

# Rate limits count per client address. Behind Render's proxy the client is
# the last X-Forwarded-For entry; locally there is no proxy.
RATE_LIMIT_PROXY_COUNT: int = config(
    "RATE_LIMIT_PROXY_COUNT", default=0 if DEBUG else 1, cast=int
)

# Django 6.1's MAILERS replaces the EMAIL_* settings. Production sends
# through SMTP (a relay such as Resend); development prints to the console.
MAILERS = {
    "default": {
        "BACKEND": config(
            "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
        ),
        "OPTIONS": {
            "host": config("EMAIL_HOST", default="localhost"),
            "port": config("EMAIL_PORT", default=1025, cast=int),
            "username": config("EMAIL_HOST_USER", default=""),
            "password": config("EMAIL_HOST_PASSWORD", default=""),
            "use_tls": config("EMAIL_USE_TLS", default=False, cast=bool),
        },
    }
}
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="planner@localhost")

# The basemap. Any MapLibre style URL; empty draws the built-in plain map
# (Switzerland's outline only), which is also the fallback when it fails.
# The default is swisstopo's winter base map, which needs no key.
# It covers Switzerland only, which is every resort here.
MAP_STYLE_URL = config(
    "MAP_STYLE_URL",
    default=(
        "https://vectortiles.geo.admin.ch/styles/"
        "ch.swisstopo.basemap-winter.vt/style.json"
    ),
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
