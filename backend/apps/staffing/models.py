"""Hospital staff rosters (B20): the doctors and nurses each hospital plans its shifts with, and when each
shift actually started and ended. A roster entry is not a sign-in account; most staff never use the system
themselves. On staging every name is synthetic."""

from django.db import models


class StaffRole(models.TextChoices):
    DOCTOR = "doctor", "Doctor"
    NURSE = "nurse", "Nurse"


class StaffMember(models.Model):
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="staff_members")
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=StaffRole.choices)
    department = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["hospital", "department", "role", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}, {self.department})"


class ShiftQuerySet(models.QuerySet):
    def on_duty_at(self, at):
        """Shifts whose person had clocked in by `at` and not yet clocked out."""
        return self.filter(clocked_in_at__lte=at).filter(
            models.Q(clocked_out_at__isnull=True) | models.Q(clocked_out_at__gt=at)
        )

    def covering(self, at):
        """Shifts planned to run at `at`, whether or not anyone clocked in."""
        return self.filter(starts_at__lte=at, ends_at__gt=at)


class Shift(models.Model):
    """One planned shift. `clocked_in_at` and `clocked_out_at` stay empty until it happens; a shift whose
    start passed without a clock-in was missed."""

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="shifts")
    # The staff member's hospital, kept here too so "who is on duty here" is one indexed query.
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    clocked_in_at = models.DateTimeField(null=True, blank=True)
    clocked_out_at = models.DateTimeField(null=True, blank=True)

    objects = ShiftQuerySet.as_manager()

    class Meta:
        ordering = ["starts_at", "id"]
        indexes = [
            models.Index(fields=["hospital", "starts_at"], name="staffing_shift_hosp_start"),
            models.Index(fields=["hospital", "ends_at"], name="staffing_shift_hosp_end"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")), name="staffing_shift_ends_after_start"
            ),
        ]

    def __str__(self):
        return f"{self.staff.name}: {self.starts_at:%d %b %H:%M}–{self.ends_at:%H:%M}"
