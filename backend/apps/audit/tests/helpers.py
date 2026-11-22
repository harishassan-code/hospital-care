"""Audit rows for the B10 tests. `at` is set by auto_now_add, so the clock is pinned during create."""

from datetime import datetime
from unittest.mock import patch

from apps.audit.models import AuditLog


def stamp(when: str = "2026-11-18T10:00:00+00:00", **fields) -> AuditLog:
    """An audit row written at `when` (ISO 8601 with an offset). Any field can be overridden."""
    values = {
        "actor_email": "admin@example.com",
        "action": "bed.status_changed",
        "target_type": "beds.bed",
        "target_id": "1",
        "target_repr": "Bed 1",
        "reason": "",
        **fields,
    }
    with patch("django.utils.timezone.now", return_value=datetime.fromisoformat(when)):
        return AuditLog.objects.create(**values)
