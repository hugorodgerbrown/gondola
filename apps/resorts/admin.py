"""apps/resorts/admin.py — Admin for resorts and passes."""

from django.contrib import admin

from .models import Pass, Resort


@admin.register(Pass)
class PassAdmin(admin.ModelAdmin):
    """Admin for ``Pass``."""

    list_display = ["name", "slug", "website"]
    search_fields = ["name", "slug"]
    readonly_fields = ["uuid", "created_at", "updated_at"]


@admin.register(Resort)
class ResortAdmin(admin.ModelAdmin):
    """Admin for ``Resort``."""

    list_display = ["name", "code", "canton", "latitude", "longitude"]
    list_filter = ["canton", "passes"]
    search_fields = ["name", "code"]
    filter_horizontal = ["passes"]
    readonly_fields = ["uuid", "created_at", "updated_at"]
