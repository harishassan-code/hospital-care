"""Transfers in the API (stories #47, #48, #49). Shape of `Transfer` in the frontend's api/transfers.ts.
The case detail (apps.emergencies) lists the same shape, so it imports this module late."""

from rest_framework import serializers

from apps.emergencies.serializers import need_label
from apps.hospitals.models import Hospital
from apps.matching.reservations import resource_label

from .models import Transfer, TransferStatus
from .services import actions_for

MAX_NOTE = 500
ACTIONS = ("approve", "reject", "dispatch", "startTransit", "deliver", "cancel")


class TransferInputSerializer(serializers.Serializer):
    """POST /api/transfers/: one need of a case, the supplying hospital, and how many."""

    itemId = serializers.IntegerField()
    supplierId = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(max_length=MAX_NOTE, required=False, allow_blank=True, default="")

    def validate_supplierId(self, value):
        """An active hospital. The validated value is the hospital itself."""
        hospital = Hospital.objects.filter(pk=value, is_active=True).first()
        if hospital is None:
            raise serializers.ValidationError("No active hospital with that id.")
        return hospital


class TransferActionSerializer(serializers.Serializer):
    """POST /api/transfers/<id>/actions/: one move, with a reason (required for reject) and a note."""

    action = serializers.ChoiceField(choices=ACTIONS)
    reason = serializers.CharField(max_length=MAX_NOTE, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=MAX_NOTE, required=False, allow_blank=True, default="")


class TransferQuerySerializer(serializers.Serializer):
    """GET /api/transfers/?direction=&status=: both filters are optional."""

    direction = serializers.ChoiceField(choices=["incoming", "outgoing"], required=False)
    status = serializers.ChoiceField(choices=TransferStatus.choices, required=False)


class TransferSerializer(serializers.Serializer):
    """One transfer. Use `Transfer.objects.with_details()` so the list costs a fixed number of queries.
    `self.context["user"]` decides `actions`."""

    def to_representation(self, transfer: Transfer):
        item = transfer.request_item
        case = item.request
        holds = list(transfer.reservations.all())
        requester = transfer.requested_by
        user = self.context.get("user")
        return {
            "id": transfer.pk,
            "case": {"reference": case.reference, "severity": case.severity},
            "itemId": item.pk,
            "resourceType": item.resource_type,
            "need": need_label(item),
            "supplier": {"id": transfer.supplier_id, "name": transfer.supplier.name},
            "receiver": {"id": transfer.receiver_id, "name": transfer.receiver.name},
            "quantity": transfer.quantity,
            "approved": len(holds),
            "resources": [resource_label(hold.resource) for hold in holds],
            "status": transfer.status,
            "reason": transfer.reason,
            "requestedBy": requester.get_full_name() or requester.email,
            "createdAt": serializers.DateTimeField().to_representation(transfer.created_at),
            "history": [
                {
                    "fromStatus": change.from_status,
                    "toStatus": change.to_status,
                    "action": change.action,
                    "note": change.note,
                    "actor": (change.actor.get_full_name() or change.actor.email) if change.actor else None,
                    "at": serializers.DateTimeField().to_representation(change.at),
                }
                for change in transfer.history.all()
            ],
            "actions": actions_for(user, transfer) if user is not None else [],
        }
