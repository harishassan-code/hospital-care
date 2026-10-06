"""Role-based access to staff modules. Mirrors ACCESS in frontend/src/features/staff/roles.ts."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role

VIEW, EDIT = "view", "edit"

ACCESS: dict[str, dict[str, str]] = {
    Role.ADMIN: {"overview": VIEW, "beds": EDIT, "blood": EDIT, "pharmacy": EDIT},
    Role.DOCTOR: {"overview": VIEW, "beds": VIEW, "blood": VIEW, "pharmacy": VIEW},
    Role.NURSE: {"overview": VIEW, "beds": EDIT, "pharmacy": VIEW},
    Role.BLOOD_BANK: {"overview": VIEW, "blood": EDIT},
    Role.PHARMACIST: {"overview": VIEW, "pharmacy": EDIT},
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
