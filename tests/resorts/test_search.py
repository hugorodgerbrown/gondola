"""Tests for apps/resorts/search.py and the Resort display helpers."""

import pytest

from apps.resorts.search import fold, search_resorts
from tests.factories import ResortFactory

pytestmark = pytest.mark.django_db


def test_fold() -> None:
    assert fold("Champéry") == "champery"


def test_search_ranks_and_ignores_accents() -> None:
    ResortFactory.create(name="Champéry", code="CHAM")
    ResortFactory.create(name="Les Diablerets")
    ResortFactory.create(name="Champex", code="CHA")
    ResortFactory.create(name="Grimentz")
    assert [r.name for r in search_resorts("champ")] == ["Champex", "Champéry"]
    assert [r.name for r in search_resorts("CHAM")][0] == "Champéry"
    assert [r.name for r in search_resorts("diab")] == ["Les Diablerets"]
    assert [r.name for r in search_resorts("ment")] == ["Grimentz"]
    assert search_resorts("  ") == []
    assert search_resorts("zzz") == []


def test_display_code_falls_back_to_name() -> None:
    assert ResortFactory.create(name="Saas-Fee", code="").display_code == "SAASF"
    assert ResortFactory.create(code="VERB").display_code == "VERB"


def test_is_placed() -> None:
    assert ResortFactory.create().is_placed
    assert not ResortFactory.create(latitude=None, longitude=None).is_placed
