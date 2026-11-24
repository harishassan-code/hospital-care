"""Specialist doctors and their on-call windows (B16, stories #61 and #62). Each hospital's public page (B19)
shows who is on call now by specialty, with names only for signed-in hospital staff. The rules are in
services.py."""

from django.db import models
from django.db.models import F, Prefetch, Q
from django.db.models.functions import Lower
from django.utils import timezone


class SpecialistQuerySet(models.QuerySet):
    def with_schedule(self, now):
        """Each specialist's hospital, and the windows that haven't ended by `now` (by start) in
        `upcoming_windows`. The API shows exactly these, loaded up front so a list costs a fixed number of
        queries."""
        upcoming = Prefetch(
            "on_call_windows",
            queryset=OnCallWindow.objects.filter(ends_at__gt=now).order_by("starts_at", "id"),
            to_attr="upcoming_windows",
        )
        return self.select_related("hospital").prefetch_related(upcoming)

    def available_at(self, now):
        """Active specialists on call at `now`. Both conditions go in one filter() call, so they must hold for
        the same window. Start is inclusive and end exclusive, the same rule as the public page's "In now"."""
        return self.filter(
            is_active=True, on_call_windows__starts_at__lte=now, on_call_windows__ends_at__gt=now
        ).distinct()


class Specialist(models.Model):
    """A specialist doctor at one hospital, e.g. "Dr. Ayesha Khan", Cardiology (story #61). Never deleted: a
    deactivated specialist stays in the list, marked, and is never on call."""

    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="specialists")
    name = models.CharField(max_length=150)
    specialty = models.CharField(max_length=100, help_text='Free text, e.g. "Cardiology".')
    is_active = models.BooleanField(default=True)

    objects = SpecialistQuerySet.as_manager()

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint("hospital", Lower("name"), name="specialists_name_unique_per_hospital"),
        ]

    def __str__(self):
        return self.name


class OnCallWindow(models.Model):
    """One stretch of on-call time for a specialist (story #62). It covers `starts_at` (inclusive) up to
    `ends_at` (exclusive), stored in UTC, and may run past midnight. Overlaps are refused in
    services.py, under a row lock."""

    specialist = models.ForeignKey(Specialist, on_delete=models.PROTECT, related_name="on_call_windows")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["starts_at", "id"]
        indexes = [models.Index(fields=["specialist", "starts_at"], name="oncall_specialist_start")]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="on_call_window_ends_after_start"
            ),
        ]

    def __str__(self):
        return f"On call {self.specialist.name} from {timezone.localtime(self.starts_at):%d %b %H:%M}"
