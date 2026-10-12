"""Tests for apps/groups/migrations/: the data steps that drop answers."""

import importlib
from unittest import mock

import pytest
from django.apps import apps

from apps.groups.models import PlanDay
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
skiing_yes_or_no = importlib.import_module(
    "apps.groups.migrations.0006_planday_skiing_yes_or_no"
)
no_private_days = importlib.import_module(
    "apps.groups.migrations.0007_remove_planday_is_private"
)


def test_not_sure_days_become_around_or_are_cleared(crew: Crew) -> None:
    there = PlanDay.objects.create(
        user=crew.sam, date=crew.day, resort=crew.verbier, skiing="not_sure"
    )
    PlanDay.objects.create(user=crew.anna, date=crew.day, skiing="not_sure")
    skiing_yes_or_no.forwards(apps, None)
    there.refresh_from_db()
    assert there.skiing == PlanDay.Skiing.NO
    assert not PlanDay.objects.filter(user=crew.anna).exists()


def test_private_days_are_deleted() -> None:
    # The flag is gone from the model, so the step is checked against a stand-in.
    historical = mock.Mock()
    no_private_days.forwards(historical, None)
    historical.get_model.assert_called_once_with("groups", "PlanDay")
    plan_days = historical.get_model.return_value.objects
    plan_days.filter.assert_called_once_with(is_private=True)
    plan_days.filter.return_value.delete.assert_called_once_with()
