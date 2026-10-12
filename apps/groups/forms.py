"""
apps/groups/forms.py — Forms for days and groups.

Resorts arrive as their public uuid (never the database id), from radio
buttons in the day sheet. Every day needs a resort.
"""

from __future__ import annotations

import uuid

from django import forms

from apps.resorts.models import Resort

from .models import Group


class DayForm(forms.Form):
    """Which resort someone will be in, on one day or several."""

    resort = forms.CharField(required=False)

    def clean_resort(self) -> Resort:
        """Return the resort picked; a day can't be at no resort."""
        value = (self.cleaned_data.get("resort") or "").strip()
        if not value:
            raise forms.ValidationError("Pick a resort.")
        try:
            return Resort.objects.get(uuid=uuid.UUID(value))
        except ValueError, Resort.DoesNotExist:
            raise forms.ValidationError("Pick a resort from the list.") from None


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
