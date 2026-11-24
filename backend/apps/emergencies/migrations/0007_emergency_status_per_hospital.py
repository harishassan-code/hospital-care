"""Emergency status per hospital (B19). The single row from before belonged to the first hospital (the one the
landing page was written for), so it goes to that hospital. Without any hospital it has no owner and goes."""

import django.db.models.deletion
from django.db import migrations, models


def give_row_to_first_hospital(apps, schema_editor):
    EmergencyStatus = apps.get_model("emergencies", "EmergencyStatus")
    Hospital = apps.get_model("hospitals", "Hospital")
    first = Hospital.objects.order_by("pk").first()
    rows = list(EmergencyStatus.objects.order_by("pk"))
    if first is None:
        EmergencyStatus.objects.all().delete()
        return
    if rows:
        keep = rows[0]
        EmergencyStatus.objects.exclude(pk=keep.pk).delete()
        keep.hospital = first
        keep.save(update_fields=["hospital"])


class Migration(migrations.Migration):
    dependencies = [
        ("hospitals", "0004_bed_type"),
        ("emergencies", "0006_patient_transfer"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="emergencystatus", options={"verbose_name_plural": "emergency statuses"}
        ),
        migrations.AddField(
            model_name="emergencystatus",
            name="hospital",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="emergency_status",
                to="hospitals.hospital",
            ),
        ),
        migrations.RunPython(give_row_to_first_hospital, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="emergencystatus",
            name="hospital",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="emergency_status",
                to="hospitals.hospital",
            ),
        ),
    ]
