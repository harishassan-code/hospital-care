"""The single-hospital doctor rota goes (B19): "on duty" now comes from each hospital's own specialists and their
on-call windows (B16), and from the staff rosters (B20)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hospitals", "0004_bed_type"),
    ]

    operations = [
        migrations.DeleteModel(name="DoctorShift"),
    ]
