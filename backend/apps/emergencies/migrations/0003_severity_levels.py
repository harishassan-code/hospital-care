from django.db import migrations, models

# Old severity -> new. Critical is unchanged. Nothing maps to low going forward (the old scale had no equivalent).
FORWARD = {"urgent": "high", "routine": "moderate"}
BACKWARD = {"high": "urgent", "moderate": "routine", "low": "routine"}


def remap(mapping):
    """A data step that renames severities, one update per old value."""

    def run(apps, schema_editor):
        EmergencyRequest = apps.get_model("emergencies", "EmergencyRequest")
        for old, new in mapping.items():
            EmergencyRequest.objects.filter(severity=old).update(severity=new)

    return run


class Migration(migrations.Migration):

    dependencies = [
        ("emergencies", "0002_emergency_cases"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emergencyrequest",
            name="severity",
            field=models.CharField(
                choices=[("critical", "Critical"), ("high", "High"), ("moderate", "Moderate"), ("low", "Low")],
                max_length=10,
            ),
        ),
        migrations.RunPython(remap(FORWARD), remap(BACKWARD)),
    ]
