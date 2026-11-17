from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.audit.services import record

from .models import Resource
from .state_machine import TransitionNotAllowed


def active_hold(resource: Resource):
    """The held or allocated reservation on `resource`, or None (story #43)."""
    from apps.matching.models import ACTIVE, Reservation  # matching builds on resources, so import late

    return (
        Reservation.objects.filter(
            content_type=ContentType.objects.get_for_model(resource), object_id=resource.pk, status__in=ACTIVE
        )
        .select_related("request_item__request")
        .first()
    )


def change_status(
    resource: Resource, action: str, *, actor, reason: str = "", held_ok: bool = False
) -> Resource:
    """
    Move `resource` along its lifecycle and record who did it, when and why in the audit log.
    Raises TransitionNotAllowed and saves nothing if the machine refuses. The caller holds the row lock
    (select_for_update inside transaction.atomic), so two people can't move the same resource at once.
    A resource held for a case can only be moved by the reservation code (`held_ok=True`), so a manual move
    can't leave a reservation pointing at stock that is back on the shelf.
    """
    if not held_ok and (hold := active_hold(resource)):
        raise TransitionNotAllowed(
            f"Held for case {hold.request_item.request.reference}; "
            "release or allocate it from the case instead."
        )
    before = resource.status
    resource.status = type(resource).machine.next(before, action)
    resource.status_since = timezone.now()
    resource.save()
    record(
        actor,
        f"{resource._meta.model_name}.status_changed",
        resource,
        before={"status": before},
        after={"status": resource.status},
        reason=reason or action,
    )
    return resource
