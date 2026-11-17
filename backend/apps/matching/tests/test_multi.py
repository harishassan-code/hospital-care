"""Story #42: multi-resource matching. Which single hospital can supply the most of a case's short needs,
and what each partial one is missing. Runs the real candidate search on the database, then judges them.
"""

import itertools
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.equipment.models import Equipment, EquipmentStatus
from apps.hospitals.models import Bed, BedStatus, Ward
from apps.matching.candidates import candidates_for_case
from apps.matching.multi import match_hospitals
from apps.matching.scoring import parse_scoring_config
from apps.operating_rooms.models import OperatingRoom, OrStatus

pytestmark = pytest.mark.django_db

_numbers = itertools.count(1)
FORTY_KM_NORTH = ("25.220700", "67.001100")  # about 40 km from the default test coordinates


@pytest.fixture(autouse=True)
def default_scoring():
    with override_settings(MATCHING_SCORING=parse_scoring_config(""), MATCHING_MAX_DISTANCE_KM=50):
        yield


def unit(hospital, group="O-", component="redCells", expires_in=30):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=f"M{next(_numbers)}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in),
        status=UnitStatus.AVAILABLE,
        location="Blood fridge 1",
    )


def bed(hospital, bed_type="icu"):
    ward, _ = Ward.objects.get_or_create(
        code=f"ward-{hospital.pk}", defaults={"name": "Ward", "kind": "General", "hospital": hospital}
    )
    return Bed.objects.create(ward=ward, label=f"B{next(_numbers)}", bed_type=bed_type, status=BedStatus.FREE)


def ventilator(hospital):
    return Equipment.objects.create(
        hospital=hospital,
        identifier=f"VENT-{next(_numbers)}",
        equipment_type="ventilator",
        location="ICU",
        status=EquipmentStatus.AVAILABLE,
    )


def theatre(hospital, capabilities):
    return OperatingRoom.objects.create(
        hospital=hospital,
        name=f"Theatre {next(_numbers)}",
        capabilities=list(capabilities),
        location="Block B",
        status=OrStatus.AVAILABLE,
    )


def blood_need(quantity, group="O-"):
    return {"resource_type": "blood", "blood_group": group, "component": "redCells", "quantity": quantity}


def bed_need(quantity=1):
    return {"resource_type": "bed", "bed_type": "icu", "quantity": quantity}


def vent_need(quantity=1):
    return {"resource_type": "equipment", "equipment_type": "ventilator", "quantity": quantity}


def room_need(capability, quantity=1):
    return {"resource_type": "operatingRoom", "capability": capability, "quantity": quantity}


def judge(origin, *needs):
    """A new case at `origin` with these needs, and the hospitals that match it, best first."""
    case = EmergencyRequest.objects.create(
        reference=f"EC-2026-{next(_numbers):04d}", severity="critical", hospital=origin
    )
    for need in needs:
        RequestItem.objects.create(request=case, **need)
    case = EmergencyRequest.objects.select_related("hospital").get(pk=case.pk)
    return case, match_hospitals(candidates_for_case(case))


def by_name(matches):
    return {m.hospital.name: m for m in matches}


def test_a_hospital_with_every_need_ranks_above_a_better_scoring_one_missing_a_need(make_hospital):
    origin = make_hospital(name="Origin")
    full = make_hospital(name="Full", latitude=FORTY_KM_NORTH[0], longitude=FORTY_KM_NORTH[1])
    near = make_hospital(name="Near")  # the origin's own spot: the nearest scores highest
    bed(full)
    ventilator(full)
    unit(full)
    unit(full)
    ventilator(near)
    _, found = judge(origin, bed_need(), vent_need(), blood_need(2))

    assert [m.hospital.name for m in found] == ["Full", "Near"]
    assert [m.rank for m in found] == [1, 2]
    assert found[0].complete and not found[1].complete
    assert found[1].score > found[0].score, "the point of the test: the partial one scores higher"


def test_among_partial_matches_the_one_that_covers_more_ranks_higher(make_hospital):
    origin = make_hospital(name="Origin")
    close = make_hospital(name="Close")  # the origin's own spot, one need only
    far = make_hospital(name="Far", latitude=FORTY_KM_NORTH[0], longitude=FORTY_KM_NORTH[1])
    ventilator(close)
    bed(far)
    ventilator(far)
    _, found = judge(origin, bed_need(), vent_need(), blood_need(2))

    assert [m.hospital.name for m in found] == ["Far", "Close"]
    assert found[1].score > found[0].score, "coverage, not the score, decides the order here"
    assert [len(m.covered) for m in found] == [2, 1]


