from django.db import migrations

# The starting managed list (story 1.3). Admins add more in Django admin; codes never change once used.
CAPABILITIES = [
    ("trauma", "Trauma centre"),
    ("icu", "Intensive care unit"),
    ("nicu", "Neonatal ICU"),
    ("bloodBank", "Blood bank"),
    ("maternity", "Maternity"),
    ("cathLab", "Cardiac catheterisation lab"),
    ("stroke", "Stroke unit"),
    ("burns", "Burns unit"),
    ("dialysis", "Dialysis"),
    ("ct", "CT scanner"),
    ("mri", "MRI scanner"),
    ("paediatrics", "Paediatrics"),
]


def add(apps, schema_editor):
    Capability = apps.get_model("hospitals", "Capability")
    for code, name in CAPABILITIES:
        Capability.objects.get_or_create(code=code, defaults={"name": name})


def remove(apps, schema_editor):
    apps.get_model("hospitals", "Capability").objects.filter(code__in=[c for c, _ in CAPABILITIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("hospitals", "0002_hospital_network")]

    operations = [migrations.RunPython(add, remove)]
