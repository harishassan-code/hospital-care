"""Run the city simulation from the command line (B21).

python manage.py simulate              # keep the city running: a tick every 15 seconds until Ctrl-C
python manage.py simulate --minutes 90 # run the next 90 city minutes now, then stop
"""

import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.simulation import engine
from apps.simulation.models import SimulationState


class Command(BaseCommand):
    help = "Run the live city simulation (needs SIMULATION_ENABLED=true)."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, help="Advance the city this many minutes now, then stop.")

    def handle(self, *args, minutes=None, **options):
        if not settings.SIMULATION_ENABLED:
            raise CommandError("The simulation is off. Set SIMULATION_ENABLED=true to run it.")
        if minutes:
            state = engine.state()
            target = state.progress + timedelta(minutes=minutes)
            SimulationState.objects.filter(pk=1).update(
                fast_forward_from=state.progress, fast_forward_to=target
            )
            while True:
                result = engine.run(force=True, budget=60)
                if not result.get("behind"):
                    break
            self.stdout.write(self.style.SUCCESS(f"City clock now {target:%Y-%m-%d %H:%M} (UTC)."))
            return
        self.stdout.write("Running the city; Ctrl-C to stop.")
        while True:
            result = engine.run(force=True)
            if result.get("ran"):
                self.stdout.write(f"  up to {result['progress']:%H:%M:%S} UTC in {result['seconds']} s")
            time.sleep(engine.MIN_INTERVAL.total_seconds())
