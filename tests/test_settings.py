"""Tests for the settings: the environment names titan writes."""

import importlib
from collections.abc import Callable, Iterator
from types import ModuleType

import pytest

import config.settings.base

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
)


@pytest.fixture
def load(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., ModuleType]]:
    """Reload the base settings under a given environment, then restore them."""
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)

    def _load(**env: str) -> ModuleType:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(config.settings.base)

    yield _load
    monkeypatch.undo()
    monkeypatch.setenv("SECRET_KEY", "restore")
    importlib.reload(config.settings.base)


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


def test_allowed_hosts_add_up(load: Callable[..., ModuleType]) -> None:
    """Both host lists, the onrender.com name and SITE_URL's host are allowed."""
    base = load(
        SECRET_KEY="k",
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
    base = load(SECRET_KEY="k", SITE_URL="https://gondola.example.com")
    assert base.ALLOWED_HOSTS == ["gondola.example.com"]


def test_production_trusts_both_origin_lists_and_the_service(
    load: Callable[..., ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Titan's DJANGO_CSRF_TRUSTED_ORIGINS adds to the bare name and the onrender.com host."""
    load(SECRET_KEY="k", RENDER_EXTERNAL_HOSTNAME="gondola-f915.onrender.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/gondola")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://*.onrender.com")
    monkeypatch.setenv("DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.ultraniche.ai")
    production = importlib.reload(importlib.import_module("config.settings.production"))
    assert production.CSRF_TRUSTED_ORIGINS == [
        "https://*.onrender.com",
        "https://*.ultraniche.ai",
        "https://gondola-f915.onrender.com",
    ]


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
