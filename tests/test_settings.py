"""Tests for config/settings/base.py: the environment names bin/titan writes."""

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
        DJANGO_ALLOWED_HOSTS="resort-planner.ultraniche.ai",
        RENDER_EXTERNAL_HOSTNAME="resort-planner.onrender.com",
        SITE_URL="https://resort-planner.ultraniche.ai",
    )
    assert base.ALLOWED_HOSTS == [
        ".onrender.com",
        "resort-planner.ultraniche.ai",
        "resort-planner.onrender.com",
    ]


def test_site_url_host_is_allowed(load: Callable[..., ModuleType]) -> None:
    """Setting SITE_URL alone is enough for the site to answer there."""
    base = load(SECRET_KEY="k", SITE_URL="https://gondola.example.com")
    assert base.ALLOWED_HOSTS == ["gondola.example.com"]
