"""Fixed data for the B18 report tests. Times are pinned, so `created_at` (auto_now_add) lands where asked."""

import itertools
from datetime import datetime
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType

from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.models import RequestStatusChange
from apps.matching.models import Allocation, Reservation, ReservationStatus
from apps.matching.tests.reservation_support import case

_numbers = itertools.count(1)


def when(text: str) -> datetime:
    """ISO 8601 with an offset, e.g. "2026-11-05T10:00:00+05:00" (Karachi)."""
    return datetime.fromisoformat(text)


def opened(hospital, at: str, *needs, severity="high", status="open"):
    """A case opened at `at`."""
    with patch("django.utils.timezone.now", return_value=when(at)):
        return case(hospital, *needs, status=status, severity=severity)


def fulfilled(emergency, at: str):
    """The case's timeline reaches fulfilled at `at`."""
    return RequestStatusChange.objects.create(
        request=emergency, from_status="matching", to_status="fulfilled", action="allocate", at=when(at)
    )


def allocated(item, resource, *, hospital, actor, at: str):
    """An allocation of `resource` to `item` at `at`, with the issued hold behind it."""
    reservation = Reservation.objects.create(
        request_item=item,
        resource=resource,
        hospital=hospital,
        reserved_by=actor,
        status=ReservationStatus.ALLOCATED,
        expires_at=when(at),
    )
    return Allocation.objects.create(
        reservation=reservation,
        request=item.request,
        request_item=item,
        hospital=hospital,
        content_type=ContentType.objects.get_for_model(resource),
        object_id=resource.pk,
        allocated_by=actor,
        at=when(at),
    )


def blood_unit(
    hospital, *, expires: str, status=UnitStatus.AVAILABLE, group="O-", component="redCells", since=None
):
    return BloodUnit.objects.create(
        donation_number=f"RPT-{next(_numbers):05d}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=when("2026-09-01T09:00:00+05:00"),
        expires_at=when(expires),
        status=status,
        status_since=when(since or "2026-09-01T09:00:00+05:00"),
        location="Blood fridge 1",
    )
