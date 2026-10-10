"""
apps/core/models.py — Shared abstract models.

Holds ``BaseModel`` so every concrete model shares one source of truth for
the standard fields. There are no concrete tables in this app.
"""

import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model providing standard fields for all concrete models.

    Provides a BigAutoField primary key, a uuid4 field for use in URLs and
    exports, and created_at / updated_at timestamps.
    """

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        abstract = True
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return the model's human-readable form."""
        return self.to_string()

    def to_string(self) -> str:
        """Return a human-readable representation; subclasses override."""
        return f"{self.__class__.__name__}({self.pk})"
