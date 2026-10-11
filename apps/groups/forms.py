"""
apps/groups/forms.py — Forms for days, groups and meet-ups.

Resorts arrive as their public uuid (never the database id), from radio
buttons in the day sheet and the meet-up form.
"""

from __future__ import annotations

import datetime
from typing import Any

from django import forms

from apps.resorts.models import Resort

from .models import Group, PlanDay
from .services.plans import today


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


class DayForm(forms.Form):
    """What someone says about one day."""

    status = forms.ChoiceField(
        choices=PlanDay.Status.choices, widget=forms.RadioSelect, initial="resort"
    )
    resort = ResortField(required=False)
    note = forms.CharField(
        max_length=140,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "Optional, e.g. first lift"}
        ),
    )
    is_private = forms.BooleanField(required=False)

    def clean(self) -> dict[str, Any]:
        """Require a resort exactly when the day is at a resort."""
        data = super().clean() or {}
        if data.get("status") == PlanDay.Status.RESORT and not data.get("resort"):
            self.add_error("resort", "Pick a resort, or choose Not sure yet.")
        return data


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
