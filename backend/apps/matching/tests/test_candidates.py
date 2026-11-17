"""Story #38: candidate hospitals for a case's shortfall, for blood, beds, equipment and operating rooms."""

import itertools
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.equipment.models import Equipment, EquipmentStatus
from apps.hospitals.models import Bed, BedStatus, Hospital, Ward
from apps.matching.candidates import _km_between, candidates_for_case, find_candidates
from apps.matching.distance import estimated_travel_minutes
from apps.operating_rooms.models import OperatingRoom, OrStatus

pytestmark = pytest.mark.django_db

_numbers = itertools.count(1)
KARACHI = ("24.860700", "67.001100")  # the default test hospital's coordinates


def unit(hospital, group="A+", component="redCells", status=UnitStatus.AVAILABLE, expires_in=30):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=f"D{next(_numbers)}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in),
        status=status,
        location="Blood fridge 1",
    )


def bed(hospital, bed_type="icu", status=BedStatus.FREE):
    ward, _ = Ward.objects.get_or_create(
        code=f"ward-{hospital.pk}", defaults={"name": "Ward", "kind": "General", "hospital": hospital}
    )
    return Bed.objects.create(ward=ward, label=f"B{next(_numbers)}", bed_type=bed_type, status=status)


def equipment(hospital, equipment_type="ventilator", status=EquipmentStatus.AVAILABLE):
    return Equipment.objects.create(
        hospital=hospital,
        identifier=f"EQ-{next(_numbers)}",
        equipment_type=equipment_type,
        location="ICU",
        status=status,
    )


def room(hospital, capabilities=("cardiac",), status=OrStatus.AVAILABLE):
    return OperatingRoom.objects.create(
        hospital=hospital,
        name=f"Theatre {next(_numbers)}",
        capabilities=list(capabilities),
        location="Block B",
        status=status,
    )


def hospital(name, lat=KARACHI[0], lng=KARACHI[1], **extra):
    return Hospital.objects.create(name=name, address="Karachi", latitude=lat, longitude=lng, **extra)


def case_at(origin, *needs, reference="EC-2026-0001"):
    """Each need is a dict of RequestItem fields with a quantity. Returns the case, fetched with its
    hospital."""
    case = EmergencyRequest.objects.create(reference=reference, severity="high", hospital=origin)
    for need in needs:
        RequestItem.objects.create(request=case, **need)
    return EmergencyRequest.objects.select_related("hospital").get(pk=case.pk)


def blood_need(group="A+", component="redCells", quantity=5):
    return {"resource_type": "blood", "blood_group": group, "component": component, "quantity": quantity}


def bed_need(bed_type="icu", quantity=5):
    return {"resource_type": "bed", "bed_type": bed_type, "quantity": quantity}


def equipment_need(equipment_type="ventilator", quantity=5):
    return {"resource_type": "equipment", "equipment_type": equipment_type, "quantity": quantity}


def room_need(capability="cardiac", quantity=5):
    return {"resource_type": "operatingRoom", "capability": capability, "quantity": quantity}


def counts(candidates):
    """{hospital name: available}, for the candidates in their order."""
    return {c.hospital.name: c.available for c in candidates}


def search(origin, need, needed=1):
    """find_candidates for one need of a new case at `origin`."""
    case = case_at(origin, need, reference=f"EC-2026-{next(_numbers):04d}")
    [item] = case.items.all()
    return find_candidates(item, origin_hospital=origin, needed=needed)


# ── Per type: the right resources are counted ──────────────────────────────────────────────────


def test_blood_counts_compatible_usable_units_only(make_hospital):
    origin = make_hospital(name="Origin")
    b1, b2, b3 = hospital("B1"), hospital("B2"), hospital("B3")
    unit(origin, "A+")  # the origin's own stock is left out
    unit(b1, "A+")
    unit(b1, "A+")
    unit(b1, "A-")  # compatible, rank 1
    unit(b2, "O+")  # compatible, rank 2
    unit(b2, "O-", expires_in=-1)  # compatible but expired
    unit(b2, "B+")  # not compatible with an A+ recipient
    unit(b3, "A+", status=UnitStatus.QUARANTINED)  # not released
    unit(b3, "A+", component="plasma")  # another component

    assert counts(search(origin, blood_need("A+", "redCells"))) == {"B1": 3, "B2": 1}


