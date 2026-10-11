"""
apps/groups/migrations/0003_planday_where_and_skiing.py — Where and skiing.

Splits a day's one status into where you are and whether you're skiing.

"At a resort" becomes skiing at that resort; "Not sure yet" and "Not
skiing" keep their meaning with no resort. The constraint tying the resort
to the status goes: any day may now name a resort, skiing or not.
"""

from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def forwards(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Turn the old "resort" status into "skiing"."""
    PlanDay = apps.get_model("groups", "PlanDay")
    PlanDay.objects.filter(skiing="resort").update(skiing="skiing")


def backwards(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Fold the two answers back into one status, losing "around" days."""
    PlanDay = apps.get_model("groups", "PlanDay")
    PlanDay.objects.filter(resort__isnull=True, skiing="skiing").update(
        skiing="not_sure"
    )
    PlanDay.objects.filter(resort__isnull=False).update(skiing="resort")


class Migration(migrations.Migration):
    """Rename status to skiing and drop the resort/status constraint."""

    dependencies = [
        ("groups", "0002_meetup_one_per_group_day"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="planday",
            name="planday_resort_matches_status",
        ),
        migrations.RenameField(
            model_name="planday",
            old_name="status",
            new_name="skiing",
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="planday",
            name="skiing",
            field=models.CharField(
                choices=[
                    ("skiing", "Skiing"),
                    ("not_sure", "Not sure yet"),
                    ("not_skiing", "Not skiing"),
                ],
                default="skiing",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="planday",
            name="resort",
            field=models.ForeignKey(
                blank=True,
                help_text="Where they'll be, skiing or not. Empty: not at a resort.",
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="plan_days",
                to="resorts.resort",
            ),
        ),
    ]
