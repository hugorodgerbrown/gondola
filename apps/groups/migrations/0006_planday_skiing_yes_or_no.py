"""
apps/groups/migrations/0006_planday_skiing_yes_or_no.py — Skiing is yes or no.

"Not sure yet" goes. A not-sure day at a resort becomes "around" (there,
not skiing), which it already counted as everywhere; a not-sure day with
no resort is deleted, back to saying nothing, the undecided answer.
"""

from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def forwards(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Turn not-sure days into around days, or clear them."""
    PlanDay = apps.get_model("groups", "PlanDay")
    unsure = PlanDay.objects.filter(skiing="not_sure")
    unsure.filter(resort__isnull=False).update(skiing="not_skiing")
    unsure.filter(resort__isnull=True).delete()


class Migration(migrations.Migration):
    """Drop "not sure" from the skiing answer."""

    dependencies = [
        ("groups", "0005_remove_meetups"),
    ]

    operations = [
        # Nothing to undo: the cleared days carried no answer worth keeping.
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="planday",
            name="skiing",
            field=models.CharField(
                choices=[("skiing", "Skiing"), ("not_skiing", "Not skiing")],
                default="skiing",
                max_length=10,
            ),
        ),
    ]
