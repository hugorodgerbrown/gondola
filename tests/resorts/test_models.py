"""Tests for apps/resorts/models.py."""

import pytest
from django.db import IntegrityError

from apps.resorts.models import Resort
from tests.factories import PassFactory, ResortFactory

pytestmark = pytest.mark.django_db


def test_to_string() -> None:
    assert str(ResortFactory.create(name="Verbier")) == "Verbier"
    assert str(PassFactory.create(name="Magic Pass")) == "Magic Pass"


def test_placed_excludes_resorts_without_a_coordinate() -> None:
    placed = ResortFactory.create()
    ResortFactory.create(latitude=None, longitude=None)
    assert list(Resort.objects.placed()) == [placed]


def test_on_pass() -> None:
    magic = PassFactory.create(slug="magic-pass")
    on_pass = ResortFactory.create()
    on_pass.passes.add(magic)
    ResortFactory.create()
    assert list(Resort.objects.on_pass("magic-pass")) == [on_pass]
    assert list(magic.resorts.all()) == [on_pass]


def test_blank_codes_may_repeat() -> None:
    ResortFactory.create(code="")
    ResortFactory.create(code="")
    assert Resort.objects.filter(code="").count() == 2


def test_a_set_code_is_unique() -> None:
    ResortFactory.create(code="VERB")
    with pytest.raises(IntegrityError):
        ResortFactory.create(code="VERB")


def test_coordinate_is_both_or_neither() -> None:
    with pytest.raises(IntegrityError):
        ResortFactory.create(latitude=46.0, longitude=None)