def test_beds_count_free_beds_of_the_type(make_hospital):
    origin, b1, b2 = make_hospital(name="Origin"), hospital("B1"), hospital("B2")
    bed(b1, "icu")
    bed(b1, "icu")
    bed(b1, "icu", status=BedStatus.OCCUPIED)
    bed(b1, "general")
    bed(b2, "icu")

    assert counts(search(origin, bed_need("icu"))) == {"B1": 2, "B2": 1}


def test_equipment_counts_available_equipment_of_the_type(make_hospital):
    origin, b1, b2 = make_hospital(name="Origin"), hospital("B1"), hospital("B2")
    equipment(b1, "ventilator")
    equipment(b1, "ventilator")
    equipment(b1, "ventilator", status=EquipmentStatus.IN_USE)
    equipment(b1, "ventilator", status=EquipmentStatus.MAINTENANCE)
    equipment(b1, "monitor")
    equipment(b2, "ventilator")

    assert counts(search(origin, equipment_need("ventilator"))) == {"B1": 2, "B2": 1}


def test_operating_rooms_count_available_rooms_with_the_capability(make_hospital):
    origin, b1, b2 = make_hospital(name="Origin"), hospital("B1"), hospital("B2")
    room(b1, ["cardiac", "general"])
    room(b1, ["cardiac"], status=OrStatus.CLEANING)
    room(b1, ["general"])
    room(b2, ["cardiac"])
    room(b2, ["cardiac"])

    assert counts(search(origin, room_need("cardiac"))) == {"B1": 1, "B2": 2}


# ── Who is left out ────────────────────────────────────────────────────────────────────────────


def test_the_origin_inactive_and_empty_hospitals_are_left_out(make_hospital):
    origin = make_hospital(name="Origin")
    active, retired = hospital("Active"), hospital("Retired", is_active=False)
    hospital("Empty")  # no beds at all
    for h in (origin, active, retired):
        bed(h, "icu")

    assert counts(search(origin, bed_need("icu"))) == {"Active": 1}


# ── Covers, and the order ──────────────────────────────────────────────────────────────────────


def test_covers_means_available_is_at_least_the_shortfall(make_hospital):
    origin, b1 = make_hospital(name="Origin"), hospital("B1")
    for _ in range(3):
        bed(b1, "icu")

    [exact] = search(origin, bed_need("icu"), needed=3)
    [short] = search(origin, bed_need("icu"), needed=4)

    assert (exact.covers, short.covers) == (True, False)


def test_order_is_covering_first_then_nearest_then_id():
    origin = hospital("Origin", "24.860000", "67.000000")
    near_cover = hospital("Near covers", "24.861000", "67.000000")
    twin_a = hospital("Twin A", "24.870000", "67.000000")  # same spot as twin B: a distance tie
    twin_b = hospital("Twin B", "24.870000", "67.000000")
    far_cover = hospital("Far covers", "24.950000", "67.000000")
    near_partial = hospital("Near partial", "24.860100", "67.000000")
    for h, n in ((near_cover, 3), (twin_a, 3), (twin_b, 3), (far_cover, 3), (near_partial, 1)):
        for _ in range(n):
            bed(h, "icu")

    found = search(origin, bed_need("icu"), needed=3)

    assert [c.hospital.name for c in found] == [
        "Near covers",
        "Twin A",
        "Twin B",
        "Far covers",
        "Near partial",
    ]
    assert [c.covers for c in found] == [True, True, True, True, False]


# ── Distance and travel ────────────────────────────────────────────────────────────────────────


