"""
apps/resorts/models.py — Resorts and the season passes they're sold on.

A ``Pass`` is reference data that groups resorts: it filters the map and
the resort picker, and never gates a plan. A plan can point at any
resort. Touring spots are deliberately not resorts here and are never
imported.

Rows come from ``apps/resorts/data/`` via the ``import_resorts`` command.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel


class PassQuerySet(models.QuerySet["Pass"]):
    """Custom queryset for Pass."""


class Pass(BaseModel):
    """A season pass that groups resorts, such as the Magic Pass."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    website = models.URLField(blank=True)

    objects = PassQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        verbose_name_plural = "passes"
        ordering = ["name"]

    def to_string(self) -> str:
        """Return the pass name."""
        return self.name


class ResortQuerySet(models.QuerySet["Resort"]):
    """Custom queryset for Resort."""

    def placed(self) -> ResortQuerySet:
        """Return resorts with a coordinate, so they can be pins on a map."""
        return self.filter(latitude__isnull=False, longitude__isnull=False)

    def on_pass(self, slug: str) -> ResortQuerySet:
        """Return resorts sold on the pass with this slug."""
        return self.filter(passes__slug=slug)


class Resort(BaseModel):
    """A ski resort friends can plan a day at."""

    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=5,
        blank=True,
        help_text="Short code for the who's-where board, 3 to 5 letters.",
    )
    canton = models.CharField(
        max_length=5,
        blank=True,
        help_text="Canton code, or two joined by a slash for a resort that spans both.",
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    website = models.URLField(blank=True)
    passes = models.ManyToManyField(Pass, blank=True, related_name="resorts")

    objects = ResortQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["name"]
        constraints = [
            # Blank until codes are assigned; once set, no two resorts share one.
            models.UniqueConstraint(
                fields=["code"],
                condition=~models.Q(code=""),
                name="resort_code_unique_when_set",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(latitude__isnull=True, longitude__isnull=True)
                    | models.Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name="resort_coordinate_pair",
            ),
        ]

    def to_string(self) -> str:
        """Return the resort name."""
        return self.name

    @property
    def display_code(self) -> str:
        """Return the board code, or the name's first letters if none is set."""
        return self.code or "".join(c for c in self.name if c.isalpha())[:5].upper()

    @property
    def is_placed(self) -> bool:
        """Return whether the resort has a coordinate for the map."""
        return self.latitude is not None and self.longitude is not None
