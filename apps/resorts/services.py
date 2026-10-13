"""apps/resorts/services.py — Load the curated resort and pass sheets.

``passes.tsv`` and ``resorts.tsv`` under ``apps/resorts/data/`` are the
source of truth for reference data, taken from Snowdesk's resort sheet with
touring spots left out. ``import_sheets`` upserts them: passes by slug,
resorts by uuid. It never deletes a row, so a resort made in the admin
survives a re-import.
"""

from __future__ import annotations

import csv
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Pass, Resort

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
PASSES_PATH = DATA_DIR / "passes.tsv"
RESORTS_PATH = DATA_DIR / "resorts.tsv"


class SheetError(Exception):
    """A sheet row can't be imported."""


@dataclass
class ImportResult:
    """What an import did, or would do on a dry run."""

    passes_created: int = 0
    resorts_created: int = 0
    resorts_updated: int = 0
    errors: list[str] = field(default_factory=list)


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Return the rows of a tab-separated file as dicts keyed by header."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _float_or_none(value: str) -> float | None:
    """Parse a coordinate cell, treating an empty cell as no value."""
    return float(value) if value.strip() else None


def _resort_fields(row: dict[str, str]) -> dict[str, object]:
    """Map a sheet row to Resort field values."""
    return {
        "name": row["name"].strip(),
        # Optional column: a sheet without it leaves codes blank.
        "code": row.get("code", "").strip().upper(),
        "canton": row["canton"].strip(),
        "latitude": _float_or_none(row["latitude"]),
        "longitude": _float_or_none(row["longitude"]),
        "website": row["website"].strip(),
    }


def _import_passes(rows: list[dict[str, str]], result: ImportResult) -> None:
    """Create any pass the database lacks; never rename or delete one."""
    for row in rows:
        _, created = Pass.objects.get_or_create(
            slug=row["slug"].strip(),
            defaults={"name": row["name"].strip(), "website": row["website"].strip()},
        )
        result.passes_created += int(created)


def _import_resort(row: dict[str, str], result: ImportResult) -> None:
    """Upsert one resort row and set its passes."""
    try:
        key = uuid.UUID(row["uuid"])
        fields = _resort_fields(row)
        # Check lengths and formats here: SQLite ignores max_length, so
        # without this a value too long for Postgres only fails on deploy.
        Resort(**fields).clean_fields(exclude=["uuid", "passes"])
    except (KeyError, ValueError) as exc:
        raise SheetError(f"{row.get('name', '?')}: {exc}") from exc
    except ValidationError as exc:
        raise SheetError(f"{row.get('name', '?')}: {exc.message_dict}") from exc
    slugs = [s.strip() for s in row.get("passes", "").split(",") if s.strip()]
    passes = list(Pass.objects.filter(slug__in=slugs))
    if len(passes) != len(slugs):
        raise SheetError(f"{fields['name']}: unknown pass in {slugs}")
    resort, created = Resort.objects.update_or_create(uuid=key, defaults=fields)
    resort.passes.set(passes)
    if created:
        result.resorts_created += 1
    else:
        result.resorts_updated += 1


def import_sheets(
    *,
    passes_path: Path = PASSES_PATH,
    resorts_path: Path = RESORTS_PATH,
    commit: bool = False,
) -> ImportResult:
    """Import the pass and resort sheets.

    Runs inside one transaction that is rolled back unless ``commit`` is
    true, so a dry run reports exactly what a real run would do. A bad row
    is recorded in ``errors`` and skipped; the rest still import.
    """
    result = ImportResult()
    with transaction.atomic():
        _import_passes(read_tsv(passes_path), result)
        for row in read_tsv(resorts_path):
            try:
                with transaction.atomic():
                    _import_resort(row, result)
            except SheetError as exc:
                logger.warning("Skipped resort row: %s", exc)
                result.errors.append(str(exc))
        if not commit:
            transaction.set_rollback(True)
    return result
