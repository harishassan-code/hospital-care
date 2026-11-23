"""The public network pages' data (B19): the city snapshot, the hospital directory and one hospital's page. No
sign-in, levels instead of stock, names only for signed-in staff, nothing about patients."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.ambulances.models import Ambulance, AmbulanceStatus
from apps.blood.services import RED_CELL_MINIMUM
from apps.emergencies.models import EmergencyStatus, ErStatus
from apps.emergencies.network import availability
from apps.hospitals.models import BedStatus, Capability, Department
from apps.matching.tests.reservation_support import bed, unit
from apps.specialists.models import OnCallWindow, Specialist

pytestmark = pytest.mark.django_db


def report(hospital, status=ErStatus.ACCEPTING, wait=20, waiting=5):
    return EmergencyStatus.objects.create(
        hospital=hospital, status=status, wait_minutes=wait, waiting_count=waiting
    )


def on_call(hospital, name, specialty, *, now=None):
    now = now or timezone.now()
    doctor = Specialist.objects.create(hospital=hospital, name=name, specialty=specialty)
    OnCallWindow.objects.create(
        specialist=doctor, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2)
    )
    return doctor


# ── Levels ──────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("free", "total", "level"),
    [
        (0, 0, None),  # no beds of that type
        (0, 10, "full"),
        (1, 10, "limited"),
        (2, 20, "limited"),  # 10%: below the 15% line
        (3, 20, "available"),  # 15%: on it
        (1, 3, "available"),  # small wards: one free bed of three is plenty
        (1, 1, "available"),
    ],
)
def test_availability_levels(free, total, level):
    assert availability(free, total) == level


# ── Network snapshot ────────────────────────────────────────────────────────────────────────────────────


def test_the_snapshot_needs_no_sign_in_and_counts_departments(api, make_hospital):
    general, seaview, northside, quiet = (
        make_hospital("General"),
        make_hospital("Seaview"),
        make_hospital("Northside"),
        make_hospital("Quiet"),
    )
    report(general, wait=45)
    report(seaview, ErStatus.BUSY, wait=80)
    report(northside, ErStatus.DIVERTING, wait=5)  # diverting: not offered as the shortest wait
    make_hospital("Closed", is_active=False)

    data = api.get(reverse("public-network")).json()

    assert data["hospitals"] == 4
    assert data["emergency"] == {
        "accepting": 1,
        "busy": 1,
        "diverting": 1,
        "notReported": 1,
        "shortestWait": {"hospitalId": general.pk, "name": "General", "waitMinutes": 45},
    }
    assert quiet.pk  # reported nothing, counted as not reported


def test_the_snapshot_gives_levels_not_counts(api, make_hospital):
    hospital = make_hospital()
    for _ in range(9):
        bed(hospital, "icu", status=BedStatus.OCCUPIED)
    bed(hospital, "icu")  # 1 of 10 free: limited
    bed(hospital, "general", status=BedStatus.OCCUPIED)  # 0 of 1: full
    bed(hospital, "nicu", status=BedStatus.OUT_OF_SERVICE)  # none in service: left out
    for _ in range(RED_CELL_MINIMUM["O-"]):
        unit(hospital, group="O-")  # at the minimum: ok
    unit(hospital, group="A+")  # 1 of 20: critical
    Ambulance.objects.create(hospital=hospital, identifier="AMB-1", type="basic")
    Ambulance.objects.create(
        hospital=hospital, identifier="AMB-2", type="advanced", status=AmbulanceStatus.DISPATCHED
    )
    Ambulance.objects.create(
        hospital=hospital, identifier="AMB-3", type="basic", status=AmbulanceStatus.OUT_OF_SERVICE
    )

    data = api.get(reverse("public-network")).json()

    assert data["beds"] == [{"bedType": "icu", "level": "limited"}, {"bedType": "general", "level": "full"}]
    levels = {row["group"]: row["level"] for row in data["blood"]}
    assert levels["O-"] == "ok" and levels["A+"] == "critical" and levels["B+"] == "critical"
    assert data["ambulances"] == {"available": 1, "total": 2}
    body = str(data)
    assert "AMB-1" not in body and "DN-" not in body  # no identifiers, only levels and counts


def test_an_empty_network_still_answers(api):
    data = api.get(reverse("public-network")).json()
    assert data["hospitals"] == 0 and data["beds"] == [] and data["blood"] == []
    assert data["emergency"]["shortestWait"] is None


def test_the_snapshot_costs_a_fixed_number_of_queries(api, make_hospital):
    def queries():
        with CaptureQueriesContext(connection) as ctx:
            api.get(reverse("public-network"))
        return len(ctx.captured_queries)

    one = make_hospital("One")
    report(one)
    bed(one, "icu")
    unit(one, group="B+")
    first = queries()
    for n in range(5):
        hospital = make_hospital(f"Extra {n}")
        report(hospital)
        bed(hospital, "icu")
        unit(hospital, group="B+")
    assert queries() == first


# ── Directory ───────────────────────────────────────────────────────────────────────────────────────────


def test_the_directory_lists_active_hospitals_with_their_status(api, make_hospital):
    trauma = Capability.objects.get_or_create(code="trauma", defaults={"name": "Trauma centre"})[0]
    general = make_hospital("General", phone="+92 21 111 000 111")
    general.capabilities.add(trauma)
    report(general, ErStatus.BUSY, wait=70, waiting=14)
    make_hospital("Bay")  # no status yet
    make_hospital("Closed", is_active=False)

    rows = api.get(reverse("public-hospitals")).json()

    assert [row["name"] for row in rows] == ["Bay", "General"]
    bay, row = rows
    assert bay["emergency"] is None
    assert row["services"] == ["Trauma centre"]
    assert row["emergency"]["status"] == "busy" and row["emergency"]["waitMinutes"] == 70
    assert row["latitude"] == pytest.approx(24.8607) and row["phone"] == "+92 21 111 000 111"


# ── One hospital ────────────────────────────────────────────────────────────────────────────────────────


def test_a_hospital_page_shows_departments_beds_and_who_is_on_duty(api, make_hospital):
    hospital = make_hospital("Seaview")
    Department.objects.create(hospital=hospital, name="Cardiology")
    report(hospital)
    bed(hospital, "icu")
    on_call(hospital, "Dr. Ayesha Khan", "Cardiology")
    on_call(hospital, "Dr. Omar Sheikh", "Cardiology")
    later = Specialist.objects.create(hospital=hospital, name="Dr. Later", specialty="Neurology")
    now = timezone.now()
    OnCallWindow.objects.create(
        specialist=later, starts_at=now + timedelta(hours=3), ends_at=now + timedelta(hours=5)
    )
    on_call(make_hospital("Elsewhere"), "Dr. Elsewhere", "Paediatrics")

    data = api.get(reverse("public-hospital", args=[hospital.pk])).json()

    assert data["name"] == "Seaview" and data["departments"] == ["Cardiology"]
    assert data["beds"] == [{"bedType": "icu", "level": "available"}]
    assert data["onDuty"] == [{"specialty": "Cardiology", "count": 2, "names": None}]
    assert data["namesShown"] is False
    assert "Ayesha" not in str(data)


@pytest.mark.parametrize("role", [Role.NURSE, Role.DOCTOR, Role.ADMIN])
def test_signed_in_hospital_staff_see_doctors_names(client_as, make_hospital, role):
    hospital = make_hospital("Seaview")
    on_call(hospital, "Dr. Ayesha Khan", "Cardiology")
    data = client_as(role).get(reverse("public-hospital", args=[hospital.pk])).json()
    assert data["namesShown"] is True
    assert data["onDuty"][0]["names"] == ["Dr. Ayesha Khan"]


def test_a_signed_in_patient_sees_no_names(client_as, make_hospital):
    hospital = make_hospital("Seaview")
    on_call(hospital, "Dr. Ayesha Khan", "Cardiology")
    data = client_as(Role.PATIENT).get(reverse("public-hospital", args=[hospital.pk])).json()
    assert data["namesShown"] is False and data["onDuty"][0]["names"] is None


def test_unknown_and_inactive_hospitals_are_not_found(api, make_hospital):
    closed = make_hospital("Closed", is_active=False)
    assert api.get(reverse("public-hospital", args=[closed.pk])).status_code == 404
    assert api.get(reverse("public-hospital", args=[999_999])).status_code == 404


def test_no_public_response_carries_patient_details(api, make_hospital):
    hospital = make_hospital()
    report(hospital)
    occupied = bed(hospital, "icu", status=BedStatus.OCCUPIED)
    occupied.patient_initials, occupied.patient_age, occupied.patient_sex = "Q.Z.", 47, "F"
    occupied.save()
    for name, args in (("public-network", []), ("public-hospitals", []), ("public-hospital", [hospital.pk])):
        body = api.get(reverse(name, args=args)).content.decode()
        assert "Q.Z." not in body and "patient" not in body.lower(), name
