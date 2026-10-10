"""Tests for the import_resorts management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.resorts.models import Resort
from apps.resorts.services import ImportResult

pytestmark = pytest.mark.django_db


def test_bare_run_is_a_dry_run() -> None:
    out = StringIO()
    call_command("import_resorts", stdout=out)
    assert "Would import" in out.getvalue()
    assert "Dry run" in out.getvalue()
    assert not Resort.objects.exists()


def test_commit_saves() -> None:
    out = StringIO()
    call_command("import_resorts", "--commit", stdout=out)
    assert "Imported: 1 new passes, 213 new resorts" in out.getvalue()
    assert Resort.objects.count() == 213


def test_silent_at_verbosity_zero() -> None:
    out = StringIO()
    call_command("import_resorts", verbosity=0, stdout=out)
    assert out.getvalue() == ""


def test_failed_rows_exit_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.resorts.management.commands.import_resorts.import_sheets",
        lambda commit: ImportResult(errors=["Broken: bad uuid"]),
    )
    err = StringIO()
    with pytest.raises(CommandError, match="1 resort rows failed"):
        call_command("import_resorts", stdout=StringIO(), stderr=err)
    assert "Broken: bad uuid" in err.getvalue()
