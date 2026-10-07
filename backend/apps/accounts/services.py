"""Account business rules: patient registration and email sign-in."""

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction

from .models import Role, User


class EmailTaken(Exception):
    pass


def email_in_use(email: str) -> bool:
    return User.objects.filter(email__iexact=email.strip()).exists()


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first[:150], last[:150]


@transaction.atomic
def register_patient(*, full_name: str, email: str, phone: str, password: str) -> User:
    """Self sign-up always creates a patient. Staff accounts are created by an administrator."""
    email = email.strip().lower()
    if email_in_use(email):
        raise EmailTaken(email)
    first, last = split_full_name(full_name)
    return User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=first,
        last_name=last,
        phone=phone.strip(),
        role=Role.PATIENT,
    )


def authenticate_by_email(request, email: str, password: str) -> User | None:
    """Look the user up by email (case-insensitive), then check the password through Django's backends."""
    user = User.objects.filter(email__iexact=email.strip()).first()
    if user is None:
        # Still run a password hash so a missing account takes as long as a wrong password.
        User().set_password(password)
        return None
    return authenticate(request, username=user.get_username(), password=password)


# Lockout after repeated failed sign-ins (LOGIN-N03). Counted per account, not per IP address:
# a hospital's computers usually share one public address, so an IP limit would lock out a whole ward.
LOCKOUT_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60


def _failed_key(email: str) -> str:
    return f"login-failures:{email.strip().lower()}"


def is_locked_out(email: str) -> bool:
    return cache.get(_failed_key(email), 0) >= LOCKOUT_ATTEMPTS


def record_failed_login(email: str) -> None:
    key = _failed_key(email)
    cache.add(key, 0, timeout=LOCKOUT_SECONDS)
    cache.incr(key)


def clear_failed_logins(email: str) -> None:
    cache.delete(_failed_key(email))
