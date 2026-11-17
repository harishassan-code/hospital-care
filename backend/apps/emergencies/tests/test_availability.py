"""Story #33: what a case's own hospital has for each requirement, and the shortfall carried to matching."""

import itertools
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.availability import local_availability, shortfall_items
from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.equipment.models import Equipment, EquipmentStatus
from apps.hospitals.models import Bed, BedStatus, Ward
from apps.operating_rooms.models import OperatingRoom, OrStatus

pytestmark = pytest.mark.django_db

_numbers = itertools.count(1)


def make_unit(hospital, group="O-", component="redCells", status=UnitStatus.AVAILABLE, expires_in=30):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=f"U{next(_numbers)}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in),
        status=status,
        location="Blood fridge 1",
    )


def make_bed(hospital, bed_type="icu", status=BedStatus.FREE):
    ward, _ = Ward.objects.get_or_create(
        code=f"ward-{hospital.pk}", defaults={"name": "Ward", "kind": "General", "hospital": hospital}
    )
    return Bed.objects.create(ward=ward, label=f"B{next(_numbers)}", bed_type=bed_type, status=status)


def make_equipment(hospital, equipment_type="ventilator", status=EquipmentStatus.AVAILABLE):
    return Equipment.objects.create(
        hospital=hospital,
        identifier=f"EQ-{next(_numbers)}",
        equipment_type=equipment_type,
        location="ICU",
        status=status,
    )


def make_room(hospital, capabilities=("cardiac",), status=OrStatus.AVAILABLE):
    return OperatingRoom.objects.create(
        hospital=hospital,
        name=f"Theatre {next(_numbers)}",
        capabilities=list(capabilities),
        location="Block B",
        status=status,
    )


def make_case(hospital, *needs, reference="EC-2026-0001"):
    """Each need is (kind, quantity, fulfilled). Kind is "O-/redCells" for blood, "equipment:ventilator" for
    equipment, "room:cardiac" for an operating room, or a bed type like "icu"."""
    case = EmergencyRequest.objects.create(reference=reference, severity="high", hospital=hospital)
    for kind, quantity, fulfilled in needs:
        if "/" in kind:
            group, component = kind.split("/")
            fields = {"resource_type": "blood", "blood_group": group, "component": component}
        elif kind.startswith("equipment:"):
            fields = {"resource_type": "equipment", "equipment_type": kind.removeprefix("equipment:")}
        elif kind.startswith("room:"):
            fields = {"resource_type": "operatingRoom", "capability": kind.removeprefix("room:")}
        else:
            fields = {"resource_type": "bed", "bed_type": kind}
        RequestItem.objects.create(request=case, quantity=quantity, fulfilled=fulfilled, **fields)
    return case


def figures(case):
    """(need, available, shortfall) for each requirement, in order."""
    return [
        (
            row.item.blood_group or row.item.bed_type or row.item.equipment_type or row.item.capability,
            row.available,
            row.shortfall,
        )
        for row in local_availability(case)
    ]


# ── Blood: exact group, component, hospital, usable ────────────────────────────────────────────


