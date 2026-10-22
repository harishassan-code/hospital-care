"""
Role-based access to staff modules. Mirrors ACCESS in frontend/src/features/staff/roles.ts, which only hides
what this enforces. The table is in docs/architecture/api-contracts.md.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role

VIEW, EDIT = "view", "edit"

ACCESS: dict[str, dict[str, str]] = {
    Role.ADMIN: {
        "overview": VIEW,
        "beds": EDIT,
        "blood": EDIT,
        "pharmacy": EDIT,
        "hospitals": EDIT,
        "users": EDIT,
        "equipment": EDIT,
    },
    Role.DOCTOR: {
        "overview": VIEW,
        "beds": VIEW,
        "blood": VIEW,
        "pharmacy": VIEW,
        "hospitals": VIEW,
        "equipment": VIEW,
    },
    Role.NURSE: {
        "overview": VIEW,
        "beds": EDIT,
        "pharmacy": VIEW,
        "hospitals": VIEW,
        "equipment": EDIT,
    },
    Role.BLOOD_BANK: {"overview": VIEW, "blood": EDIT, "hospitals": VIEW},
    Role.PHARMACIST: {"overview": VIEW, "pharmacy": EDIT, "hospitals": VIEW},
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


def may_change(user, resource) -> bool:
    """
    Own-hospital rule: admins manage the whole network; everyone else only their own hospital's resources.
    Rows from before Sprint 2 have no hospital and match users without one, so old data keeps working.
    """
    return user.effective_role == Role.ADMIN or resource.hospital_id == user.hospital_id
