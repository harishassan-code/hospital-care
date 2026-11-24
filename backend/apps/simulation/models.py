"""The live city simulation's state (B21): one row for the city clock and the engine, and a log of what the
engine did, for the CityCare admin's panel."""

from django.db import models
from django.utils import timezone


class Scenario(models.TextChoices):
    REGULAR = "regular", "Regular day"
    FLU = "flu", "Flu season"
    SLOW = "slow", "Slow day"


class SimulationState(models.Model):
    """A single row (pk=1). The city clock reads `anchor_city + (real now - anchor_real) x speed`, or stays at
    `anchor_city` while paused, or follows `progress` (how far the engine got) while fast-forwarding."""

    enabled = models.BooleanField(default=True, help_text="Off: nothing moves; the clock is the real one.")
    paused = models.BooleanField(default=False)
    speed = models.FloatField(default=1.0)
    anchor_real = models.DateTimeField(default=timezone.now)
    anchor_city = models.DateTimeField(default=timezone.now)
    progress = models.DateTimeField(default=timezone.now, help_text="City time the engine has reached.")
    fast_forward_to = models.DateTimeField(null=True, blank=True)
    fast_forward_from = models.DateTimeField(null=True, blank=True)
    scenario = models.CharField(max_length=10, choices=Scenario.choices, default=Scenario.REGULAR)
    # A mass-casualty event, while it lasts: where it happened and when it ends (city time).
    incident_lat = models.FloatField(null=True, blank=True)
    incident_lng = models.FloatField(null=True, blank=True)
    incident_until = models.DateTimeField(null=True, blank=True)
    # One tick at a time, across every copy of the app: the tick that holds the lease until this (real) time.
    lease_until = models.DateTimeField(null=True, blank=True)
    last_tick_real = models.DateTimeField(null=True, blank=True)
    # This hour's running counts per hospital (flushed into MetricSnapshot at the hour), and when each kind of
    # alert last went out per hospital (rate limit).
    counters = models.JSONField(default=dict, blank=True)
    alerts_sent = models.JSONField(default=dict, blank=True)
    seed = models.PositiveIntegerField(default=7)

    class Meta:
        verbose_name = "simulation state"

    def __str__(self):
        return (
            f"Simulation ({self.get_scenario_display()}, {self.speed:g}x{', paused' if self.paused else ''})"
        )


class SimEvent(models.Model):
    """Something the simulation did that a person would notice, for the CityCare admin's list."""

    at = models.DateTimeField(help_text="City time.")
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.CASCADE, null=True, related_name="+")
    kind = models.CharField(max_length=40)
    message = models.CharField(max_length=300)

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [models.Index(fields=["at"], name="simulation_event_at")]

    def __str__(self):
        return self.message
