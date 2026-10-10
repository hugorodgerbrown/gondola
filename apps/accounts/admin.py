"""apps/accounts/admin.py — Admin for the custom user model."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import EmailUserChangeForm, EmailUserCreationForm
from .models import User


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
