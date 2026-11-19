import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("hospitals", "0004_bed_type"),
        ("transfers", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Ambulance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status_since", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "identifier",
                    models.CharField(help_text="Call sign, e.g. AMB-12. Unique within a hospital.", max_length=40),
                ),
                (
                    "ambulance_type",
                    models.CharField(
                        choices=[
                            ("basic", "Basic life support"),
                            ("advanced", "Advanced life support"),
                            ("transport", "Patient transport"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Available"),
                            ("inUse", "In use"),
                            ("maintenance", "Maintenance"),
                            ("outOfService", "Out of service"),
                        ],
                        default="available",
                        max_length=20,
                    ),
                ),
                (
                    "hospital",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="hospitals.hospital",
                    ),
                ),
                (
                    "storage_location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="hospitals.storagelocation",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "ambulances",
                "ordering": ["identifier"],
            },
        ),
        migrations.CreateModel(
            name="Trip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("dispatched", "Dispatched"),
                            ("enRoute", "En route"),
                            ("arrived", "Arrived"),
                            ("completed", "Completed"),
                        ],
                        default="dispatched",
                        max_length=12,
                    ),
                ),
                (
                    "eta_minutes",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="Estimated drive time from supplier to receiver when dispatched.",
                        null=True,
                    ),
                ),
                ("dispatched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("status_since", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "ambulance",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trips", to="ambulances.ambulance"),
                ),
                (
                    "dispatched_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "transfer",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT, related_name="trip", to="transfers.transfer"
                    ),
                ),
            ],
            options={
                "ordering": ["-dispatched_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="ambulance",
            index=models.Index(fields=["ambulance_type", "status"], name="ambulances__ambulan_db757c_idx"),
        ),
        migrations.AddConstraint(
            model_name="ambulance",
            constraint=models.UniqueConstraint(
                models.F("hospital"),
                django.db.models.functions.text.Lower("identifier"),
                name="ambulance_identifier_unique_per_hospital",
                nulls_distinct=False,
            ),
        ),
        migrations.AddIndex(
            model_name="trip",
            index=models.Index(fields=["status"], name="trips_status"),
        ),
    ]