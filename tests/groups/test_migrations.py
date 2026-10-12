"""Tests for apps/groups/migrations/: the data step that drops "not sure"."""

import importlib

import pytest
from django.apps import apps

from apps.groups.models import PlanDay
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
skiing_yes_or_no = importlib.import_module(
    "apps.groups.migrations.0006_planday_skiing_yes_or_no"
)


def test_not_sure_days_become_around_or_are_cleared(crew: Crew) -> None:
    there = PlanDay.objects.create(
        user=crew.sam, date=crew.day, resort=crew.verbier, skiing="not_sure"
    )
    PlanDay.objects.create(user=crew.anna, date=crew.day, skiing="not_sure")
    skiing_yes_or_no.forwards(apps, None)  # type: ignore[arg-type]
    there.refresh_from_db()
    assert there.skiing == PlanDay.Skiing.NO
    assert not PlanDay.objects.filter(user=crew.anna).exists()
