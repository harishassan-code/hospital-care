"""Emergency cases in the API (stories #30, #32). Shapes match frontend/src/api/emergencies.ts."""

from rest_framework import serializers

from apps.blood.models import BloodGroup, Component
from apps.equipment.models import EquipmentType
from apps.hospitals.models import BedType
from apps.matching.allocations import may_allocate
from apps.matching.models import ACTIVE, Allocation, Reservation, ReservationStatus
from apps.matching.multi import HospitalMatch
from apps.matching.reservations import resource_label
from apps.matching.scoring import FACTOR_LABELS, rank, strategy_for
from apps.operating_rooms.models import OrCapability

from .availability import local_availability
from .models import (
    REQUEST_LIFECYCLE,
    EmergencyRequest,
    RequestItem,
    RequestStatusChange,
    ResourceType,
    Severity,
)

MAX_ITEMS = 10
MAX_QUANTITY = {
    ResourceType.BLOOD: 20,
    ResourceType.BED: 5,
    ResourceType.EQUIPMENT: 5,
    ResourceType.OPERATING_ROOM: 3,  # a room is a bigger ask than a bed, so fewer per line
}
# The field each type of need must send. Fields of other types are ignored and stored blank.
REQUIRED_FIELDS = {
    ResourceType.BLOOD: ["group", "component"],
    ResourceType.BED: ["bedType"],
    ResourceType.EQUIPMENT: ["equipmentType"],
    ResourceType.OPERATING_ROOM: ["capability"],
}
MAX_NOTE = 500


class RequestItemSerializer(serializers.Serializer):
    """`{type: "blood", group, component, quantity}`, `{type: "bed", bedType, quantity}`,
    `{type: "equipment", equipmentType, quantity}` or `{type: "operatingRoom", capability, quantity}`."""

    type = serializers.ChoiceField(choices=ResourceType.choices)
    group = serializers.ChoiceField(choices=BloodGroup.choices, required=False)
    component = serializers.ChoiceField(choices=Component.choices, required=False)
    bedType = serializers.ChoiceField(choices=BedType.choices, required=False)
    equipmentType = serializers.ChoiceField(choices=EquipmentType.choices, required=False)
    capability = serializers.ChoiceField(choices=OrCapability.choices, required=False)
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        kind = attrs["type"]
        missing = {field: "This field is required." for field in REQUIRED_FIELDS[kind] if field not in attrs}
        if missing:
            raise serializers.ValidationError(missing)
        if attrs["quantity"] > MAX_QUANTITY[kind]:
            raise serializers.ValidationError(
                {"quantity": f"Ask for at most {MAX_QUANTITY[kind]} per item; add another item for more."}
            )
        return attrs

    def to_representation(self, item: RequestItem):
        data = {"type": item.resource_type, "quantity": item.quantity}
        if item.resource_type == ResourceType.BLOOD:
            data.update(group=item.blood_group, component=item.component)
        elif item.resource_type == ResourceType.BED:
            data["bedType"] = item.bed_type
        elif item.resource_type == ResourceType.EQUIPMENT:
            data["equipmentType"] = item.equipment_type
        else:
            data["capability"] = item.capability
        return data


class CaseInputSerializer(serializers.Serializer):
    """POST /api/emergencies/. No patient-identifying data: `patientRef` is optional and short."""

    severity = serializers.ChoiceField(choices=Severity.choices)
    patientRef = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    items = RequestItemSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        if len(items) > MAX_ITEMS:
            raise serializers.ValidationError(f"A case can list at most {MAX_ITEMS} needs.")
        return items


class CaseSerializer(serializers.ModelSerializer):
    """Shape of `EmergencyCase` in frontend/src/api/emergencies.ts."""

    id = serializers.CharField(source="reference")
    patientRef = serializers.CharField(source="patient_ref")
    hospital = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at")
    items = RequestItemSerializer(many=True)

    class Meta:
        model = EmergencyRequest
        fields = ["id", "severity", "status", "patientRef", "hospital", "createdBy", "createdAt", "items"]

    def get_hospital(self, case):
        return {"id": case.hospital_id, "name": case.hospital.name} if case.hospital else None

    def get_createdBy(self, case):
        user = case.created_by
        return (user.get_full_name() or user.email) if user else ""


