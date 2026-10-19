"""apps/accounts/models.py — The user, their passkeys, and pending sign-ins.

``User`` signs in with an email address, never a username. Emails are
normalised to lowercase before storage and lookup, at every entry point,
so ``Bob@x.com`` and ``bob@x.com`` are one account. ``SignInRequest`` is
one emailed link and code (see ``sign_in.py``). ``ReviewerAccount`` is an
address app directory reviewers sign in with, by a fixed code.
"""

from __future__ import annotations

import secrets
from typing import Any, ClassVar

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.auth.password_validation import validate_password
from django.db import models
from django.utils import timezone

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

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError("A user must have an email address.")
        user = self.model(email=normalise_email(email), **extra_fields)
        if password is None:
            # People sign in by emailed link or passkey; only staff may have one.
            user.set_unusable_password()
        else:
            validate_password(password, user)
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
    toured_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When they last finished the onboarding tour, if ever.",
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


class PasskeyQuerySet(models.QuerySet["Passkey"]):
    """Custom queryset for Passkey."""

    def for_user(self, user: User) -> PasskeyQuerySet:
        """Return the passkeys ``user`` has added."""
        return self.filter(user=user)


class Passkey(BaseModel):
    """A passkey (WebAuthn credential) someone can sign in with.

    The public key is stored; the private key never leaves the person's
    device or password manager. A person can add one per device, and the
    emailed link keeps working alongside them.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="passkeys")
    credential_id = models.CharField(
        max_length=1400,
        unique=True,
        help_text="The credential's id, base64url-encoded, as the browser sends it.",
    )
    public_key = models.BinaryField(help_text="COSE-encoded public key.")
    sign_count = models.PositiveBigIntegerField(default=0)
    name = models.CharField(max_length=100, help_text="Shown on the account page.")
    backed_up = models.BooleanField(
        default=False, help_text="Synced by a password manager, not tied to one device."
    )
    last_used_at = models.DateTimeField(null=True, blank=True)

    objects = PasskeyQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]

    def to_string(self) -> str:
        """Return the passkey's name and whose it is."""
        return f"{self.name} ({self.user.email})"


class SignInRequestQuerySet(models.QuerySet["SignInRequest"]):
    """Custom queryset for SignInRequest."""

    def unused(self) -> SignInRequestQuerySet:
        """Return requests not yet used or retired, expired or not."""
        return self.filter(used_at__isnull=True)

    def live(self) -> SignInRequestQuerySet:
        """Return requests that are unused and unexpired."""
        return self.filter(used_at__isnull=True, expires_at__gt=timezone.now())

    def expired(self) -> SignInRequestQuerySet:
        """Return requests past their expiry, used or not: safe to delete."""
        return self.filter(expires_at__lte=timezone.now())

    def for_email(self, email: str) -> SignInRequestQuerySet:
        """Return the requests sent to ``email``."""
        return self.filter(email=normalise_email(email))


class SignInRequest(BaseModel):
    """One emailed sign-in: a link and a six-digit code, either usable once.

    Only hashes are stored, so a copy of the database signs no one in. The
    link works in any browser; the code only in the browser that asked for
    it (the session holds this row's uuid), which is what makes it safe to
    keep short. The code is there because an installed iPhone app has its
    own cookies: a link opened from Mail signs in Safari, not the app, so
    the app's user types the code instead.

    At most one request per address is open (unused) at a time, enforced by
    the database, so only the newest email signs anyone in even when two
    are asked for at once.
    """

    email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    code_hash = models.CharField(max_length=64)
    next_url = models.CharField(max_length=2048, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    code_attempts = models.PositiveSmallIntegerField(default=0)

    objects = SignInRequestQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(used_at__isnull=True),
                name="one_open_sign_in_request_per_email",
            )
        ]

    def to_string(self) -> str:
        """Return who it was for and whether it was used."""
        state = "used" if self.used_at else "unused"
        return f"Sign-in for {self.email} ({state})"


# The same length as an emailed code (sign_in.CODE_DIGITS), so the code
# form takes it.
REVIEWER_CODE_DIGITS = 6


def new_reviewer_code() -> str:
    """Return a random code for a reviewer account."""
    return f"{secrets.randbelow(10**REVIEWER_CODE_DIGITS):0{REVIEWER_CODE_DIGITS}d}"


class ReviewerAccountQuerySet(models.QuerySet["ReviewerAccount"]):
    """Custom queryset for ReviewerAccount."""

    def for_email(self, email: str) -> ReviewerAccountQuerySet:
        """Return the reviewer account for ``email``, if there is one."""
        return self.filter(email=normalise_email(email))


class ReviewerAccount(BaseModel):
    """An address that signs in with a fixed code, for app directory reviewers.

    OpenAI's and Anthropic's reviews need a test account with no email or
    other verification step. This address is sent no email: on the code page
    it takes ``code``, which is made on the first save. The code is kept as
    it is, unlike an emailed one, so staff can read it here and paste it into
    the submission form. It is a shared test credential, not a person's
    secret; give a new one after each review (the admin action). Deleting
    the row turns the address back into an ordinary one.
    """

    email = models.EmailField(unique=True)
    code = models.CharField(max_length=REVIEWER_CODE_DIGITS, editable=False)

    objects = ReviewerAccountQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["email"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalise the address, and make a code if there isn't one.

        Changing the address ends the old one's pending sign-ins, which hold
        this code: it is no longer a reviewer address.
        """
        self.email = normalise_email(self.email)
        if not self.code:
            self.code = new_reviewer_code()
        update_fields = kwargs.get("update_fields")
        email_saved = update_fields is None or "email" in update_fields
        previous = (
            ReviewerAccount.objects.filter(pk=self.pk).values_list("email", flat=True).first()
            if self.pk and email_saved
            else None
        )
        super().save(*args, **kwargs)
        if previous and previous != self.email:
            SignInRequest.objects.for_email(previous).live().update(used_at=timezone.now())

    def give_new_code(self) -> None:
        """Replace the code, and end sign-ins already started with the old one."""
        self.code = new_reviewer_code()
        self.save(update_fields=["code", "updated_at"])
        self.end_pending_sign_ins()

    def end_pending_sign_ins(self) -> None:
        """Stop this address's unused sign-in requests working.

        A request holds the code it was issued with, so without this an old
        code would keep working in a browser that asked for it until the
        request expired.
        """
        SignInRequest.objects.for_email(self.email).live().update(used_at=timezone.now())

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Delete the account, ending any sign-in it had started."""
        self.end_pending_sign_ins()
        return super().delete(*args, **kwargs)

    def to_string(self) -> str:
        """Return the address."""
        return self.email
