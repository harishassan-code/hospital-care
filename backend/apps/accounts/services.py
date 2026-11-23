"""Account business rules: patient registration and email sign-in."""

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction

from apps.audit.services import record

from .models import Role, User


class EmailTaken(Exception):
    pass


class RoleLocked(Exception):
    """This account's role can't be changed here. The message says why."""


class HospitalRequired(Exception):
    """A staff role that works at one hospital was given without a hospital."""


# Staff who work at one hospital. An account with one of these roles must have a hospital: without one it
# could neither see nor change any hospital's records (own_hospital, changeable_by). Admins may have none
# (functional sweep, F12).
HOSPITAL_ROLES = frozenset({Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST})
_KEEP = object()


@transaction.atomic
def change_role(actor: User, user: User, role: str, hospital=_KEEP) -> User:
    """Change someone's role, and optionally the hospital they work at, and log it. Takes effect on their next
    request (roles are read per request). `hospital` left out keeps theirs; None clears it."""
    if user.pk == actor.pk:
        raise RoleLocked("You can't change your own role.")
    if user.is_superuser:
        raise RoleLocked("This account is a superuser. Change it in Django admin.")
    new_hospital = user.hospital if hospital is _KEEP else hospital
    if role in HOSPITAL_ROLES and new_hospital is None:
        raise HospitalRequired("Choose the hospital this person works at.")
    before, after, fields = {}, {}, []
    if role != user.role:
        before["role"], after["role"] = user.role, role
        user.role = role
        fields.append("role")
    if hospital is not _KEEP and user.hospital_id != (hospital.pk if hospital else None):
        before["hospital"] = user.hospital.name if user.hospital_id else None
        after["hospital"] = hospital.name if hospital else None
        user.hospital = hospital
        fields.append("hospital")
    if fields:
        user.save(update_fields=fields)
        record(actor, "user.role_changed", user, before=before, after=after)
    return user


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
