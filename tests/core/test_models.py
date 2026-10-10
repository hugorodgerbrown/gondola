"""Tests for apps/core/models.py."""

import pytest

from apps.core.models import BaseModel
from tests.factories import PassFactory


@pytest.mark.django_db
def test_str_delegates_to_to_string() -> None:
    pass_ = PassFactory.create(name="Magic Pass")
    assert str(pass_) == "Magic Pass"


@pytest.mark.django_db
def test_base_to_string_names_class_and_pk() -> None:
    pass_ = PassFactory.create()
    assert BaseModel.to_string(pass_) == f"Pass({pass_.pk})"


@pytest.mark.django_db
def test_base_fields_are_filled() -> None:
    pass_ = PassFactory.create()
    assert pass_.uuid is not None
    assert pass_.created_at.tzinfo is not None
    assert pass_.updated_at >= pass_.created_at
