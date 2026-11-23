"""Who the simulation acts as, and who may run it (B21)."""

from django.contrib.auth import get_user_model

from apps.accounts.models import Role

SYSTEM_EMAIL = "simulation@system.citycare.invalid"


def system_user():
    """The "CityCare simulation" account every simulated change is recorded under. An admin without a
    hospital, so the services accept its moves anywhere, but inactive with no usable password: nobody can
    sign in as it, and it receives no alerts."""
    User = get_user_model()
    user = User.objects.filter(username=SYSTEM_EMAIL).first()
    if user is None:
        user = User(
            username=SYSTEM_EMAIL,
            email=SYSTEM_EMAIL,
            first_name="CityCare",
            last_name="simulation",
            role=Role.ADMIN,
            is_active=False,
        )
        user.set_unusable_password()
        user.save()
    return user


def is_network_admin(user) -> bool:
    """The CityCare admin: an admin who works for the network, not one hospital. Only they run the clock."""
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.effective_role == Role.ADMIN
        and user.hospital_id is None
    )
