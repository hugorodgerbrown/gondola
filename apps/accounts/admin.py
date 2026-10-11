"""apps/accounts/admin.py — Admin for the custom user model."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import EmailUserChangeForm, EmailUserCreationForm
from .models import Passkey, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for ``User``, keyed on email instead of username."""

    form = EmailUserChangeForm
    add_form = EmailUserCreationForm
    ordering = ["-created_at"]
    list_display = ["email", "display_name", "is_staff", "is_active", "created_at"]
    list_filter = ["is_staff", "is_active", "evening_email_enabled"]
    search_fields = ["email", "display_name"]
    readonly_fields = ["uuid", "created_at", "updated_at", "last_login"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "evening_email_enabled")}),
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
