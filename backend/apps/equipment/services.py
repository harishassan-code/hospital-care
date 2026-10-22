"""Equipment registry rules (story #26)."""

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record

from .models import Equipment


def register_equipment(serializer, actor) -> Equipment:
    """Save new equipment in the actor's hospital and audit-log it. Asset tags are unique per hospital."""
    hospital = getattr(actor, "hospital", None)
    identifier = serializer.validated_data["identifier"]
    if Equipment.objects.filter(hospital=hospital, identifier__iexact=identifier).exists():
        raise ValidationError({"identifier": ["This asset tag is already registered in your hospital."]})
    try:
        with transaction.atomic():
            equipment = serializer.save(hospital=hospital)
    except IntegrityError:  # someone registered the same tag at the same moment
        raise ValidationError(
            {"identifier": ["This asset tag is already registered in your hospital."]}
        ) from None
    record(
        actor,
        "equipment.registered",
        equipment,
        after={
            "identifier": equipment.identifier,
            "type": equipment.equipment_type,
            "status": equipment.status,
        },
    )
    return equipment
