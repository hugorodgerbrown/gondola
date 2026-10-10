"""
apps/accounts/forms.py — Admin forms for the email-keyed user model.

Django's stock user forms name a ``username`` field this model doesn't
have, so the admin needs these two subclasses.
"""

from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


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
