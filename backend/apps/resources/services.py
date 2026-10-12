from django.utils import timezone

from apps.audit.services import record

from .models import Resource


def change_status(resource: Resource, action: str, *, actor, reason: str = "") -> Resource:
    """
    Move `resource` along its lifecycle and record who did it, when and why in the audit log.
    Raises TransitionNotAllowed and saves nothing if the machine refuses. The caller holds the row lock
    (select_for_update inside transaction.atomic), so two people can't move the same resource at once.
    """
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
