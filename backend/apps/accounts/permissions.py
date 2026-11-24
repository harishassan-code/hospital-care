"""
Role-based access to staff modules. Mirrors ACCESS in frontend/src/features/staff/roles.ts, which only hides
what this enforces. The table is in docs/architecture/api-contracts.md.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import STAFF_ROLES, Role

VIEW, EDIT = "view", "edit"

ACCESS: dict[str, dict[str, str]] = {
    Role.ADMIN: {
        "overview": VIEW,
        "alerts": VIEW,  # the user's own notifications (B07); a personal list, so view only
        "emergencies": EDIT,
        "beds": EDIT,
        "blood": EDIT,
        "donors": EDIT,
        "pharmacy": EDIT,
        "hospitals": EDIT,
        "specialists": EDIT,
        "users": EDIT,
        "equipment": EDIT,
        "operatingRooms": EDIT,
        "orBookings": EDIT,
        "transfers": EDIT,
        "ambulances": EDIT,
        "commandCentre": VIEW,  # the whole network's figures, read-only (story #55)
        "audit": VIEW,
        "reports": VIEW,  # operational reports and their export (B18, #66, #67); "management" is the admin
        "simulation": EDIT,  # the city clock and scenarios (B21): only the admin without a hospital, below
        "metrics": VIEW,  # the hourly figures behind the trend charts (B22)
        "emergencyDepartment": EDIT,  # the queue and its actions (B22)
        "staffing": EDIT,  # who is on duty, against the rota (B22)
    },
    Role.DOCTOR: {
        "overview": VIEW,
        "alerts": VIEW,
        "emergencies": EDIT,
        "beds": VIEW,
        "blood": VIEW,
        "pharmacy": VIEW,
        "hospitals": VIEW,
        "specialists": VIEW,
        "equipment": VIEW,
        "operatingRooms": VIEW,
        "orBookings": EDIT,  # surgeons book their own slots; the room registry stays admin/nurse
        "transfers": EDIT,  # who may approve or receive is narrowed per move in apps.transfers.services
        "ambulances": VIEW,
        "metrics": VIEW,
        "emergencyDepartment": EDIT,
        "staffing": VIEW,
    },
    Role.NURSE: {
        "overview": VIEW,
        "alerts": VIEW,
        "emergencies": EDIT,
        "beds": EDIT,
        "pharmacy": VIEW,
        "hospitals": VIEW,
        "specialists": EDIT,
        "equipment": EDIT,
        "operatingRooms": EDIT,
        "orBookings": EDIT,
        "transfers": EDIT,
        "ambulances": EDIT,
        "metrics": VIEW,
        "emergencyDepartment": EDIT,
        "staffing": EDIT,  # the nurse in charge covers gaps
    },
    Role.BLOOD_BANK: {
        "overview": VIEW,
        "alerts": VIEW,
        "emergencies": VIEW,
        "blood": EDIT,
        "donors": EDIT,  # personal data (names, phones, emails): doctors and nurses don't see donors
        "hospitals": VIEW,
        "specialists": VIEW,
        "transfers": EDIT,
        "metrics": VIEW,
    },
    Role.PHARMACIST: {
        "overview": VIEW,
        "alerts": VIEW,
        "emergencies": VIEW,
        "pharmacy": EDIT,
        "hospitals": VIEW,
        "specialists": VIEW,
        "metrics": VIEW,
    },
    Role.PATIENT: {},
}


def can_see(role: str, module: str) -> bool:
    return module in ACCESS.get(role, {})


def can_edit(role: str, module: str) -> bool:
    return ACCESS.get(role, {}).get(module) == EDIT


def module_permission(module: str) -> type[BasePermission]:
    """Permission class for one module: reads need 'view', writes need 'edit'."""

    class ModuleAccess(BasePermission):
        message = "Your role can't do this in this module."

        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            role = user.effective_role
            if request.method in SAFE_METHODS:
                return can_see(role, module)
            return can_edit(role, module)

    ModuleAccess.__name__ = f"{module.title()}ModuleAccess"
    return ModuleAccess


def own_hospital(queryset, user):
    """Users who work at a hospital see only its rows. Admins without a hospital see the whole network. Anyone
    else without a hospital sees only rows that have none either (old data), as changeable_by() does: a role
    change that left out the hospital must not open every hospital's records (functional sweep, F11).
    Always a fresh queryset: handing back a shared one (e.g. a module-level constant) would cache its rows."""
    if user.hospital_id:
        return queryset.filter(hospital_id=user.hospital_id)
    if user.effective_role == Role.ADMIN:
        return queryset.all()
    return queryset.filter(hospital_id__isnull=True)


def changeable_by(queryset, user):
    """The rows the user may change, filtered the way may_change() checks them: admins see every row, everyone
    else only their own hospital's. A row outside this is a 404, as if it didn't exist (B13, F1 to F3)."""
    if user.effective_role == Role.ADMIN:
        return queryset.all()
    return queryset.filter(hospital_id=user.hospital_id)


def may_change(user, resource) -> bool:
    """
    Own-hospital rule: admins manage the whole network; everyone else only their own hospital's resources.
    Rows from before Sprint 2 have no hospital and match users without one, so old data keeps working.
    """
    return user.effective_role == Role.ADMIN or resource.hospital_id == user.hospital_id


# ── Patient information: the minimum necessary (B23, docs/testing/privacy-review.md) ───────────────────────

# The roles that treat patients, and the admin who runs a hospital.
PATIENT_ROLES = (Role.DOCTOR, Role.NURSE, Role.ADMIN)


def sees_patients(user, hospital_id) -> bool:
    """Whether `user` may see patient-level details (initials, age, sex, a case's patient reference and notes,
    a visit's details) of a record at `hospital_id`. Only doctors, nurses and the admin of that same hospital:
    blood bank staff and pharmacists work from a case's needs, an admin who runs one hospital never sees
    another hospital's patients, and the CityCare admin (no hospital) sees counts and statuses only. Doctors
    and nurses without a hospital match records without one (data from before Sprint 2), as `own_hospital`
    does."""
    if not (user and user.is_authenticated):
        return False
    role = user.effective_role
    if role in (Role.DOCTOR, Role.NURSE):
        return user.hospital_id == hospital_id
    return role == Role.ADMIN and user.hospital_id is not None and user.hospital_id == hospital_id


def sees_case_patient(user, case) -> bool:
    """A case's patient reference and notes: its own hospital's clinical staff, and the receiving hospital's
    once a move of the patient to it has been requested (they need to know who is coming)."""
    if sees_patients(user, case.hospital_id):
        return True
    if not (user and user.is_authenticated and user.effective_role in PATIENT_ROLES and user.hospital_id):
        return False
    from apps.emergencies.models import PatientTransfer  # emergencies builds on accounts

    return PatientTransfer.objects.filter(request=case, to_hospital_id=user.hospital_id).exists()


class IsStaff(BasePermission):
    """Signed in with a staff role, admins included (with or without a hospital). Patients and
    signed-out users get 403. Personal data such as notifications has no module, so no ACCESS row."""

    message = "Only staff can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.effective_role in STAFF_ROLES)


class IsNetworkAdmin(BasePermission):
    """The CityCare admin (B21): an admin who works for the network, not one hospital. Only they run the
    simulation's clock and scenarios; a hospital's admin can't, though both have the module."""

    message = "Only the CityCare network admin can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and can_edit(user.effective_role, "simulation")
            and user.hospital_id is None
        )