def test_unmet_lists_exactly_the_missing_needs_with_their_missing_counts(make_hospital):
    origin, stock = make_hospital(name="Origin"), make_hospital(name="Stock")
    other = make_hospital(name="Other")  # gives the blood line candidates, so it is judged too
    bed(stock)
    ventilator(stock)  # one of two
    for _ in range(5):
        unit(other)
    _, found = judge(origin, bed_need(), vent_need(2), blood_need(3))

    stock_match = by_name(found)["Stock"]
    assert [(m.item.resource_type, m.missing, m.available) for m in stock_match.unmet] == [
        ("equipment", 1, 1),
        ("blood", 3, 0),
    ]
    assert [m.item.resource_type for m in stock_match.covered] == ["bed"]
    assert not stock_match.complete


def test_a_partial_quantity_is_unmet_with_how_many_the_hospital_has(make_hospital):
    origin, stock = make_hospital(name="Origin"), make_hospital(name="Stock")
    ventilator(stock)  # one of three
    _, found = judge(origin, vent_need(3))

    [match] = found
    assert match.partial == match.unmet
    assert [(m.missing, m.available) for m in match.partial] == [(2, 1)]


def test_two_lines_on_the_same_stock_are_not_both_covered_by_one_stock(make_hospital):
    origin, stock = make_hospital(name="Origin"), make_hospital(name="Stock")
    for _ in range(3):
        unit(stock)  # three O- units: enough for the first line, not for both
    case, [match] = judge(origin, blood_need(2), blood_need(2))
    first, second = case.items.order_by("id")

    assert not match.complete
    assert [m.item.pk for m in match.covered] == [first.pk], "the first line is covered first"
    assert [(m.item.pk, m.missing, m.available) for m in match.unmet] == [(second.pk, 1, 1)]


def test_two_lines_on_the_same_stock_are_both_covered_when_the_stock_is_enough(make_hospital):
    origin, stock = make_hospital(name="Origin"), make_hospital(name="Stock")
    for _ in range(4):
        unit(stock)
    _, [match] = judge(origin, blood_need(2), blood_need(2))

    assert match.complete and len(match.covered) == 2 and match.unmet == ()


def test_operating_rooms_with_different_capabilities_are_judged_on_their_own_rooms(make_hospital):
    origin, stock = make_hospital(name="Origin"), make_hospital(name="Stock")
    theatre(stock, ["cardiac"])
    theatre(stock, ["general"])
    _, [match] = judge(origin, room_need("cardiac"), room_need("general"))

    assert match.complete


def test_a_hospital_is_scored_only_on_the_needs_it_has_candidates_for(make_hospital):
    origin, stock = make_hospital(name="Origin"), make_hospital(name="Stock")
    bed(stock)  # at the origin's own spot: a nearest-first score of 100
    other = make_hospital(name="Other")
    unit(other)  # the blood need has candidates elsewhere, not at Stock
    _, found = judge(origin, bed_need(), blood_need(2))

    assert by_name(found)["Stock"].score == 100.0


def test_ties_are_ordered_by_hospital_id_every_time(make_hospital):
    origin = make_hospital(name="Origin")
    first = make_hospital(name="Twin one")  # the same spot, the same stock: a tie all the way down
    second = make_hospital(name="Twin two")
    for hospital in (first, second):
        ventilator(hospital)
    case, found = judge(origin, vent_need())

    assert [m.hospital.pk for m in found] == [first.pk, second.pk]
    again = match_hospitals(candidates_for_case(case))
    assert [m.hospital.pk for m in again] == [m.hospital.pk for m in found]


def test_nothing_comes_back_when_nothing_is_short(make_hospital):
    origin, other = make_hospital(name="Origin"), make_hospital(name="Other")
    bed(origin)
    bed(other)
    _, found = judge(origin, bed_need())

    assert found == []


def test_nothing_comes_back_when_no_hospital_has_any_of_it(make_hospital):
    origin = make_hospital(name="Origin")
    _, found = judge(origin, bed_need(), vent_need())

    assert found == []
