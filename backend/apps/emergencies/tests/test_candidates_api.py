"""Story #38: GET /api/emergencies/<reference>/candidates/, the other hospitals that can supply each short
need. Story #41: each item's hospitals come ranked and scored, with the breakdown of each score.
Story #42: the hospitals judged across all the short needs at once."""

import itertools
from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestItem, RequestStatusChange
from apps.equipment.models import Equipment, EquipmentStatus
from apps.hospitals.models import Bed, BedStatus, Ward
from apps.matching.scoring import parse_scoring_config

pytestmark = pytest.mark.django_db

_numbers = itertools.count(1)
REFERENCE = "EC-2026-0001"


def unit(hospital, group="O-", component="redCells", expires_in=30):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=f"U{next(_numbers)}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in),
        status=UnitStatus.AVAILABLE,
        location="Blood fridge 1",
    )


def bed(hospital, bed_type="icu", status=BedStatus.FREE):
    ward, _ = Ward.objects.get_or_create(
        code=f"ward-{hospital.pk}", defaults={"name": "Ward", "kind": "General", "hospital": hospital}
    )
    return Bed.objects.create(ward=ward, label=f"B{next(_numbers)}", bed_type=bed_type, status=status)


def ventilator(hospital):
    return Equipment.objects.create(
        hospital=hospital,
        identifier=f"VENT-{next(_numbers)}",
        equipment_type="ventilator",
        location="ICU",
        status=EquipmentStatus.AVAILABLE,
    )


def case(hospital, *needs):
    """Each need is a dict of RequestItem fields."""
    created = EmergencyRequest.objects.create(reference=REFERENCE, severity="critical", hospital=hospital)
    for need in needs:
        RequestItem.objects.create(request=created, **need)
    return created


def blood(quantity):
    return {"resource_type": "blood", "blood_group": "O-", "component": "redCells", "quantity": quantity}


def icu(quantity):
    return {"resource_type": "bed", "bed_type": "icu", "quantity": quantity}


def vents(quantity):
    return {"resource_type": "equipment", "equipment_type": "ventilator", "quantity": quantity}


def get(client, reference=REFERENCE):
    return client.get(reverse("emergency-case-candidates", args=[reference]))


def test_each_short_need_lists_the_hospitals_that_have_it(client_as, make_hospital):
    here = make_hospital(name="Here", latitude="24.860700", longitude="67.001100")
    there = make_hospital(name="There", latitude="24.960700", longitude="67.001100")  # about 11 km north
    spare = make_hospital(name="Spare")  # the default coordinates, close to here
    unit(here)  # one O- red cell at home: 3 of 4 short
    for _ in range(5):
        unit(there)
    bed(there, "icu")
    ventilator(spare)
    created = case(here, blood(4), icu(1), vents(2))
    doctor = client_as(Role.DOCTOR, hospital=here)

    res = get(doctor)

    assert res.status_code == 200
    body = res.json()
    assert body["reference"] == REFERENCE
    blood_item, bed_item, vent_item = body["items"]
    assert (blood_item["need"], blood_item["shortfall"]) == ("O- red cells", 3)
    assert (bed_item["need"], bed_item["shortfall"]) == ("ICU bed", 1)
    assert (vent_item["need"], vent_item["shortfall"]) == ("Ventilator", 2)
    assert [item["itemId"] for item in body["items"]] == list(
        created.items.order_by("id").values_list("pk", flat=True)
    )

    [there_blood] = blood_item["candidates"]
    assert there_blood["hospital"] == {"id": there.pk, "name": "There"}
    assert (there_blood["available"], there_blood["covers"]) == (5, True)
    assert there_blood["distanceKm"] == pytest.approx(11.1, abs=0.1)
    assert there_blood["travelMinutes"] == 17
    assert there_blood["earliestExpiry"] and there_blood["bestDonorRank"] == 0
    [there_bed] = bed_item["candidates"]
    assert (
        there_bed["available"] == 1 and "earliestExpiry" not in there_bed and "bestDonorRank" not in there_bed
    )
    [spare_vent] = vent_item["candidates"]
    assert (spare_vent["hospital"]["name"], spare_vent["available"], spare_vent["covers"]) == (
        "Spare",
        1,
        False,
    )


def test_a_need_with_nobody_to_give_it_has_no_candidates(client_as, make_hospital):
    here = make_hospital(name="Here")
    case(here, icu(1))

    [item] = get(client_as(Role.DOCTOR, hospital=here)).json()["items"]

    assert item["candidates"] == []


