"""Mark every blood unit past its expiry date as expired (story #19). Schedule it, e.g. hourly:

python manage.py expire_blood_units
"""

from django.core.management.base import BaseCommand

from apps.blood.services import expire_overdue_units


class Command(BaseCommand):
    help = "Mark blood units past their expiry date as expired, with an audit entry for each."

    def handle(self, *args, **options):
        count = expire_overdue_units()
        self.stdout.write(self.style.SUCCESS(f"Marked {count} unit(s) as expired."))
