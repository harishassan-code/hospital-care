from django.utils import timezone

from apps.audit.services import record

from .models import BloodUnit
from .serializers import BloodUnitSerializer


def register_unit(serializer, actor) -> BloodUnit:
    """Create a blood unit from a valid serializer, scoped to the actor's hospital, and audit-log it."""
    unit = serializer.save(hospital=getattr(actor, "hospital", None))
    after = BloodUnitSerializer(unit, context={"now": timezone.now()}).data
    record(actor, "bloodunit.registered", unit, after=dict(after))
    return unit
