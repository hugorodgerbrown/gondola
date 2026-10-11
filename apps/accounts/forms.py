"""
apps/accounts/forms.py — Forms for signing in, the profile and the admin.

Django's stock user forms name a ``username`` field this model doesn't
have, so the admin needs the two subclasses at the bottom.
"""

from typing import Any

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User, normalise_email


class SignInForm(forms.Form):
    """Ask for the email address to send a sign-in link to."""

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "input",
                "autocomplete": "email",
                "placeholder": "you@example.com",
                "autofocus": True,
            }
        ),
    )

    def clean_email(self) -> str:
        """Return the email lowercased."""
        return normalise_email(self.cleaned_data["email"])


class ProfileForm(forms.ModelForm):
    """The name friends see, and whether to get the evening email."""

    class Meta:
        """Form metadata."""

        model = User
        fields: tuple[str, ...] = ("display_name", "evening_email_enabled")
        labels = {
            "display_name": "Your name",
            "evening_email_enabled": "Email me the evening before I ski",
        }
        widgets = {
            "display_name": forms.TextInput(
                attrs={"class": "input", "autocomplete": "given-name"}
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Make the name required: it's how friends recognise you."""
        super().__init__(*args, **kwargs)
        self.fields["display_name"].required = True

    def clean_display_name(self) -> str:
        """Return the name with surrounding space removed."""
        return str(self.cleaned_data["display_name"]).strip()


class NameForm(ProfileForm):
    """Ask the first-run question: what friends should call you."""

    class Meta(ProfileForm.Meta):
        """Form metadata."""

        fields: tuple[str, ...] = ("display_name",)


class EmailUserCreationForm(UserCreationForm):
    """Create a user from an email, a display name and a password."""

    class Meta:
        """Form metadata."""

        model = User
        fields = ("email", "display_name")


class EmailUserChangeForm(UserChangeForm):
    """Edit a user in the admin."""

    class Meta:
        """Form metadata."""

        model = User
        fields = ("email", "display_name", "evening_email_enabled")
