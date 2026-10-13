"""Tests for apps/resorts/services.py."""

from pathlib import Path

import pytest

from apps.resorts.models import Pass, Resort
from apps.resorts.services import RESORTS_PATH, ImportResult, import_sheets, read_tsv

pytestmark = pytest.mark.django_db

HEADER = "uuid\tname\tcanton\tlatitude\tlongitude\tpasses\twebsite\n"
PASSES = "slug\tname\twebsite\nmagic-pass\tMagic Pass\thttps://www.magicpass.ch/\n"
UUID_A = "f12cecf9-def8-43d3-b9df-80f93472f16f"
UUID_B = "532151df-47a0-497b-b168-09f975f7d07d"


def _import(tmp_path: Path, rows: str, *, commit: bool) -> ImportResult:
    passes = tmp_path / "passes.tsv"
    resorts = tmp_path / "resorts.tsv"
    passes.write_text(PASSES, encoding="utf-8")
    resorts.write_text(HEADER + rows, encoding="utf-8")
    return import_sheets(passes_path=passes, resorts_path=resorts, commit=commit)


def test_shipped_sheets_import_cleanly() -> None:
    result = import_sheets(commit=True)
    assert result.errors == []
    assert result.resorts_created == 213
    assert Resort.objects.count() == 213
    assert Resort.objects.on_pass("magic-pass").count() == 90


def test_shipped_sheet_has_no_touring_spots() -> None:
    rows = read_tsv(RESORTS_PATH)
    assert len(rows) == 213
    assert "kind" not in rows[0]


def test_dry_run_saves_nothing(tmp_path: Path) -> None:
    result = _import(tmp_path, f"{UUID_A}\tVerbier\tVS\t46.09\t7.22\t\t\n", commit=False)
    assert result.resorts_created == 1
    assert result.passes_created == 1
    assert not Resort.objects.exists()
    assert not Pass.objects.exists()


def test_commit_creates_then_updates(tmp_path: Path) -> None:
    rows = (
        f"{UUID_A}\tVerbier\tVS\t46.09\t7.22\tmagic-pass\thttps://verbier.ch\n"
        f"{UUID_B}\tThyon\tVS\t\t\t\t\n"
    )
    first = _import(tmp_path, rows, commit=True)
    assert (first.resorts_created, first.resorts_updated) == (2, 0)
    thyon = Resort.objects.get(name="Thyon")
    assert thyon.latitude is None
    assert str(thyon.uuid) == UUID_B
    assert list(Resort.objects.on_pass("magic-pass").values_list("name", flat=True)) == ["Verbier"]

    renamed = rows.replace("Thyon", "Thyon 2000")
    second = _import(tmp_path, renamed, commit=True)
    assert (second.resorts_created, second.resorts_updated) == (0, 2)
    assert second.passes_created == 0
    assert Resort.objects.filter(name="Thyon 2000").exists()


def test_bad_rows_are_reported_and_skipped(tmp_path: Path) -> None:
    rows = (
        f"not-a-uuid\tBroken\tVS\t\t\t\t\n"
        f"{UUID_B}\tUnknown pass\tVS\t\t\tnope-pass\t\n"
        f"{UUID_A}\tVerbier\tVS\t46.09\t7.22\t\t\n"
    )
    result = _import(tmp_path, rows, commit=True)
    assert len(result.errors) == 2
    assert "Broken" in result.errors[0]
    assert "unknown pass" in result.errors[1]
    assert list(Resort.objects.values_list("name", flat=True)) == ["Verbier"]


def test_resort_spanning_two_cantons_keeps_both() -> None:
    import_sheets(commit=True)
    assert Resort.objects.get(name="Lötschental").canton == "BE/VS"


def test_value_too_long_for_its_column_is_skipped(tmp_path: Path) -> None:
    result = _import(tmp_path, f"{UUID_A}\tVerbier\tVALAIS\t46.09\t7.22\t\t\n", commit=True)
    assert result.resorts_created == 0
    assert "canton" in result.errors[0]
    assert not Resort.objects.exists()


def test_only_web_addresses_become_links(tmp_path: Path) -> None:
    rows = (
        f"{UUID_A}\tVerbier\tVS\t46.09\t7.22\t\tjavascript:alert(1)\n"
        f"{UUID_B}\tThyon\tVS\t\t\t\t http://thyon.ch \n"
    )
    _import(tmp_path, rows, commit=True)
    assert Resort.objects.get(name="Verbier").website == ""
    assert Resort.objects.get(name="Thyon").website == "http://thyon.ch"
