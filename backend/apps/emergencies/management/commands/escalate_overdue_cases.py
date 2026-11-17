"""
Escalate critical emergency cases that have been unfulfilled for EMERGENCY_ESCALATION_MINUTES (story #35).

    python manage.py escalate_overdue_cases

Safe to run as often as you like: a case escalated once is no longer active, so a second run escalates
nothing. The case list and case page already run the same check on every read; this command is for a
scheduler, once the platform has one.
"""

from django.core.management.base import BaseCommand

from apps.emergencies.services import escalate_overdue


class Command(BaseCommand):
    help = "Escalate overdue critical emergency cases and print how many."

    def handle(self, *args, **options):
        count = escalate_overdue()
        self.stdout.write(f"Escalated {count} overdue case{'' if count == 1 else 's'}.")