def test_only_the_short_needs_are_listed(client_as, make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    bed(here, "icu")  # covers the bed need here
    bed(there, "icu")
    unit(there)
    case(here, icu(1), blood(2))

    body = get(client_as(Role.DOCTOR, hospital=here)).json()

    assert [item["need"] for item in body["items"]] == ["O- red cells"]


def test_a_case_covered_locally_has_no_items(client_as, make_hospital):
    here = make_hospital(name="Here")
    bed(here, "icu")
    case(here, icu(1))

    assert get(client_as(Role.DOCTOR, hospital=here)).json() == {
        "reference": REFERENCE,
        "items": [],
        "hospitals": [],
    }


def test_another_hospitals_case_is_not_found(client_as, make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    case(here, icu(1))

    assert get(client_as(Role.DOCTOR, hospital=there)).status_code == 404


def test_a_patient_is_refused(client_as, make_hospital):
    here = make_hospital(name="Here")
    case(here, icu(1))

    assert get(client_as(Role.PATIENT)).status_code == 403


def test_the_read_does_not_escalate_an_overdue_case(client_as, make_hospital, settings):
    """The list and the detail escalate an overdue critical case; this read leaves it alone."""
    settings.EMERGENCY_ESCALATION_MINUTES = 30
    here = make_hospital(name="Here")
    created = case(here, icu(1))
    RequestStatusChange.objects.create(
        request=created, to_status="open", action="create", at=timezone.now() - timedelta(hours=2)
    )
    doctor = client_as(Role.DOCTOR, hospital=here)

    get(doctor)
    created.refresh_from_db()
    assert created.status == "open"

    assert doctor.get(reverse("emergency-case", args=[REFERENCE])).status_code == 200
    created.refresh_from_db()
    assert created.status == "escalated"  # the setup is overdue: the detail read does escalate it


# Story #41: ranked results with their scores. The default scoring, whatever the environment says.


@pytest.fixture(autouse=True)
def default_scoring():
    with override_settings(MATCHING_SCORING=parse_scoring_config(""), MATCHING_MAX_DISTANCE_KM=50):
        yield


def sole_item(client_as, hospital):
    [item] = get(client_as(Role.DOCTOR, hospital=hospital)).json()["items"]
    return item


def test_blood_sources_are_ranked_earliest_expiry_first_at_equal_distance(client_as, make_hospital):
    here = make_hospital(name="Here")
    later = make_hospital(name="Later")  # default coordinates: the same distance as here
    soon = make_hospital(name="Soon")
    for _ in range(4):
        unit(later, expires_in=30)
        unit(soon, expires_in=3)
    case(here, blood(4))

    item = sole_item(client_as, here)

    assert item["strategy"] == {"name": "earliestExpiry", "label": "Earliest expiry first"}
    assert [c["hospital"]["name"] for c in item["candidates"]] == ["Soon", "Later"]
    assert [c["rank"] for c in item["candidates"]] == [1, 2]
    assert [c["recommended"] for c in item["candidates"]] == [True, False]


def test_bed_sources_are_ranked_nearest_first_even_when_created_later(client_as, make_hospital):
    here = make_hospital(name="Here")
    far = make_hospital(name="Far", latitude="24.960700", longitude="67.001100")  # about 11 km north, first
    near = make_hospital(name="Near")  # the same spot as here
    for h in (far, near):
        bed(h, "icu")
        bed(h, "icu")
    case(here, icu(2))

    item = sole_item(client_as, here)

    assert item["strategy"] == {"name": "nearest", "label": "Nearest first"}
    assert [c["hospital"]["name"] for c in item["candidates"]] == ["Near", "Far"]


def test_only_the_first_source_is_recommended(client_as, make_hospital):
    here = make_hospital(name="Here")
    near = make_hospital(name="Near")
    far = make_hospital(name="Far", latitude="24.960700", longitude="67.001100")
    for h in (near, far):
        bed(h, "icu")
    case(here, icu(1))

    item = sole_item(client_as, here)

    assert [c["recommended"] for c in item["candidates"]] == [True, False]


def test_a_first_source_with_a_score_of_zero_is_not_recommended(client_as, make_hospital):
    here = make_hospital(name="Here")
    beyond = make_hospital(name="Beyond", latitude="25.560700", longitude="67.001100")  # about 78 km
    bed(beyond, "icu")
    case(here, icu(1))
    # Only distance counts, and the hospital is past the maximum distance.
    raw = '{"bed": {"weights": {"distance": 1, "quantity": 0}}}'

    with override_settings(MATCHING_SCORING=parse_scoring_config(raw)):
        item = sole_item(client_as, here)

    [beyond_row] = item["candidates"]
    assert (beyond_row["rank"], beyond_row["score"]["total"], beyond_row["recommended"]) == (1, 0.0, False)


def test_each_candidate_breaks_its_score_down_into_points_that_add_up(client_as, make_hospital):
    here = make_hospital(name="Here")
    there = make_hospital(name="There", latitude="24.960700", longitude="67.001100")  # about 11.1 km north
    for _ in range(5):
        unit(there, expires_in=9)
    case(here, blood(3))

    [row] = sole_item(client_as, here)["candidates"]
    score = row["score"]

    assert score["strategy"] == "earliestExpiry"
    assert [f["name"] for f in score["factors"]] == ["expiry", "compatibility", "distance", "quantity"]
    assert [f["label"] for f in score["factors"]] == ["Expiry", "Blood group match", "Distance", "Stock"]
    assert {f["name"]: f["detail"] for f in score["factors"]} == {
        "expiry": "expires in 9 days",
        "compatibility": "identical group",
        "distance": "11.1 km, about 17 min",
        "quantity": "5 available, 3 needed",
    }
    assert sum(f["points"] for f in score["factors"]) == pytest.approx(score["total"], abs=0.05)
    assert sum(f["weight"] for f in score["factors"]) == pytest.approx(1.0, abs=0.02)
    assert all(0 <= f["value"] <= 1 for f in score["factors"])


def test_the_scoring_setting_changes_the_order_through_the_api(client_as, make_hospital):
    here = make_hospital(name="Here")
    near = make_hospital(name="Near")  # the same spot as here
    deep = make_hospital(name="Deep", latitude="24.960700", longitude="67.001100")  # about 11 km north
    bed(near, "icu")
    bed(near, "icu")  # 2 of the 3 needed
    for _ in range(3):
        bed(deep, "icu")  # all 3
    case(here, icu(3))
    doctor = client_as(Role.DOCTOR, hospital=here)

    [item] = get(doctor).json()["items"]
    assert [c["hospital"]["name"] for c in item["candidates"]] == ["Near", "Deep"]

    with override_settings(MATCHING_SCORING=parse_scoring_config('{"bed": {"strategy": "mostStock"}}')):
        [item] = get(doctor).json()["items"]
    assert [c["hospital"]["name"] for c in item["candidates"]] == ["Deep", "Near"]
    assert item["strategy"] == {"name": "mostStock", "label": "Most stock first"}


# Story #42: the hospitals judged across all the short needs at once.


def hospitals_for(client_as, hospital):
    return get(client_as(Role.DOCTOR, hospital=hospital)).json()["hospitals"]


def test_three_needs_across_three_hospitals_put_the_one_with_everything_first(client_as, make_hospital):
    here = make_hospital(name="Here")
    full = make_hospital(name="Full", latitude="25.220700", longitude="67.001100")  # about 40 km north
    bed_and_blood = make_hospital(
        name="Bed and blood", latitude="24.960700", longitude="67.001100"
    )  # about 11 km north
    vent_only = make_hospital(name="Vent only")  # the same spot as here: nearest, best scored, still partial
    bed(full, "icu")
    ventilator(full)
    unit(full)
    unit(full)
    bed(bed_and_blood, "icu")
    for _ in range(5):
        unit(bed_and_blood)
    ventilator(vent_only)
    created = case(here, icu(1), vents(1), blood(2))
    icu_id, vent_id, blood_id = created.items.order_by("id").values_list("pk", flat=True)

    full_row, two_row, vent_row = hospitals_for(client_as, here)

    assert [row["hospital"]["name"] for row in (full_row, two_row, vent_row)] == [
        "Full",
        "Bed and blood",
        "Vent only",
    ]
    assert [row["rank"] for row in (full_row, two_row, vent_row)] == [1, 2, 3]
    assert (full_row["complete"], full_row["recommended"], full_row["coverage"]) == (True, True, "3 of 3")
    assert (full_row["coveredCount"], full_row["totalNeeds"], full_row["unmet"]) == (3, 3, [])
    assert {need["need"] for need in full_row["covered"]} == {"ICU bed", "Ventilator", "O- red cells"}
    assert full_row["distanceKm"] == pytest.approx(40.0, abs=0.5)
    assert full_row["travelMinutes"] == 60

    assert (two_row["complete"], two_row["recommended"], two_row["coverage"]) == (False, False, "2 of 3")
    assert two_row["unmet"] == [{"itemId": vent_id, "need": "Ventilator", "missing": 1, "available": 0}]

    assert vent_row["unmet"] == [
        {"itemId": icu_id, "need": "ICU bed", "missing": 1, "available": 0},
        {"itemId": blood_id, "need": "O- red cells", "missing": 2, "available": 0},
    ]


def test_only_a_hospital_with_everything_is_recommended(client_as, make_hospital):
    here = make_hospital(name="Here")
    bed_only, vent_only = make_hospital(name="Bed only"), make_hospital(name="Vent only")
    bed(bed_only)
    ventilator(vent_only)
    case(here, icu(1), vents(1))

    rows = hospitals_for(client_as, here)

    assert [row["complete"] for row in rows] == [False, False]
    assert [row["recommended"] for row in rows] == [False, False]


def test_a_partial_quantity_is_unmet_with_what_the_hospital_has(client_as, make_hospital):
    here, stock = make_hospital(name="Here"), make_hospital(name="Stock")
    ventilator(stock)
    created = case(here, vents(2))
    [vent_id] = created.items.values_list("pk", flat=True)

    [row] = hospitals_for(client_as, here)

    assert row["unmet"] == [{"itemId": vent_id, "need": "Ventilator", "missing": 1, "available": 1}]
    assert row["coverage"] == "0 of 1"
