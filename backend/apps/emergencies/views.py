from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission, own_hospital
from apps.audit.services import record_view
from apps.matching.candidates import candidates_for_case
from apps.matching.models import Reservation
from apps.matching.multi import match_hospitals
from apps.matching.reservations import (
    ReservationNotHeld,
    ReservationUnavailable,
    release,
    release_expired,
    reserve,
)
from apps.resources.state_machine import TransitionNotAllowed

from .models import EmergencyRequest, RequestItem, RequestStatus, RequestStatusChange
from .serializers import (
    CandidateItemSerializer,
    CaseActionSerializer,
    CaseDetailSerializer,
    CaseInputSerializer,
    CaseSerializer,
    FeedEntrySerializer,
    FeedQuerySerializer,
    HospitalMatchSerializer,
    ReservationInputSerializer,
    ReservationSerializer,
)
from .services import ACTIVE, OutcomeNoteRequired, apply_case_action, create_case, escalate_overdue

# Story #36: what the network feed lists. Active cases, and escalated ones (still waiting for blood).
FEED_STATUSES = (*ACTIVE, RequestStatus.ESCALATED)
# ponytail: the first 100 by urgency, no paging. Ceiling: a network with more than 100 active requests of one
# type sees only the first 100; add paging when that happens.
FEED_LIMIT = 100


def case_queryset():
    return EmergencyRequest.objects.select_related("hospital", "created_by").prefetch_related("items")


def case_detail_queryset():
    """The list's queryset plus the timeline. Only the detail uses it, so the list stays light."""
    timeline = Prefetch("history", queryset=RequestStatusChange.objects.select_related("actor"))
    return case_queryset().prefetch_related(timeline)


class CaseListView(APIView):
    """GET /api/emergencies/ → the user's hospital's cases, most severe first, then oldest first (every case
    for staff without one). POST opens a case with its needs (stories #30, #32; emergencies: edit)."""

    permission_classes = [module_permission("emergencies")]

    def get(self, request):
        escalate_overdue()  # Story #35: reads sweep overdue cases first (see its ponytail note).
        cases = own_hospital(case_queryset(), request.user).by_priority()
        data = CaseSerializer(cases, many=True, context={"user": request.user}).data
        shown = sum(1 for case in data if case["patientRef"])
        if shown:
            record_view(request.user, "cases", hospital=request.user.hospital, count=shown)
        return Response(data)

    def post(self, request):
        serializer = CaseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        case = create_case(
            severity=data["severity"], patient_ref=data["patientRef"], items=data["items"], actor=request.user
        )
        created = CaseSerializer(case_queryset().get(pk=case.pk), context={"user": request.user}).data
        return Response(created, status=status.HTTP_201_CREATED)


class CaseDetailView(APIView):
    """GET /api/emergencies/<reference>/. Another hospital's case is 404, as if it didn't exist."""

    permission_classes = [module_permission("emergencies")]

    def get(self, request, reference):
        escalate_overdue()  # Story #35: the same request-time sweep as the list.
        release_expired()  # Story #43: expired holds go back to stock before the figures are worked out.
        case = get_object_or_404(own_hospital(case_detail_queryset(), request.user), reference=reference)
        data = CaseDetailSerializer(case, context={"user": request.user}).data
        if data["patientRef"]:
            record_view(request.user, f"case:{case.reference}", hospital=case.hospital, count=1)
        return Response(data)


class EmergencyFeedView(APIView):
    """GET /api/emergencies/feed/?type=blood|bed → the network's active requests, most urgent first (#36).
    Every hospital's, not only the user's: a blood bank elsewhere has to see them. Blood is the default. Each
    entry lists only the needs of that type. Emergencies: view, for every role that can see the module."""

    permission_classes = [module_permission("emergencies")]

    def get(self, request):
        escalate_overdue()  # Story #35: the same request-time sweep as the list.
        query = FeedQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        kind = query.validated_data["type"]
        needs = RequestItem.objects.filter(request=OuterRef("pk"), resource_type=kind)
        cases = (
            EmergencyRequest.objects.filter(status__in=FEED_STATUSES)
            .filter(Exists(needs))
            .select_related("hospital")
            .prefetch_related(Prefetch("items", queryset=RequestItem.objects.filter(resource_type=kind)))
            .by_priority()[:FEED_LIMIT]
        )
        return Response(FeedEntrySerializer(cases, many=True).data)


