"""Release the reservations whose hold has run out (story #43), and return their resources to stock.

python manage.py release_expired_reservations

Safe to run as often as you like: a released hold is no longer held, so a second run releases nothing. The
case and candidate pages already run the same check on every read; this command is for a scheduler, once the
platform has one."""

from django.core.management.base import BaseCommand

from apps.matching.reservations import release_expired


class Command(BaseCommand):
    help = "Release expired resource holds and print how many."

    def handle(self, *args, **options):
        count = release_expired()
        self.stdout.write(f"Released {count} expired hold{'' if count == 1 else 's'}.")
