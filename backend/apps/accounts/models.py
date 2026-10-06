from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class Role(models.TextChoices):
    """Values match the frontend's `Role` ids (frontend/src/features/staff/roles.ts), plus patients."""

    ADMIN = "admin", "Admin"
    DOCTOR = "doctor", "Doctor"
    NURSE = "nurse", "Nurse"
    BLOOD_BANK = "bloodBank", "Blood bank"
    PHARMACIST = "pharmacist", "Pharmacist"
    PATIENT = "patient", "Patient"


STAFF_ROLES = {Role.ADMIN, Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST}


class User(AbstractUser):
    """Project user. People sign in with their email; `username` is kept equal to it for Django admin."""

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    phone = models.CharField(max_length=20, blank=True)

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                condition=~models.Q(email=""),
            )
        ]

    @property
    def effective_role(self) -> str:
        """Superusers always act as admins, whatever their stored role."""
        return Role.ADMIN if self.is_superuser else self.role

    @property
    def is_hospital_staff(self) -> bool:
        return self.effective_role in STAFF_ROLES