class CaseCandidatesView(APIView):
    """GET /api/emergencies/<reference>/candidates/ → the other hospitals that can supply each short
    requirement (story #38). Items with no shortfall are left out, so a case that is covered locally gets
    `items: []`. Each item's hospitals come ranked and scored, best first (story #41). `hospitals` ranks the
    hospitals across all the short needs at once (story #42). The same read rule as the detail: another
    hospital's case is 404. Doesn't escalate, so it stays a plain read."""

    permission_classes = [module_permission("emergencies")]

    def get(self, request, reference):
        release_expired()  # Story #43: a released hold is stock again, so it is offered to other cases.
        case = get_object_or_404(
            own_hospital(EmergencyRequest.objects.select_related("hospital"), request.user),
            reference=reference,
        )
        found = candidates_for_case(case)
        return Response(
            {
                "reference": case.reference,
                "items": CandidateItemSerializer(found, many=True).data,
                "hospitals": HospitalMatchSerializer(match_hospitals(found), many=True).data,
            }
        )


class CaseActionView(APIView):
    """POST /api/emergencies/<reference>/actions/ {"action": "startMatching", "note"?} → the updated case.
    A move the lifecycle refuses is 409 and changes nothing. Closing without an outcome note is 400 (story
    #35). Emergencies: edit, at the case's hospital."""

    permission_classes = [module_permission("emergencies")]

    def post(self, request, reference):
        serializer = CaseActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            case = apply_case_action(reference, data["action"], note=data["note"], actor=request.user)
        except OutcomeNoteRequired as exc:
            return Response({"note": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except TransitionNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        detail = case_detail_queryset().get(pk=case.pk)
        return Response(CaseDetailSerializer(detail, context={"user": request.user}).data)


class CaseReservationsView(APIView):
    """POST /api/emergencies/<reference>/reservations/ {"itemId", "quantity"} → 201 with the holds made (story
    #43). Stock comes from the case's own hospital, and whatever is free there is taken, up to the quantity.
    400 when nothing is free, or the quantity is more than the need has left. Emergencies: edit; another
    hospital's case is 404."""

    permission_classes = [module_permission("emergencies")]

    def post(self, request, reference):
        release_expired()  # Story #43: see CaseCandidatesView.
        case = get_object_or_404(
            own_hospital(EmergencyRequest.objects.select_related("hospital"), request.user),
            reference=reference,
        )
        serializer = ReservationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = case.items.filter(pk=data["itemId"]).first()
        if item is None:
            return Response(
                {"itemId": ["No need with that id on this case."]}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            holds = reserve(item, hospital=case.hospital, quantity=data["quantity"], actor=request.user)
        except ReservationUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        context = {"user": request.user}
        return Response(
            ReservationSerializer(holds, many=True, context=context).data, status=status.HTTP_201_CREATED
        )


class CaseReservationReleaseView(APIView):
    """POST /api/emergencies/<reference>/reservations/<id>/release/ → the released hold (story #43). A hold
    that is no longer held (allocated, released or expired) is 409 and changes nothing. Emergencies: edit."""

    permission_classes = [module_permission("emergencies")]

    def post(self, request, reference, pk):
        release_expired()  # Story #43: a hold that has just run out is already expired, so it answers 409.
        case = get_object_or_404(
            own_hospital(EmergencyRequest.objects.all(), request.user), reference=reference
        )
        hold = get_object_or_404(
            Reservation.objects.filter(request_item__request=case).select_related("hospital", "reserved_by"),
            pk=pk,
        )
        try:
            hold = release(hold, actor=request.user, reason="Released by staff")
        except ReservationNotHeld as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(ReservationSerializer(hold, context={"user": request.user}).data)
