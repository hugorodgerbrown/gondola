"""
apps/groups/migrations/0008_remove_planday_note.py — No day notes.

A plan is where you are and whether you're skiing; anything more goes in
the group chat. The notes are dropped with the column.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Drop the note on a plan day."""

    dependencies = [
        ("groups", "0007_remove_planday_is_private"),
    ]

    operations = [
        migrations.RemoveField(model_name="planday", name="note"),
    ]