def test_blood_counts_only_usable_units_of_the_exact_group_and_component_at_this_hospital(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    make_unit(here, "O-", "redCells")
    make_unit(here, "O-", "redCells")  # the two that count
    make_unit(here, "O-", "redCells", expires_in=-1)  # available but past its expiry
    for status in (UnitStatus.QUARANTINED, UnitStatus.RESERVED, UnitStatus.ISSUED, UnitStatus.DISCARDED):
        make_unit(here, "O-", "redCells", status=status)
    make_unit(here, "O-", "redCells", status=UnitStatus.EXPIRED)
    make_unit(here, "O-", "plasma")  # other component
    make_unit(here, "O+", "redCells")  # other group
    make_unit(there, "O-", "redCells")  # other hospital
    make_unit(None, "O-", "redCells")  # no hospital
    case = make_case(here, ("O-/redCells", 5, 0))

    assert figures(case) == [("O-", 2, 3)]


def test_exact_match_only_so_compatible_groups_do_not_count(make_hospital):
    """O- could serve A+ under the compatibility rules, but that is story #37, not this check."""
    here = make_hospital()
    make_unit(here, "O-", "redCells")
    case = make_case(here, ("A+/redCells", 1, 0))

    assert figures(case) == [("A+", 0, 1)]


# ── Beds: free, of the type, at this hospital ──────────────────────────────────────────────────


def test_beds_count_only_free_beds_of_the_type_at_this_hospital(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    make_bed(here, "icu")
    make_bed(here, "icu")
    for status in (BedStatus.OCCUPIED, BedStatus.RESERVED, BedStatus.CLEANING, BedStatus.OUT_OF_SERVICE):
        make_bed(here, "icu", status=status)
    make_bed(here, "general")  # free, but another type: not an icu
    make_bed(there, "icu")  # other hospital
    case = make_case(here, ("icu", 3, 0), ("general", 1, 0))

    assert figures(case) == [("icu", 2, 1), ("general", 1, 0)]


# ── Equipment and operating rooms (#32, completed in #38) ──────────────────────────────────────


def test_equipment_counts_only_available_equipment_of_the_type_at_this_hospital(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    make_equipment(here, "ventilator")
    make_equipment(here, "ventilator")
    for status in (EquipmentStatus.IN_USE, EquipmentStatus.MAINTENANCE, EquipmentStatus.OUT_OF_SERVICE):
        make_equipment(here, "ventilator", status=status)
    make_equipment(here, "monitor")  # available, but another type
    make_equipment(there, "ventilator")  # other hospital
    case = make_case(here, ("equipment:ventilator", 3, 0), ("equipment:monitor", 1, 0))

    assert figures(case) == [("ventilator", 2, 1), ("monitor", 1, 0)]


def test_operating_rooms_count_available_rooms_with_the_capability_at_this_hospital(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    make_room(here, ["cardiac", "general"])
    make_room(here, ["cardiac"])
    for status in (OrStatus.IN_USE, OrStatus.CLEANING, OrStatus.MAINTENANCE, OrStatus.OUT_OF_SERVICE):
        make_room(here, ["cardiac"], status=status)
    make_room(here, ["neuro"])  # available, but without the capability
    make_room(there, ["cardiac"])  # other hospital
    case = make_case(here, ("room:cardiac", 3, 0), ("room:general", 1, 0))

    assert figures(case) == [("cardiac", 2, 1), ("general", 0, 1)]


def test_a_room_with_two_capabilities_covers_one_line_not_both(make_hospital):
    """One cardiac room that is also general: the cardiac line takes it, so the general line is short."""
    here = make_hospital()
    make_room(here, ["cardiac", "general"])
    case = make_case(here, ("room:cardiac", 1, 0), ("room:general", 1, 0))

    assert figures(case) == [("cardiac", 1, 0), ("general", 0, 1)]


def test_equipment_and_rooms_shortfall_subtracts_fulfilled(make_hospital):
    here = make_hospital()
    make_equipment(here, "dialysis")
    make_room(here, ["trauma"])
    case = make_case(here, ("equipment:dialysis", 2, 0), ("room:trauma", 3, 1))

    assert [row.shortfall for row in local_availability(case)] == [1, 1]
    assert [item.equipment_type or item.capability for item, _ in shortfall_items(case)] == [
        "dialysis",
        "trauma",
    ]


# ── Shortfall ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("quantity", "fulfilled", "available", "shortfall"),
    [
        (4, 0, 2, 2),  # nothing fulfilled
        (4, 1, 2, 1),  # fulfilled counts against the need
        (2, 2, 0, 0),  # fulfilled in full
        (1, 0, 5, 0),  # more here than needed: never negative
        (3, 3, 1, 0),
    ],
)
def test_shortfall_is_quantity_less_fulfilled_less_available_and_never_negative(
    make_hospital, quantity, fulfilled, available, shortfall
):
    here = make_hospital()
    for _ in range(available):
        make_bed(here, "icu")
    case = make_case(here, ("icu", quantity, fulfilled))

    assert [row.shortfall for row in local_availability(case)] == [shortfall]


def test_needs_that_draw_on_the_same_stock_share_it_in_list_order(make_hospital):
    """Two ICU lines of 3 with 4 free beds: the first is covered, the second has 1 bed left and is 2 short."""
    here = make_hospital()
    for _ in range(4):
        make_bed(here, "icu")
    case = make_case(here, ("icu", 3, 0), ("icu", 3, 0))

    assert figures(case) == [("icu", 4, 0), ("icu", 1, 2)]
    assert [short for _, short in shortfall_items(case)] == [2]


def test_shortfall_items_returns_only_the_short_items_with_their_shortfall(make_hospital):
    here = make_hospital()
    make_unit(here, "O-", "redCells")
    make_bed(here, "icu")
    make_bed(here, "icu")
    case = make_case(
        here,
        ("O-/redCells", 3, 0),  # short by 2
        ("icu", 2, 0),  # covered
        ("general", 1, 0),  # short by 1
        ("icu", 5, 1),  # the covered icu line used both beds, so none are left: 5 - 1 - 0 = 4
    )

    pairs = shortfall_items(case)

    assert [(item.blood_group or item.bed_type, short) for item, short in pairs] == [
        ("O-", 2),
        ("general", 1),
        ("icu", 4),
    ]


def test_a_case_without_a_hospital_has_nothing_available(make_hospital):
    hospital = make_hospital()
    make_unit(hospital, "O-", "redCells")
    make_bed(hospital, "icu")
    case = make_case(None, ("O-/redCells", 2, 0), ("icu", 1, 0))

    assert figures(case) == [("O-", 0, 2), ("icu", 0, 1)]
    assert [short for _, short in shortfall_items(case)] == [2, 1]


# ── API ────────────────────────────────────────────────────────────────────────────────────────


def test_the_detail_exposes_local_figures_per_need_and_the_list_does_not(client_as, make_hospital):
    here = make_hospital()
    make_unit(here, "O-", "redCells")
    make_bed(here, "icu")
    make_case(here, ("O-/redCells", 3, 0), ("icu", 1, 0))
    doctor = client_as(Role.DOCTOR, hospital=here)

    detail = doctor.get(reverse("emergency-case", args=["EC-2026-0001"])).json()
    assert detail["items"][0] == {
        "type": "blood",
        "group": "O-",
        "component": "redCells",
        "quantity": 3,
        "fulfilled": 0,
        "remaining": 3,
        "localAvailable": 1,
        "shortfall": 2,
        "reserved": 0,
        "itemId": RequestItem.objects.order_by("id").first().pk,
    }
    assert [(i["localAvailable"], i["shortfall"]) for i in detail["items"]] == [(1, 2), (1, 0)]
    assert [i["itemId"] for i in detail["items"]] == list(
        RequestItem.objects.order_by("id").values_list("pk", flat=True)
    )
    assert detail["shortfallTotal"] == 2

    listed = doctor.get(reverse("emergency-cases")).json()[0]
    assert "shortfallTotal" not in listed
    assert all("localAvailable" not in item and "shortfall" not in item for item in listed["items"])


def count_queries(client, url):
    with CaptureQueriesContext(connection) as context:
        assert client.get(url).status_code == 200
    return len(context.captured_queries)


def test_the_detail_query_count_is_bounded_and_does_not_grow_with_the_needs(
    client_as, make_hospital, django_assert_max_num_queries
):
    here = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=here)
    make_case(here, ("O-/redCells", 1, 0), reference="EC-2026-0001")
    needs = [
        ("O-/redCells", 1, 0),
        ("A+/plasma", 1, 0),
        ("AB-/platelets", 2, 0),
        ("icu", 1, 0),
        ("general", 1, 0),
    ]
    make_case(here, *needs, reference="EC-2026-0002")
    for _ in range(3):
        make_unit(here, "O-", "redCells")
        make_bed(here, "icu")

    small = count_queries(doctor, reverse("emergency-case", args=["EC-2026-0001"]))
    url = reverse("emergency-case", args=["EC-2026-0002"])
    # The overdue check (one query, story #35), the expiry check for holds (one query, story #43), the case,
    # its needs, its history, the needs again with their holds for availability (one query, story #43), the
    # holds on the case (one query), the allocations on the case (one query, story #45), and one query per
    # resource type (blood, beds, equipment, operating rooms), whatever the needs.
    with django_assert_max_num_queries(12):
        big = count_queries(doctor, url)

    assert big == small
