"""
apps/groups/migrations/0007_remove_planday_is_private.py — No private days.

Group-mates now see every day said. A day that was private was promised
to stay hidden, so it is deleted rather than shown: back to saying
nothing, which is how someone keeps a day to themselves from now on.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def forwards(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Delete the days that were kept private."""
    PlanDay = apps.get_model("groups", "PlanDay")
    PlanDay.objects.filter(is_private=True).delete()


class Migration(migrations.Migration):
    """Drop private days and the flag that made them."""

    dependencies = [
        ("groups", "0006_planday_skiing_yes_or_no"),
    ]

    operations = [
        # Nothing to undo: a deleted private day can't be brought back.
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(model_name="planday", name="is_private"),
    ]
