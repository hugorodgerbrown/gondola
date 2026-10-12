"""Tests for apps/groups/migrations/: the data steps that drop answers.

The fields they read are gone from the model, so each step is checked
against a stand-in for the historical model.
"""

import importlib
from unittest import mock

skiing_yes_or_no = importlib.import_module(
    "apps.groups.migrations.0006_planday_skiing_yes_or_no"
)
no_private_days = importlib.import_module(
    "apps.groups.migrations.0007_remove_planday_is_private"
)
in_town = importlib.import_module("apps.groups.migrations.0009_planday_in_town")


def test_not_sure_days_become_around_or_are_cleared() -> None:
    historical = mock.Mock()
    skiing_yes_or_no.forwards(historical, None)
    unsure = historical.get_model.return_value.objects.filter
    unsure.assert_called_once_with(skiing="not_sure")
    there, nowhere = unsure.return_value.filter.call_args_list
    assert there == mock.call(resort__isnull=False)
    assert nowhere == mock.call(resort__isnull=True)
    unsure.return_value.filter.return_value.update.assert_called_once_with(
        skiing="not_skiing"
    )
    unsure.return_value.filter.return_value.delete.assert_called_once_with()


def test_private_days_are_deleted() -> None:
    historical = mock.Mock()
    no_private_days.forwards(historical, None)
    historical.get_model.assert_called_once_with("groups", "PlanDay")
    plan_days = historical.get_model.return_value.objects
    plan_days.filter.assert_called_once_with(is_private=True)
    plan_days.filter.return_value.delete.assert_called_once_with()


def test_days_without_a_resort_are_deleted() -> None:
    historical = mock.Mock()
    in_town.forwards(historical, None)
    plan_days = historical.get_model.return_value.objects
    plan_days.filter.assert_called_once_with(resort__isnull=True)
    plan_days.filter.return_value.delete.assert_called_once_with()
