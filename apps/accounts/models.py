"""
apps/accounts/models.py — The custom user model.

``User`` signs in with an email address, never a username. Emails are
normalised to lowercase before storage and lookup, at every entry point,
so ``Bob@x.com`` and ``bob@x.com`` are one account.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

from apps.core.models import BaseModel


def normalise_email(email: str) -> str:
    """Return ``email`` stripped and lowercased."""
    return email.strip().lower()


class UserQuerySet(models.QuerySet["User"]):
    """Custom queryset for User."""

    def active(self) -> UserQuerySet:
        """Return users whose accounts are active."""
        return self.filter(is_active=True)

    def wants_evening_email(self) -> UserQuerySet:
        """Return active users who have not turned the evening email off."""
        return self.active().filter(evening_email_enabled=True)


class UserManager(BaseUserManager["User"]):
    """Manager that creates users keyed on a lowercased email."""

    def get_queryset(self) -> UserQuerySet:
        """Return the custom queryset."""
        return UserQuerySet(self.model, using=self._db)

    def active(self) -> UserQuerySet:
        """Proxy for ``UserQuerySet.active``."""
        return self.get_queryset().active()

    def wants_evening_email(self) -> UserQuerySet:
        """Proxy for ``UserQuerySet.wants_evening_email``."""
        return self.get_queryset().wants_evening_email()

    def get_by_natural_key(self, username: str | None) -> User:
        """Look a user up by email, case-insensitively."""
        return self.get(email=normalise_email(username or ""))

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError("A user must have an email address.")
        user = self.model(email=normalise_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create and save a staff superuser."""
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self.create_user(email, password, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """A person who plans days and joins groups, identified by email."""

    email = models.EmailField(unique=True)
    display_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="The name friends see on the board.",
    )
    evening_email_enabled = models.BooleanField(
        default=True,
        help_text="Send the evening-before email. Covers that email only.",
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalise the email before every save."""
        self.email = normalise_email(self.email)
        super().save(*args, **kwargs)

    def to_string(self) -> str:
        """Return the display name, falling back to the email."""
        return self.display_name or self.email

    def get_short_name(self) -> str:
        """Return the name shown in compact places such as the board."""
        return self.to_string()

    def get_full_name(self) -> str:
        """Return the name shown in full."""
        return self.to_string()