class FeedNeedSerializer(RequestItemSerializer):
    """A need as the feed shows it: what is asked for, and how much of it is already fulfilled."""

    def to_representation(self, item: RequestItem):
        return {**super().to_representation(item), "fulfilled": item.fulfilled}


class FeedEntrySerializer(serializers.ModelSerializer):
    """One active request in the network feed (story #36). No `patientRef`, notes, timeline or author: the
    feed crosses hospitals, so it carries nothing patient-related and nothing about the staff who made the
    request. Shape of `FeedEntry` in frontend/src/api/emergencies.ts."""

    hospital = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at")
    needs = FeedNeedSerializer(source="items", many=True, read_only=True)

    class Meta:
        model = EmergencyRequest
        fields = ["reference", "hospital", "severity", "status", "createdAt", "needs"]

    def get_hospital(self, case):
        return {"id": case.hospital_id, "name": case.hospital.name} if case.hospital else None


class FeedQuerySerializer(serializers.Serializer):
    """GET /api/emergencies/feed/?type=: which needs the feed lists. Blood is the default."""

    type = serializers.ChoiceField(choices=ResourceType.choices, default=ResourceType.BLOOD)


class CaseActionSerializer(serializers.Serializer):
    """POST /api/emergencies/<reference>/actions/: one move along the lifecycle, with an optional note."""

    action = serializers.ChoiceField(choices=REQUEST_LIFECYCLE.actions)
    note = serializers.CharField(max_length=MAX_NOTE, required=False, allow_blank=True, default="")


class StatusChangeSerializer(serializers.ModelSerializer):
    """One timeline entry. Shape of `StatusChange` in frontend/src/api/emergencies.ts."""

    fromStatus = serializers.CharField(source="from_status")
    toStatus = serializers.CharField(source="to_status")
    actor = serializers.SerializerMethodField()
    at = serializers.DateTimeField()

    class Meta:
        model = RequestStatusChange
        fields = ["fromStatus", "toStatus", "action", "note", "actor", "at"]

    def get_actor(self, change):
        user = change.actor
        return (user.get_full_name() or user.email) if user else None


class ReservationSerializer(serializers.ModelSerializer):
    """One hold on a resource for a need (story #43). Shape of `CaseReservation` in
    frontend/src/api/emergencies.ts.

    Reads `hospital`, `reserved_by`, `resource` and `request_item`: select them, so the list costs no
    query per hold. `canAllocate` is for the user in the context (story #45)."""

    itemId = serializers.IntegerField(source="request_item_id", read_only=True)
    resource = serializers.SerializerMethodField()
    hospital = serializers.SerializerMethodField()
    expiresAt = serializers.DateTimeField(source="expires_at", read_only=True)
    reservedBy = serializers.SerializerMethodField()
    canAllocate = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id",
            "itemId",
            "resource",
            "hospital",
            "status",
            "expiresAt",
            "reservedBy",
            "canAllocate",
        ]

    def get_resource(self, hold):
        return resource_label(hold.resource)

    def get_hospital(self, hold):
        return {"id": hold.hospital_id, "name": hold.hospital.name}

    def get_reservedBy(self, hold):
        user = hold.reserved_by
        return user.get_full_name() or user.email

    def get_canAllocate(self, hold):
        return can_allocate_hold(self.context.get("user"), hold)


def can_allocate_hold(user, hold: Reservation) -> bool:
    """Whether `user` may allocate this hold now: it is held, and the user may allocate its type here."""
    if user is None or hold.status != ReservationStatus.HELD:
        return False
    return may_allocate(user, hold.request_item.resource_type, hold.resource)


class AllocationSerializer(serializers.ModelSerializer):
    """One allocation (story #45). Shape of `CaseAllocation` in frontend/src/api/emergencies.ts.

    Select `hospital`, `allocated_by`, `request_item` and `resource` to avoid a query per row."""

    itemId = serializers.IntegerField(source="request_item_id", read_only=True)
    resource = serializers.SerializerMethodField()
    hospital = serializers.SerializerMethodField()
    allocatedBy = serializers.SerializerMethodField()

    class Meta:
        model = Allocation
        fields = ["id", "itemId", "resource", "hospital", "allocatedBy", "at", "note"]

    def get_resource(self, allocation):
        return resource_label(allocation.resource)

    def get_hospital(self, allocation):
        return {"id": allocation.hospital_id, "name": allocation.hospital.name}

    def get_allocatedBy(self, allocation):
        user = allocation.allocated_by
        return user.get_full_name() or user.email