def test_distance_and_travel_time_come_from_the_distance_module():
    origin = hospital("Origin", "24.860000", "67.000000")
    there = hospital("There", "24.960000", "67.000000")  # 0.1 degrees north: about 11.1 km
    bed(there, "icu")

    [candidate] = search(origin, bed_need("icu"))

    assert candidate.distance_km == pytest.approx(11.12, abs=0.05)
    assert candidate.travel_minutes == round(estimated_travel_minutes(candidate.distance_km))


def test_distance_is_none_without_an_origin_hospital(make_hospital):
    there = hospital("There")
    bed(there, "icu")
    case = EmergencyRequest.objects.create(reference="EC-2026-0009", severity="high", hospital=None)
    RequestItem.objects.create(request=case, **bed_need("icu", quantity=1))
    [item] = case.items.all()

    [candidate] = find_candidates(item, origin_hospital=None, needed=1)

    assert (candidate.distance_km, candidate.travel_minutes) == (None, None)


def test_distance_is_none_when_either_hospital_has_no_coordinates():
    """The model requires coordinates, so this is checked on unsaved instances."""
    with_coordinates = Hospital(name="A", address="x", latitude="24.8", longitude="67.0")
    without = Hospital(name="B", address="x", latitude=None, longitude=None)

    assert _km_between(None, with_coordinates) is None
    assert _km_between(without, with_coordinates) is None
    assert _km_between(with_coordinates, without) is None
    assert _km_between(with_coordinates, with_coordinates) == pytest.approx(0.0)


# ── Blood: earliest expiry and best donor rank ─────────────────────────────────────────────────


def test_blood_candidates_carry_the_earliest_expiry_and_the_best_donor_rank(make_hospital):
    origin = make_hospital(name="Origin")
    x, y = hospital("X"), hospital("Y")
    soonest_x = unit(x, "O+", expires_in=10)  # compatible for A+ (rank 2), not the identical group
    unit(x, "O+", expires_in=20)
    unit(y, "A+", expires_in=5)  # identical group, rank 0
    compatible_y = unit(y, "A-", expires_in=2)  # rank 1, and the soonest at Y

    by_name = {c.hospital.name: c for c in search(origin, blood_need("A+", "redCells"))}

    assert by_name["Y"].best_donor_rank == 0
    assert by_name["Y"].earliest_expiry == compatible_y.expires_at
    assert by_name["X"].best_donor_rank == 2
    assert by_name["X"].earliest_expiry == soonest_x.expires_at


def test_non_blood_candidates_have_no_expiry_or_donor_rank(make_hospital):
    origin, b1 = make_hospital(name="Origin"), hospital("B1")
    bed(b1, "icu")

    [candidate] = search(origin, bed_need("icu"))

    assert (candidate.earliest_expiry, candidate.best_donor_rank) == (None, None)


# ── Query budget: flat as the network grows ────────────────────────────────────────────────────


def four_needs():
    return [
        blood_need("A+", "redCells", 50),
        bed_need("icu", 50),
        equipment_need("ventilator", 50),
        room_need("cardiac", 50),
    ]


def stock_every_hospital(hospital_obj):
    unit(hospital_obj, "A+")
    unit(hospital_obj, "O+")
    bed(hospital_obj, "icu")
    equipment(hospital_obj, "ventilator")
    room(hospital_obj, ["cardiac"])


def run_counting(case):
    with CaptureQueriesContext(connection) as context:
        candidates_for_case(case)
    return len(context.captured_queries)


def test_the_query_count_is_flat_as_hospitals_and_resources_grow(
    make_hospital, django_assert_max_num_queries
):
    origin = make_hospital(name="Origin")
    for i in range(2):
        stock_every_hospital(hospital(f"Small {i}"))
    small = run_counting(case_at(origin, *four_needs(), reference="EC-2026-0001"))

    for i in range(12):
        stock_every_hospital(hospital(f"Big {i}"))
        bed(hospital(f"Big bed {i}"), "icu")
    case = case_at(origin, *four_needs(), reference="EC-2026-0002")
    with django_assert_max_num_queries(
        10
    ):  # items, four stock counts, four grouped searches, one hospital fetch
        big = run_counting(case)

    assert big == small
