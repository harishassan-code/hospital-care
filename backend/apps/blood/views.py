from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.resources.state_machine import TransitionNotAllowed

from . import services
from .models import AppointmentStatus, BloodUnit, Component, DonationAppointment, Donor, UnitStatus
from .serializers import (
    AppointmentSerializer,
    BloodUnitCreateSerializer,
    BloodUnitDetailSerializer,
    BloodUnitSerializer,
    DonorSerializer,
    RecordTestSerializer,
    ScreeningSerializer,
    UnitActionSerializer,
)

BloodAccess = module_permission("blood")


def own_hospital(queryset, user):
    """Users who work at a hospital see only its rows; admins without one see the whole network."""
    return queryset.filter(hospital_id=user.hospital_id) if user.hospital_id else queryset


def conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class BloodUnitListView(APIView):
    """GET /api/blood/units/ → the units in the user's hospital (every unit for users without one).
    Optional filters: ?status=available&group=O-&component=redCells (#18: searches use available).
    POST registers a new unit (story #17; blood: edit), optionally linked to a donor (story #20)."""

    permission_classes = [BloodAccess]

    def get(self, request):
        now = timezone.now()
        units = own_hospital(BloodUnit.objects.all(), request.user)
        wanted = request.query_params.get("status")
        if wanted in UnitStatus.values:
            units = units.filter(status=wanted)
            if wanted == UnitStatus.AVAILABLE:
                units = units.filter(expires_at__gt=now)  # never offer a unit that has just expired
        if request.query_params.get("group"):
            units = units.filter(group=request.query_params["group"])
        if request.query_params.get("component") in Component.values:
            units = units.filter(component=request.query_params["component"])
        return Response(BloodUnitSerializer(units, many=True, context={"now": now}).data)

    def post(self, request):
        serializer = BloodUnitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = services.register_unit(serializer, request.user)
        return Response(
            BloodUnitSerializer(unit, context={"now": timezone.now()}).data, status=status.HTTP_201_CREATED
        )


def unit_detail(donation_number):
    unit = (
        BloodUnit.objects.select_related("donor")
        .prefetch_related("tests")
        .get(donation_number=donation_number)
    )
    return BloodUnitDetailSerializer(unit, context={"now": timezone.now()}).data


class BloodUnitDetailView(APIView):
    """GET /api/blood/units/<id>/ → the unit with its donor and screening results."""

    permission_classes = [BloodAccess]

    def get(self, request, unit_id):
        get_object_or_404(own_hospital(BloodUnit.objects.all(), request.user), donation_number=unit_id)
        return Response(unit_detail(unit_id))


class BloodUnitTestView(APIView):
    """POST /api/blood/units/<id>/tests/ {test, passed, reason?} (story #18)."""

    permission_classes = [BloodAccess]

    def post(self, request, unit_id):
        get_object_or_404(BloodUnit, donation_number=unit_id)
        serializer = RecordTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.record_test(unit_id, actor=request.user, **serializer.validated_data)
        except TransitionNotAllowed as exc:
            return conflict(exc)
        return Response(unit_detail(unit_id), status=status.HTTP_201_CREATED)


class BloodUnitActionView(APIView):
    """POST /api/blood/units/<id>/actions/ {action, reason?}: reserve, cancelReservation, issue, expire,
    release (only when every test passed) or discard (reason required)."""

    permission_classes = [BloodAccess]

    def post(self, request, unit_id):
        get_object_or_404(BloodUnit, donation_number=unit_id)
        serializer = UnitActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.apply_unit_action(unit_id, actor=request.user, **serializer.validated_data)
        except TransitionNotAllowed as exc:
            return conflict(exc)
        return Response(unit_detail(unit_id))


class BloodStockView(APIView):
    """GET /api/blood/stock/?nearExpiryDays=3 (story #19). Marks overdue units expired first."""

    permission_classes = [BloodAccess]

    def get(self, request):
        try:
            days = int(request.query_params.get("nearExpiryDays", settings.BLOOD_NEAR_EXPIRY_DAYS))
        except ValueError:
            return Response({"nearExpiryDays": ["Must be a whole number of days."]}, status=400)
        if not 0 <= days <= 60:
            return Response({"nearExpiryDays": ["Must be between 0 and 60."]}, status=400)
        services.expire_overdue_units()
        units = own_hospital(BloodUnit.objects.all(), request.user)
        return Response(
            services.stock_summary(
                units, near_expiry_days=days, low_stock_units=settings.BLOOD_LOW_STOCK_UNITS
            )
        )


class DonorListView(APIView):
    """GET /api/blood/donors/?q=… (name, code or phone) · POST registers a donor (story #20)."""

    permission_classes = [BloodAccess]

    def get(self, request):
        donors = own_hospital(Donor.objects.all(), request.user)
        if q := request.query_params.get("q", "").strip():
            donors = donors.filter(Q(full_name__icontains=q) | Q(code__iexact=q) | Q(phone__icontains=q))
        if group := request.query_params.get("bloodGroup"):
            donors = donors.filter(blood_group=group)
        return Response(DonorSerializer(donors[:200], many=True).data)

    def post(self, request):
        serializer = DonorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donor = services.register_donor(serializer, request.user)
        return Response(DonorSerializer(donor).data, status=status.HTTP_201_CREATED)


class DonorDetailView(APIView):
    """GET /api/blood/donors/<id>/ → the donor, their eligibility and their units."""

    permission_classes = [BloodAccess]

    def get(self, request, donor_id):
        donor = get_object_or_404(own_hospital(Donor.objects.all(), request.user), code=donor_id)
        data = DonorSerializer(donor).data
        data["units"] = BloodUnitSerializer(
            donor.units.all(), many=True, context={"now": timezone.now()}
        ).data
        return Response(data)


class DonorScreeningView(APIView):
    """POST /api/blood/donors/<id>/screening/ {eligible, reason?, deferredUntil?} (story #21)."""

    permission_classes = [BloodAccess]

    def post(self, request, donor_id):
        donor = get_object_or_404(Donor, code=donor_id)
        serializer = ScreeningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        donor = services.screen_donor(
            donor, eligible=data["eligible"], reason=data["reason"], deferred_until=data["deferredUntil"],
            actor=request.user,
        )  # fmt: skip
        return Response(DonorSerializer(donor).data)


class AppointmentListView(APIView):
    """GET /api/blood/appointments/?from=YYYY-MM-DD (upcoming by default) · POST books one (story #22)."""

    permission_classes = [BloodAccess]

    def get(self, request):
        appointments = own_hospital(DonationAppointment.objects.select_related("donor"), request.user)
        if request.query_params.get("all") != "true":
            appointments = appointments.filter(status=AppointmentStatus.BOOKED, starts_at__gte=timezone.now())
        return Response(AppointmentSerializer(appointments, many=True).data)

    def post(self, request):
        serializer = AppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        appointment = services.book_appointment(data["donor"], data["starts_at"], actor=request.user)
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class AppointmentCancelView(APIView):
    """POST /api/blood/appointments/<id>/cancel/"""

    permission_classes = [BloodAccess]

    def post(self, request, appointment_id):
        appointment = get_object_or_404(DonationAppointment, pk=appointment_id)
        try:
            appointment = services.cancel_appointment(appointment, actor=request.user)
        except TransitionNotAllowed as exc:
            return conflict(exc)
        return Response(AppointmentSerializer(appointment).data)
