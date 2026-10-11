"""
apps/groups/forms.py — Forms for days, groups and meet-ups.

Resorts arrive as their public uuid (never the database id), from radio
buttons in the day sheet and the meet-up form. The day sheet's resort can
also be empty (not at a resort) or "keep".
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from django import forms

from apps.resorts.models import Resort

from .models import Group, PlanDay
from .services.plans import KEEP, Keep, today


class ResortField(forms.UUIDField):
    """A resort chosen by its uuid."""

    def clean(self, value: Any) -> Resort | None:
        """Return the resort the uuid names, or None when left empty."""
        key = super().clean(value)
        if key is None:
            return None
        try:
            return Resort.objects.get(uuid=key)
        except Resort.DoesNotExist as exc:
            raise forms.ValidationError("Pick a resort from the list.") from exc


# The resort radio's value for "leave each day's resort as it is".
KEEP_RESORT = "keep"


class DayForm(forms.Form):
    """What someone says about one day or several: where, and if skiing.

    Every answer can be left out to keep what each day already says, which
    is how a sheet for several days changes only what was touched: no
    skiing choice, the "keep" resort, or the ``*_keep`` flag the page
    renders beside a note or privacy that differs across the days (and
    drops once that answer is changed).
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
    is_private = forms.BooleanField(required=False)
    private_keep = forms.BooleanField(required=False)

    def clean_resort(self) -> Resort | None | Keep:
        """Return the resort picked, None for no resort, or KEEP."""
        value = (self.cleaned_data.get("resort") or "").strip()
        if value == KEEP_RESORT:
            return KEEP
        if not value:
            return None
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
            "is_private": KEEP if data["private_keep"] else data["is_private"],
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


class MeetUpForm(forms.Form):
    """Propose a meet-up: a day and a resort, with an optional time and pin."""

    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "input"})
    )
    resort = ResortField()
    start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "class": "input"}),
    )
    meeting_latitude = forms.FloatField(
        required=False, min_value=-90, max_value=90, widget=forms.HiddenInput
    )
    meeting_longitude = forms.FloatField(
        required=False, min_value=-180, max_value=180, widget=forms.HiddenInput
    )

    def clean_date(self) -> datetime.date:
        """Refuse a day in the past."""
        day: datetime.date = self.cleaned_data["date"]
        if day < today():
            raise forms.ValidationError("Pick today or a later day.")
        return day

    def clean(self) -> dict[str, Any]:
        """Keep the meeting pin whole: both coordinates or neither."""
        data = super().clean() or {}
        lat, lng = data.get("meeting_latitude"), data.get("meeting_longitude")
        if (lat is None) != (lng is None):
            data["meeting_latitude"] = data["meeting_longitude"] = None
        return data
