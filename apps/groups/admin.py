"""apps/groups/admin.py — Admin for groups and plan days."""

from django.contrib import admin

from .models import Group, Membership, PlanDay


class MembershipInline(admin.TabularInline):
    """Members shown on their group's page."""

    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Admin for ``Group``."""

    list_display = ["name", "owner", "is_demo", "created_at"]
    list_filter = ["is_demo"]
    search_fields = ["name", "owner__email"]
    autocomplete_fields = ["owner"]
    readonly_fields = [
        "uuid",
        "invite_token",
        "is_demo",
        "created_at",
        "updated_at",
    ]
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    """Admin for ``Membership``."""

    list_display = ["user", "group", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "group__name"]
    autocomplete_fields = ["user", "group"]
    readonly_fields = ["uuid", "created_at", "updated_at"]


@admin.register(PlanDay)
class PlanDayAdmin(admin.ModelAdmin):
    """Admin for ``PlanDay``."""

    list_display = ["user", "date", "resort"]
    search_fields = ["user__email", "resort__name"]
    date_hierarchy = "date"
    autocomplete_fields = ["user", "resort"]
    readonly_fields = ["uuid", "created_at", "updated_at"]