class HeldReservationSerializer(serializers.ModelSerializer):
    """A held reservation at the user's hospital, for the Blood page's "Reserved for cases" panel (#46).
    Shape of `HeldReservation` in frontend/src/api/emergencies.ts. Select `request_item__request`,
    `hospital`, `reserved_by` and `resource`."""

    type = serializers.CharField(source="request_item.resource_type", read_only=True)
    case = serializers.SerializerMethodField()
    need = serializers.SerializerMethodField()
    resource = serializers.SerializerMethodField()
    expiresAt = serializers.DateTimeField(source="expires_at", read_only=True)
    reservedBy = serializers.SerializerMethodField()
    canAllocate = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id",
            "type",
            "status",
            "case",
            "need",
            "resource",
            "expiresAt",
            "reservedBy",
            "canAllocate",
        ]

    def get_case(self, hold):
        case = hold.request_item.request
        return {"reference": case.reference, "severity": case.severity, "status": case.status}

    def get_need(self, hold):
        item = hold.request_item
        return {
            "itemId": item.pk,
            "label": need_label(item),
            "quantity": item.quantity,
            "fulfilled": item.fulfilled,
            "remaining": item.quantity - item.fulfilled,
        }

    def get_resource(self, hold):
        return resource_label(hold.resource)

    def get_reservedBy(self, hold):
        user = hold.reserved_by
        return user.get_full_name() or user.email

    def get_canAllocate(self, hold):
        return can_allocate_hold(self.context.get("user"), hold)


class ReservationInputSerializer(serializers.Serializer):
    """POST /api/emergencies/<reference>/reservations/: one need of the case, and how many to hold here."""

    itemId = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class AllocationInputSerializer(serializers.Serializer):
    """POST /api/reservations/<id>/allocate/ {"note"?}: an optional note for the allocation record."""

    note = serializers.CharField(max_length=MAX_NOTE, required=False, allow_blank=True, default="")


class AllocateManySerializer(serializers.Serializer):
    """POST /api/reservations/allocate/ {"ids": [...]}: the holds to allocate together, all or none."""

    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=50)

    def validate_ids(self, ids):
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError("Each reservation can be listed once.")
        return ids


class HeldQuerySerializer(serializers.Serializer):
    """GET /api/reservations/?status=held&type=blood: the held reservations to list. Both are optional."""

    status = serializers.ChoiceField(choices=[ReservationStatus.HELD], default=ReservationStatus.HELD)
    type = serializers.ChoiceField(choices=ResourceType.choices, required=False)


class CaseDetailSerializer(CaseSerializer):
    """One case with its timeline (oldest first), the actions valid from its current status (story #34), and
    what its hospital has for each need (story #33): `localAvailable` and `shortfall` per item, and the
    case's `shortfallTotal`. Only the detail computes availability, so the list stays cheap. Also the holds
    on the case's stock (story #43): `reserved` per item (held, not yet allocated) and `reservations`, the
    held and allocated ones."""

    history = StatusChangeSerializer(many=True, read_only=True)
    actions = serializers.SerializerMethodField()
    outcome = serializers.SerializerMethodField()

    class Meta(CaseSerializer.Meta):
        # shortfallTotal: see to_representation
        fields = [*CaseSerializer.Meta.fields, "history", "actions", "outcome"]

    def to_representation(self, case):
        """`self.context["user"]`, when given, decides each hold's `canAllocate` (story #45)."""
        rows = local_availability(case)  # same order as the items below: both read case.items
        data = super().to_representation(case)
        data["items"] = [
            {
                **need,
                "itemId": row.item.pk,
                "fulfilled": row.item.fulfilled,
                "remaining": row.item.quantity - row.item.fulfilled,
                "localAvailable": row.available,
                "shortfall": row.shortfall,
                "reserved": row.held,
            }
            for need, row in zip(data["items"], rows, strict=True)
        ]
        data["shortfallTotal"] = sum(row.shortfall for row in rows)
        holds = (
            Reservation.objects.filter(request_item__request=case, status__in=ACTIVE)
            .select_related("hospital", "reserved_by", "request_item")
            .prefetch_related("resource")
        )
        data["reservations"] = ReservationSerializer(holds, many=True, context=self.context).data
        allocations = (
            Allocation.objects.filter(request=case)
            .select_related("hospital", "allocated_by", "request_item")
            .prefetch_related("resource")
        )
        data["allocations"] = AllocationSerializer(allocations, many=True).data
        return data

    def get_actions(self, case):
        return [action for status, action in REQUEST_LIFECYCLE.transitions if status == case.status]

    def get_outcome(self, case):
        """The note of the latest close (story #35), or None. Reads the prefetched history: no extra query."""
        closes = [change for change in case.history.all() if change.action == "close"]
        return closes[-1].note if closes else None


