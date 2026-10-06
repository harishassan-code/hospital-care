"""Account business rules: patient registration and email sign-in."""

from django.contrib.auth import authenticate
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
