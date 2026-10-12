"""
apps/groups/forms.py — Forms for days and groups.

Resorts arrive as their public uuid (never the database id), from radio
buttons in the day sheet. Every day needs a resort; a sheet for several
days can also send "keep".
"""

from __future__ import annotations

import uuid
from typing import Any

from django import forms

from apps.resorts.models import Resort

from .models import Group, PlanDay
from .services.plans import KEEP, Keep

# The resort radio's value for "leave each day's resort as it is".
KEEP_RESORT = "keep"


class DayForm(forms.Form):
    """What someone says about one day or several: where, and if skiing.

    Every answer can be left out to keep what each day already says, which
    is how a sheet for several days changes only what was touched: no
    skiing choice, the "keep" resort, or the ``note_keep`` flag the page
    renders beside a note that differs across the days (and drops once
    the note is changed).
    """

    skiing = forms.ChoiceField(choices=PlanDay.Skiing.choices, required=False)
    resort = forms.CharField(required=False)
    note = forms.CharField(
        max_length=140,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "Optional, e.g. first lift"}
        ),
    )
    note_keep = forms.BooleanField(required=False)

    def clean_resort(self) -> Resort | Keep:
        """Return the resort picked, or KEEP; a day can't be at no resort."""
        value = (self.cleaned_data.get("resort") or "").strip()
        if value == KEEP_RESORT:
            return KEEP
        if not value:
            raise forms.ValidationError("Pick a resort.")
        try:
            return Resort.objects.get(uuid=uuid.UUID(value))
        except ValueError, Resort.DoesNotExist:
            raise forms.ValidationError("Pick a resort from the list.") from None

    def changes(self) -> dict[str, Any]:
        """Return the answers to save, as ``update_plans`` keywords."""
        data = self.cleaned_data
        return {
            "skiing": data["skiing"] or KEEP,
            "resort": data["resort"],
            "note": KEEP if data["note_keep"] else data["note"],
        }


class GroupForm(forms.ModelForm):
    """Name a new group."""

    class Meta:
        """Form metadata."""

        model = Group
        fields = ("name",)
        labels = {"name": "Group name"}
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Thursday crew"}
            )
        }