def score_data(score) -> dict:
    """A score as the API shows it (story #41): each factor's label, value and weight as shares, its points
    and its detail. The points add up to the total."""
    total_weight = sum(f.weight for f in score.factors)
    return {
        "total": score.total,
        "strategy": score.strategy,
        "factors": [
            {
                "name": f.name,
                "label": FACTOR_LABELS[f.name],
                "value": round(f.value, 2),
                "weight": round(f.weight / total_weight, 2),
                "points": f.points,
                "detail": f.detail,
            }
            for f in score.factors
        ],
    }


class CandidateSerializer(serializers.Serializer):
    """One hospital that can supply a requirement (story #38), ranked and scored (story #41).
    `earliestExpiry` and `bestDonorRank` are blood only, so other types don't carry them. `recommended` is
    true only for rank 1 when its score is above 0."""

    def to_representation(self, ranked):
        candidate = ranked.candidate
        data = {
            "hospital": {"id": candidate.hospital.pk, "name": candidate.hospital.name},
            "available": candidate.available,
            "covers": candidate.covers,
            "distanceKm": None if candidate.distance_km is None else round(candidate.distance_km, 1),
            "travelMinutes": candidate.travel_minutes,
            "rank": ranked.rank,
            "score": score_data(ranked.score),
            "recommended": ranked.rank == 1 and ranked.score.total > 0,
        }
        if candidate.earliest_expiry is not None:
            data["earliestExpiry"] = serializers.DateTimeField().to_representation(candidate.earliest_expiry)
        if candidate.best_donor_rank is not None:
            data["bestDonorRank"] = candidate.best_donor_rank
        return data


def need_label(item: RequestItem) -> str:
    """A requirement as a short label for the sources list: "O- red cells", "ICU bed", "Ventilator",
    "Cardiac operating room"."""
    if item.resource_type == ResourceType.BLOOD:
        return f"{item.blood_group} {Component(item.component).label.lower()}"
    if item.resource_type == ResourceType.BED:
        return f"{BedType(item.bed_type).label} bed"
    if item.resource_type == ResourceType.EQUIPMENT:
        return EquipmentType(item.equipment_type).label
    return f"{OrCapability(item.capability).label} operating room"


class CandidateItemSerializer(serializers.Serializer):
    """One short requirement and the hospitals that can supply it, in the order the scoring gives (story #41).
    Shape of `CandidateItem` in api/emergencies.ts."""

    def to_representation(self, found):
        strategy = strategy_for(found.item.resource_type)
        return {
            "itemId": found.item.pk,
            "need": need_label(found.item),
            "shortfall": found.shortfall,
            "strategy": {"name": strategy.name, "label": strategy.label},
            "candidates": [CandidateSerializer(ranked).data for ranked in rank(found)],
        }


class HospitalMatchSerializer(serializers.Serializer):
    """One hospital judged across the case's short needs (story #42), best first. Shape of `HospitalMatch` in
    api/emergencies.ts. `recommended` is true only on rank 1, and only when that hospital has everything."""

    def to_representation(self, match: HospitalMatch):
        return {
            "rank": match.rank,
            "hospital": {"id": match.hospital.pk, "name": match.hospital.name},
            "complete": match.complete,
            "recommended": match.rank == 1 and match.complete,
            "coverage": f"{len(match.covered)} of {match.total_needs}",
            "coveredCount": len(match.covered),
            "totalNeeds": match.total_needs,
            "score": match.score,
            "distanceKm": None if match.distance_km is None else round(match.distance_km, 1),
            "travelMinutes": match.travel_minutes,
            "covered": [{"itemId": m.item.pk, "need": need_label(m.item)} for m in match.covered],
            "unmet": [
                {
                    "itemId": m.item.pk,
                    "need": need_label(m.item),
                    "missing": m.missing,
                    "available": m.available,
                }
                for m in match.unmet
            ],
        }
