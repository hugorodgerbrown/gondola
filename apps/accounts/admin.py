"""apps/accounts/admin.py — Admin for users, passkeys, sign-ins and reviewer accounts.

Putting a user in the "Testers" auth group (on their page, or with the
list's actions) joins them to the "UI test" planning group; taking them out
removes them. See ``apps.groups.services.testers``.
"""

from typing import Any

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest

from apps.groups.services.testers import set_testers, sync_tester

from .forms import EmailUserChangeForm, EmailUserCreationForm
from .models import Passkey, ReviewerAccount, SignInRequest, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for ``User``, keyed on email instead of username."""

    form = EmailUserChangeForm
    add_form = EmailUserCreationForm
    ordering = ["-created_at"]
    list_display = ["email", "display_name", "is_staff", "is_active", "created_at"]
    list_filter = ["is_staff", "is_active", "evening_email_enabled", "groups"]
    actions = ["add_to_testers", "remove_from_testers"]
    search_fields = ["email", "display_name"]
    readonly_fields = ["uuid", "created_at", "updated_at", "last_login"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "evening_email_enabled", "toured_at")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("uuid", "last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "password1", "password2"),
            },
        ),
    )

    def save_related(
        self, request: HttpRequest, form: ModelForm, formsets: Any, change: bool
    ) -> None:
        """Save the user's groups, then join or leave "UI test" to match."""
        super().save_related(request, form, formsets, change)
        sync_tester(form.instance)

    @admin.action(description="Add to Testers (joins UI test)")
    def add_to_testers(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Put the selected users in Testers."""
        set_testers(queryset, on=True)
        self.message_user(request, f"Added {queryset.count()} to Testers.")

    @admin.action(description="Remove from Testers (leaves UI test)")
    def remove_from_testers(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Take the selected users out of Testers."""
        set_testers(queryset, on=False)
        self.message_user(request, f"Removed {queryset.count()} from Testers.")


@admin.register(Passkey)
class PasskeyAdmin(admin.ModelAdmin):
    """Admin for ``Passkey``: see and remove them, never edit the key."""

    list_display = ["name", "user", "backed_up", "last_used_at", "created_at"]
    list_filter = ["backed_up"]
    search_fields = ["name", "user__email"]
    list_select_related = ["user"]
    readonly_fields = [
        "uuid",
        "user",
        "credential_id",
        "sign_count",
        "backed_up",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
    exclude = ["public_key"]


@admin.register(SignInRequest)
class SignInRequestAdmin(admin.ModelAdmin):
    """Who asked to sign in and whether they did. The hashes stay hidden."""

    list_display = ["email", "created_at", "expires_at", "used_at", "code_attempts"]
    search_fields = ["email"]
    fields = ("email", "next_url", "created_at", "expires_at", "used_at", "code_attempts")
    readonly_fields = ("email", "next_url", "created_at", "expires_at", "used_at", "code_attempts")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Requests are made by the sign-in form only."""
        return False


@admin.register(ReviewerAccount)
class ReviewerAccountAdmin(admin.ModelAdmin):
    """Addresses app directory reviewers sign in with, and their fixed codes."""

    list_display = ["email", "code", "created_at", "updated_at"]
    search_fields = ["email"]
    fields = ("email", "code", "created_at", "updated_at")
    readonly_fields = ("code", "created_at", "updated_at")
    actions = ["give_new_code"]

    @admin.action(description="Give the selected accounts a new code")
    def give_new_code(self, request: HttpRequest, queryset: QuerySet[ReviewerAccount]) -> None:
        """Replace each selected account's code, as after a review."""
        count = 0
        for account in queryset:
            account.give_new_code()
            count += 1
        noun = "account" if count == 1 else "accounts"
        self.message_user(request, f"Gave {count} {noun} a new code.", messages.SUCCESS)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[ReviewerAccount]) -> None:
        """Delete one by one, so each ends the sign-ins it had started."""
        for account in queryset:
            account.delete()
