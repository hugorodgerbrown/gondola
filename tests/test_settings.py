"""Tests for the settings: the environment names titan writes."""

import importlib
from collections.abc import Callable, Iterator
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured

import config.settings

NAMES = (
    "SECRET_KEY",
    "DJANGO_SECRET_KEY",
    "DEBUG",
    "DJANGO_DEBUG",
    "ALLOWED_HOSTS",
    "DJANGO_ALLOWED_HOSTS",
    "RENDER_EXTERNAL_HOSTNAME",
    "SITE_URL",
    "CSRF_TRUSTED_ORIGINS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "FIVEBAR_DOMAIN",
    "RENDER",
    "DATABASE_URL",
)
# Production needs a database URL; tests that aren't about it get this one.
SQLITE = "sqlite:///settings-test.sqlite3"


@pytest.fixture
def load(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., ModuleType]]:
    """Reload the settings under a given environment, then restore them."""
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)

    def _load(**env: str) -> ModuleType:
        env.setdefault("DATABASE_URL", SQLITE)
        for key, value in env.items():
            if key == "DATABASE_URL" and not value:
                monkeypatch.delenv(key, raising=False)
                continue
            monkeypatch.setenv(key, value)
        return importlib.reload(config.settings)

    yield _load
    monkeypatch.undo()
    monkeypatch.setenv("SECRET_KEY", "restore")
    importlib.reload(config.settings)


def test_titan_names_win(load: Callable[..., ModuleType]) -> None:
    """DJANGO_SECRET_KEY and DJANGO_DEBUG take over from the bare names."""
    base = load(SECRET_KEY="old", DJANGO_SECRET_KEY="new", DEBUG="1", DJANGO_DEBUG="0")
    assert base.SECRET_KEY == "new"
    assert base.DEBUG is False


def test_bare_names_still_work(load: Callable[..., ModuleType]) -> None:
    """The first deployment's SECRET_KEY and DEBUG keep working."""
    base = load(SECRET_KEY="old", DEBUG="1")
    assert base.SECRET_KEY == "old"
    assert base.DEBUG is True


def test_debug_is_off_on_render_unless_turned_on(load: Callable[..., ModuleType]) -> None:
    """Render sets RENDER; a forgotten DJANGO_DEBUG there never means debug on."""
    assert load(RENDER="true").DEBUG is False
    assert load(RENDER="true", DJANGO_DEBUG="1").DEBUG is True
    assert load().DEBUG is True


def test_production_needs_a_secret_key(load: Callable[..., ModuleType]) -> None:
    """With debug off there is no fallback key."""
    assert load(DJANGO_DEBUG="0").SECRET_KEY == ""
    assert load(DJANGO_DEBUG="1").SECRET_KEY.startswith("django-insecure")


def test_production_needs_a_database_url(load: Callable[..., ModuleType]) -> None:
    """Debug off with no DATABASE_URL stops at startup, never falls back to SQLite."""
    with pytest.raises(ImproperlyConfigured, match="DATABASE_URL"):
        load(DJANGO_DEBUG="0", DATABASE_URL="")
    local = load(DJANGO_DEBUG="1", DATABASE_URL="")
    assert local.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


def test_allowed_hosts_add_up(load: Callable[..., ModuleType]) -> None:
    """Both host lists, the onrender.com name and SITE_URL's host are allowed."""
    base = load(
        SECRET_KEY="k",
        DJANGO_DEBUG="0",
        ALLOWED_HOSTS=".onrender.com",
        DJANGO_ALLOWED_HOSTS="gondola.ultraniche.ai",
        RENDER_EXTERNAL_HOSTNAME="gondola.onrender.com",
        SITE_URL="https://gondola.ultraniche.ai",
    )
    assert base.ALLOWED_HOSTS == [
        ".onrender.com",
        "gondola.ultraniche.ai",
        "gondola.onrender.com",
    ]


def test_site_url_host_is_allowed(load: Callable[..., ModuleType]) -> None:
    """Setting SITE_URL alone is enough for the site to answer there."""
    base = load(SECRET_KEY="k", DJANGO_DEBUG="0", SITE_URL="https://gondola.example.com")
    assert base.ALLOWED_HOSTS == ["gondola.example.com"]


def test_development_answers_locally(load: Callable[..., ModuleType]) -> None:
    """With debug on, the local addresses work without any setting."""
    assert load().ALLOWED_HOSTS == ["localhost", "127.0.0.1", "[::1]"]


def test_site_url_defaults_to_the_render_address(load: Callable[..., ModuleType]) -> None:
    """Before go-live, links point at the service's onrender.com name."""
    base = load(RENDER_EXTERNAL_HOSTNAME="gondola.onrender.com")
    assert base.SITE_URL == "https://gondola.onrender.com"
    assert base.WEBAUTHN_RP_ID == "gondola.onrender.com"


def test_csrf_trusts_both_origin_lists_and_the_service(load: Callable[..., ModuleType]) -> None:
    """Titan's DJANGO_CSRF_TRUSTED_ORIGINS adds to the bare name and the onrender.com host."""
    base = load(
        SECRET_KEY="k",
        RENDER_EXTERNAL_HOSTNAME="gondola-f915.onrender.com",
        CSRF_TRUSTED_ORIGINS="https://*.onrender.com",
        DJANGO_CSRF_TRUSTED_ORIGINS="https://*.ultraniche.ai",
    )
    assert base.CSRF_TRUSTED_ORIGINS == [
        "https://*.onrender.com",
        "https://*.ultraniche.ai",
        "https://gondola-f915.onrender.com",
    ]


def test_production_hardening(load: Callable[..., ModuleType]) -> None:
    """Debug off turns on HTTPS, HSTS and secure cookies, and hashed static files."""
    base = load(SECRET_KEY="k", DJANGO_DEBUG="0", DATABASE_URL="postgresql://u:p@h:5432/gondola")
    assert base.SECURE_SSL_REDIRECT is True
    assert base.SESSION_COOKIE_SECURE is True
    assert base.DATABASES["default"]["NAME"] == "gondola"
    assert "Manifest" in base.STORAGES["staticfiles"]["BACKEND"]


def test_fivebar_counts_under_the_site_url_domain(
    load: Callable[..., ModuleType],
) -> None:
    settings = load(SECRET_KEY="x", SITE_URL="https://gondola.ultraniche.ai")
    assert settings.FIVEBAR_DOMAIN == "gondola.ultraniche.ai"


def test_fivebar_is_off_locally_and_without_a_site_url(
    load: Callable[..., ModuleType],
) -> None:
    assert load(SECRET_KEY="x").FIVEBAR_DOMAIN == ""
    assert load(SECRET_KEY="x", SITE_URL="http://localhost:8000").FIVEBAR_DOMAIN == ""


def test_fivebar_domain_can_be_overridden_or_turned_off(
    load: Callable[..., ModuleType],
) -> None:
    site = "https://gondola.ultraniche.ai"
    other = load(SECRET_KEY="x", SITE_URL=site, FIVEBAR_DOMAIN="other.example")
    assert other.FIVEBAR_DOMAIN == "other.example"
    assert load(SECRET_KEY="x", SITE_URL=site, FIVEBAR_DOMAIN="").FIVEBAR_DOMAIN == ""
