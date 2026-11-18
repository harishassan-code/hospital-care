"""Inter-hospital transfers (stories #47, #48, #49; bolts B01 to B03): one hospital asks another for a
quantity of one need of one emergency case, the supplier approves (holding the stock), ships it, and the
receiving hospital confirms receipt (allocating it to the case).

A transfer is the request and its lifecycle. Its holds are ordinary reservations (apps.matching), linked to
the transfer while it is live, so the expiry sweep and the case page leave them alone. The rules are in
services.py."""

from django.conf import settings
from django.db import models
from django.db.models import Prefetch
from django.utils import timezone

from apps.ambulances.models import Trip
from apps.matching.models import Reservation
from apps.resources.state_machine import StateMachine


class TransferStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    APPROVED = "approved", "Approved"
    DISPATCHED = "dispatched", "Dispatched"
    IN_TRANSIT = "inTransit", "In transit"
    DELIVERED = "delivered", "Delivered"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


T = TransferStatus

# The statuses whose holds are pinned: the expiry sweep skips them, and only the transfer moves them.
LIVE = (T.APPROVED, T.DISPATCHED, T.IN_TRANSIT)

# Story #48 (see the tracking spec's lifecycle table). Delivered, rejected and cancelled are final.
TRANSFER_LIFECYCLE = StateMachine(
    "transfer",
    TransferStatus,
    {
        (T.REQUESTED, "approve"): T.APPROVED,
        (T.REQUESTED, "reject"): T.REJECTED,
        (T.REQUESTED, "cancel"): T.CANCELLED,
        (T.APPROVED, "dispatch"): T.DISPATCHED,
        (T.APPROVED, "cancel"): T.CANCELLED,
        (T.DISPATCHED, "startTransit"): T.IN_TRANSIT,
        (T.DISPATCHED, "deliver"): T.DELIVERED,
        (T.DISPATCHED, "cancel"): T.CANCELLED,
        (T.IN_TRANSIT, "deliver"): T.DELIVERED,
        (T.IN_TRANSIT, "cancel"): T.CANCELLED,
    },
)


class TransferQuerySet(models.QuerySet):
    def with_details(self):
        """Everything the API shows for a transfer, loaded up front: a list of them costs a fixed number of
        queries, however many transfers it has."""
        holds = Prefetch("reservations", queryset=Reservation.objects.prefetch_related("resource"))
        history = Prefetch("history", queryset=TransferStatusChange.objects.select_related("actor"))
        trips = Prefetch(
            "trips", queryset=Trip.objects.select_related("ambulance", "dispatched_by", "transfer")
        )
        return self.select_related(
            "request_item__request", "supplier", "receiver", "requested_by"
        ).prefetch_related(holds, history, trips)


class Transfer(models.Model):
    """One ask of one hospital for a quantity of one need of a case (story #47). The receiver is the case's
    hospital at the time of the request."""

    request_item = models.ForeignKey(
        "emergencies.RequestItem", on_delete=models.PROTECT, related_name="transfers"
    )
    supplier = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    receiver = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=TransferStatus.choices, default=TransferStatus.REQUESTED)
    reason = models.TextField(blank=True, help_text="Why the request was rejected or cancelled.")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    reservations = models.ManyToManyField(
        "matching.Reservation",
        blank=True,
        related_name="transfers",
        help_text="The holds made at the supplier when the transfer was approved.",
    )

    objects = TransferQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status"], name="transfers_status"),
            models.Index(fields=["supplier", "status"], name="transfers_supplier_status"),
            models.Index(fields=["receiver", "status"], name="transfers_receiver_status"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="transfers_quantity_positive"),
            models.CheckConstraint(
                condition=~models.Q(supplier=models.F("receiver")), name="transfers_supplier_not_receiver"
            ),
        ]

    def __str__(self):
        return f"Transfer #{self.pk}"


class TransferStatusChange(models.Model):
    """One entry in a transfer's history (story #48). The first is the request: "" to requested, action
    "request". Same shape as the case timeline (emergencies.RequestStatusChange)."""

    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12, choices=TransferStatus.choices)
    action = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["at", "id"]
        verbose_name_plural = "transfer status changes"

    def __str__(self):
        return f"{self.transfer_id}: {self.from_status or '-'} → {self.to_status}"
