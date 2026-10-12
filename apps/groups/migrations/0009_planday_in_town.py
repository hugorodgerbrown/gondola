"""
apps/groups/migrations/0009_planday_in_town.py — A day is just "in town".

Gondola answers who's in which resort over the coming days; whether
anyone skies is left to the group chat. Skiing goes, and so do the old
days that named no resort, which now say nothing. Every day left names a
resort, so the column becomes required.
"""

from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def forwards(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Delete the days with no resort."""
    PlanDay = apps.get_model("groups", "PlanDay")
    PlanDay.objects.filter(resort__isnull=True).delete()


class Migration(migrations.Migration):
    """Drop skiing; make the resort required."""

    dependencies = [
        ("groups", "0008_remove_planday_note"),
        ("resorts", "__first__"),
    ]

    operations = [
        # Nothing to undo: a day with no resort carried no answer worth keeping.
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(model_name="planday", name="skiing"),
        migrations.AlterField(
            model_name="planday",
            name="resort",
            field=models.ForeignKey(
                help_text="Where they'll be.",
                on_delete=models.deletion.PROTECT,
                related_name="plan_days",
                to="resorts.resort",
            ),
        ),
    ]
