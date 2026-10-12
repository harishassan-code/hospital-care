"""The one call other modules use to log a critical action (story 8.1)."""

from .models import AuditLog


def record(actor, action: str, target, *, before=None, after=None, reason: str = "") -> AuditLog:
    """
    Log `action` on `target` (any model instance) by `actor` (a user, or None for the system).
    `before`/`after` are JSON-able dicts of the values that changed.
    """
    signed_in = actor is not None and actor.is_authenticated
    return AuditLog.objects.create(
        actor=actor if signed_in else None,
        actor_email=actor.email if signed_in else "",
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        target_repr=str(target)[:200],
        before=before,
        after=after,
        reason=reason[:300],
    )
