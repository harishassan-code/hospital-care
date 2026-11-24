from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.ambulances.models import Ambulance, AmbulanceType, Trip
from apps.ambulances.services import dispatch_trip
from apps.blood.models import BloodGroup, BloodUnit, Component, UnitStatus
from apps.blood.services import usable_units
from apps.core.management.commands.seed_demo import DOCTORS, SPECIALIST_DAYS
from apps.core.management.commands.seed_demo import Command as SeedCommand
from apps.emergencies.models import EmergencyRequest, PatientTransfer
from apps.emergencies.patient_transfers import request_patient_transfer
from apps.emergencies.services import create_case
from apps.hospitals.models import Bed, BedType, Department, Hospital, StorageLocation, Ward
from apps.matching.allocations import allocate
from apps.matching.models import Allocation, Reservation
from apps.matching.reservations import reserve
from apps.notifications.models import Notification
from apps.pharmacy.models import Medicine
from apps.specialists.models import OnCallWindow, Specialist
from apps.transfers.models import Transfer
from apps.transfers.services import approve, request_transfer

pytestmark = pytest.mark.django_db

SEAVIEW, NORTHSIDE, MAIN = "Seaview Hospital", "Northside Children's Hospital", "CityCare General Hospital"


def counts():
    models = (Hospital, Department, Ward, StorageLocation, Bed, BloodUnit, Medicine, User, Ambulance)
    return {model.__name__: model.objects.count() for model in models}


def test_seed_demo_is_repeatable():
    call_command("seed_demo", stdout=None)
    first = counts()
    call_command("seed_demo", stdout=None)
    assert first == {
        "Hospital": 10,  # the scenario's three and seven more (B20)
        "Department": 41,
        "Ward": 56,
        "StorageLocation": 27,
        "Bed": 1088,
        "BloodUnit": 1682,  # 320 at CityCare General, the scenario's 16 per partner, and each bank's stock
        "Medicine": 23,
        "User": 6,
        "Ambulance": 31,  # the scenario's seven (story #50) and each hospital's fleet
    }
    assert counts() == first


def test_every_hospital_has_structure_and_resources():
    call_command("seed_demo", stdout=None)
    for hospital in Hospital.objects.all():
        assert hospital.is_active and hospital.capabilities.exists()
        assert hospital.departments.exists() and hospital.locations.exists()
        if hospital.type == "bloodBank":  # a blood bank has stock and donors, no beds
            assert not hospital.wards.exists() and BloodUnit.objects.filter(hospital=hospital).count() >= 500
            continue
        assert hospital.wards.exists() and Bed.objects.filter(hospital=hospital).exists()
    assert not Bed.objects.filter(hospital=None).exists()
    assert not BloodUnit.objects.filter(hospital=None).exists()
    assert not BloodUnit.objects.filter(storage_location=None).exists()


def test_beds_cover_every_bed_type():
    """Story 2.1 Bed registry: bed types include ICU, emergency, general, isolation and NICU."""
    call_command("seed_demo", stdout=None)
    assert set(Bed.objects.values_list("bed_type", flat=True)) == set(BedType.values)
    assert set(Bed.objects.filter(ward__code="icu").values_list("bed_type", flat=True)) == {BedType.ICU}


def test_one_login_per_role_and_staff_work_at_a_hospital():
    call_command("seed_demo", stdout=None)
    assert sorted(User.objects.values_list("role", flat=True)) == sorted(Role.values)
    for user in User.objects.all():
        assert (user.hospital is None) == (user.role == Role.PATIENT)


def test_links_data_from_before_sprint_2_without_duplicating_it(make_user):
    """A database seeded in Sprint 1 has wards, beds and staff with no hospital."""
    legacy = Ward.objects.create(code="icu", name="ICU", kind="Intensive care")
    Bed.objects.create(ward=legacy, label="ICU-01")
    nurse = make_user(Role.NURSE, email="nurse@demo.citycare.pk")
    call_command("seed_demo", stdout=None)
    legacy.refresh_from_db()
    nurse.refresh_from_db()
    main = Hospital.objects.get(name="CityCare General Hospital")
    assert legacy.hospital == main and legacy.department.name == "Emergency medicine"
    assert Bed.objects.filter(ward=legacy).count() == 1  # its beds aren't re-created
    assert Bed.objects.get(label="ICU-01").hospital == main
    assert nurse.hospital == main
    assert Ward.objects.filter(code="icu").count() == 1


def test_ambulances_per_hospital_and_a_rerun_adds_only_the_missing_ones():
    """Story #50: the scenario's fleet (advanced and basic at each of its hospitals, a patient transport at
    the main one) and each hospital's own (B20). A blood bank runs none."""
    call_command("seed_demo", stdout=None)
    main = Hospital.objects.get(name="CityCare General Hospital")
    assert Ambulance.objects.filter(hospital=main, type=AmbulanceType.PATIENT_TRANSPORT).count() == 1
    for hospital in Hospital.objects.all():
        kinds = set(Ambulance.objects.filter(hospital=hospital).values_list("type", flat=True))
        assert (not kinds) == (hospital.type == "bloodBank"), hospital.name
    scenario = Ambulance.objects.filter(identifier__regex=r"^AMB-0\d$")
    assert sorted(scenario.values_list("identifier", flat=True)) == [f"AMB-0{n}" for n in range(1, 8)]
    Ambulance.objects.filter(identifier="AMB-05").delete()
    call_command("seed_demo", stdout=None)
    assert Ambulance.objects.count() == 31
    assert Ambulance.objects.get(identifier="AMB-05").hospital.name == "Seaview Hospital"


def test_reset_starts_over():
    call_command("seed_demo", stdout=None)
    Department.objects.create(hospital=Hospital.objects.first(), name="Extra")
    call_command("seed_demo", "--reset", stdout=None)
    assert counts()["Department"] == 41


def o_neg_red_cells(hospital):
    return BloodUnit.objects.filter(hospital=hospital, group=BloodGroup.O_NEG, component=Component.RED_CELLS)


def unit_states():
    """Every blood unit as (hospital name, group, component, status), keyed by donation number. The hospital
    is named, not numbered: `--reset` recreates the hospitals, so their ids change."""
    rows = BloodUnit.objects.values_list("donation_number", "hospital__name", "group", "component", "status")
    return {
        number: (hospital, group, component, status) for number, hospital, group, component, status in rows
    }


def test_citycare_has_one_usable_o_neg_red_cell_for_the_mvp_scenario():
    """MVP scenario (B12): CityCare reserves its one local unit, and each scenario partner has two to
    transfer. Seaview's expire first of all the network's usable O- red cells, so it ranks first as the
    source."""
    call_command("seed_demo", stdout=None)
    main = Hospital.objects.get(name=MAIN)
    assert usable_units(o_neg_red_cells(main)).count() == 1
    for name in (SEAVIEW, NORTHSIDE):
        assert usable_units(o_neg_red_cells(Hospital.objects.get(name=name))).count() == 2
    seaview_first = usable_units(o_neg_red_cells(Hospital.objects.get(name=SEAVIEW))).order_by("expires_at")[
        0
    ]
    others = BloodUnit.objects.filter(group=BloodGroup.O_NEG, component=Component.RED_CELLS).exclude(
        hospital__name__in=(MAIN, SEAVIEW)
    )
    assert all(u.expires_at > seaview_first.expires_at for u in usable_units(others))


def test_scenario_stock_is_the_same_on_every_fresh_seed():
    call_command("seed_demo", stdout=None)
    first = unit_states()
    call_command("seed_demo", "--reset", stdout=None)
    assert unit_states() == first


def test_scenario_change_touches_only_citycare_o_neg_red_cells(monkeypatch):
    """Without the scenario change, every unit keeps the status the random draws gave it. With it, the only
    units that differ are CityCare's O- red cells, and no unit is added or removed."""
    with monkeypatch.context() as patch:
        patch.setattr(SeedCommand, "seed_scenario_stock", lambda self, hospital, now: None)
        call_command("seed_demo", stdout=None)
    drawn = unit_states()
    call_command("seed_demo", "--reset", stdout=None)
    scenario = unit_states()
    assert scenario.keys() == drawn.keys()
    changed = [number for number in drawn if drawn[number] != scenario[number]]
    assert changed, "the scenario change should alter the O- red cells, or this test proves nothing"
    for number in changed:
        hospital, group, component, _ = scenario[number]
        assert (hospital, group, component) == (MAIN, BloodGroup.O_NEG, Component.RED_CELLS)


def test_scenario_stock_makes_a_reserved_unit_usable_when_none_is_usable():
    call_command("seed_demo", stdout=None)
    main = Hospital.objects.get(name=MAIN)
    units = o_neg_red_cells(main)
    units.update(status=UnitStatus.EXPIRED)
    spare = units.filter(expires_at__gt=timezone.now()).order_by("expires_at").first()
    units.filter(pk=spare.pk).update(status=UnitStatus.RESERVED)
    SeedCommand().seed_scenario_stock(main, timezone.now())
    spare.refresh_from_db()
    assert spare.status == UnitStatus.AVAILABLE
    assert usable_units(units).count() == 1


def test_scenario_stock_refuses_to_guess_when_no_o_neg_red_cell_can_be_used():
    call_command("seed_demo", stdout=None)
    main = Hospital.objects.get(name=MAIN)
    o_neg_red_cells(main).delete()
    with pytest.raises(CommandError, match="--seed"):
        SeedCommand().seed_scenario_stock(main, timezone.now())


def test_specialists_are_the_demo_doctors_at_their_hospitals():
    """The scenario's three list the demo doctors (B16); the rest list consultants from their own rosters
    (B20)."""
    call_command("seed_demo", stdout=None)
    scenario = Specialist.objects.select_related("hospital").filter(
        hospital__name__in=(SEAVIEW, NORTHSIDE, MAIN)
    )
    hospital_of = {s.name: s.hospital.name for s in scenario}
    assert set(hospital_of) == {name for name, *_ in DOCTORS}
    assert set(hospital_of.values()) == {SEAVIEW, NORTHSIDE, MAIN}
    for specialist in Specialist.objects.exclude(hospital__name__in=(SEAVIEW, NORTHSIDE, MAIN)):
        assert specialist.hospital.staff_members.filter(name=specialist.name, role="doctor").exists()
    assert hospital_of["Dr. Ayesha Khan"] == SEAVIEW  # Cardiology
    assert hospital_of["Dr. Sana Malik"] == NORTHSIDE  # Paediatrics
    assert hospital_of["Dr. Kamran Shah"] == MAIN  # Emergency medicine
    assert {s.specialty for s in scenario} == {department for _, department, *_ in DOCTORS}


def test_every_specialist_has_a_window_for_each_of_the_next_days_in_karachi():
    call_command("seed_demo", stdout=None)
    today = timezone.localdate()
    for specialist in Specialist.objects.all():
        days = [
            timezone.localtime(w.starts_at).date() for w in specialist.on_call_windows.order_by("starts_at")
        ]
        assert days == [today + timedelta(days=offset) for offset in range(SPECIALIST_DAYS)], specialist.name


def test_windows_never_overlap_and_an_overnight_shift_ends_the_next_morning():
    call_command("seed_demo", stdout=None)
    for specialist in Specialist.objects.all():
        windows = list(specialist.on_call_windows.order_by("starts_at"))
        for earlier, later in zip(windows, windows[1:], strict=False):
            assert earlier.ends_at <= later.starts_at, specialist.name
    usman = Specialist.objects.get(name="Dr. Usman Farooq").on_call_windows.order_by("starts_at").first()
    starts, ends = timezone.localtime(usman.starts_at), timezone.localtime(usman.ends_at)
    assert (starts.hour, starts.minute) == (20, 0)
    assert (ends.hour, ends.minute) == (8, 0)
    assert ends.date() == starts.date() + timedelta(days=1)


def test_a_rerun_adds_no_specialist_and_no_window_it_already_has():
    call_command("seed_demo", stdout=None)
    first = (Specialist.objects.count(), OnCallWindow.objects.count())
    call_command("seed_demo", stdout=None)
    assert first[1] == first[0] * SPECIALIST_DAYS and first[0] > len(DOCTORS)
    assert (Specialist.objects.count(), OnCallWindow.objects.count()) == first


def test_a_rerun_fills_in_a_missing_window_and_duplicates_nothing():
    call_command("seed_demo", stdout=None)
    OnCallWindow.objects.filter(specialist__name="Dr. Kamran Shah").order_by("starts_at").first().delete()
    call_command("seed_demo", stdout=None)
    assert OnCallWindow.objects.filter(specialist__name="Dr. Kamran Shah").count() == SPECIALIST_DAYS
    assert OnCallWindow.objects.count() == Specialist.objects.count() * SPECIALIST_DAYS


def test_a_rerun_leaves_a_specialist_added_by_staff_alone():
    call_command("seed_demo", stdout=None)
    seeded = Specialist.objects.count()
    Specialist.objects.create(hospital=Hospital.objects.first(), name="Dr. Added Later", specialty="Oncology")
    call_command("seed_demo", stdout=None)
    assert Specialist.objects.get(name="Dr. Added Later").on_call_windows.count() == 0
    assert OnCallWindow.objects.count() == seeded * SPECIALIST_DAYS


def test_reset_starts_the_specialists_over():
    call_command("seed_demo", stdout=None)
    seeded = Specialist.objects.count()
    Specialist.objects.create(hospital=Hospital.objects.first(), name="Dr. Extra", specialty="ENT")
    call_command("seed_demo", "--reset", stdout=None)
    assert Specialist.objects.count() == seeded
    assert OnCallWindow.objects.count() == seeded * SPECIALIST_DAYS


def rehearse():
    """What a demo rehearsal leaves behind, through the real services: a critical case at CityCare (with its
    alerts), its local hold allocated, a stock transfer from Seaview carried by an ambulance, and a request to
    move the patient to Northside. Each of these protects a hospital, a need or a resource from deletion."""
    main, seaview, northside = (Hospital.objects.get(name=name) for name in (MAIN, SEAVIEW, NORTHSIDE))
    nurse = User.objects.get(email="nurse@demo.citycare.pk")
    admin = User.objects.get(email="admin@demo.citycare.pk")
    need = {"type": "blood", "group": BloodGroup.O_NEG, "component": Component.RED_CELLS, "quantity": 3}
    case = create_case(severity="critical", patient_ref="SYN-REHEARSAL", items=[need], actor=nurse)
    item = case.items.get()
    [hold] = reserve(item, hospital=main, quantity=1, actor=nurse)
    allocate(hold.pk, actor=admin)
    transfer = approve(request_transfer(item, supplier=seaview, quantity=1, actor=nurse), actor=admin)
    van = Ambulance.objects.filter(hospital=seaview).order_by("identifier").first()
    dispatch_trip(transfer, ambulance_id=van.pk, actor=admin)
    request_patient_transfer(case, destination=northside, actor=nurse)


REHEARSAL_ROWS = (EmergencyRequest, Reservation, Allocation, Transfer, Trip, PatientTransfer, Notification)


def test_reset_after_a_rehearsal_clears_its_cases_and_gives_a_fresh_seed():
    """A rehearsal leaves cases, holds, transfers, a trip and alerts that protect the hospitals and stock the
    reset deletes. The reset clears them first, so it gives a fresh seed's data, not a ProtectedError."""
    call_command("seed_demo", stdout=None)
    fresh = counts()
    rehearse()
    assert all(model.objects.exists() for model in REHEARSAL_ROWS), "the rehearsal should leave every kind"

    call_command("seed_demo", "--reset", stdout=None)

    assert [model.__name__ for model in REHEARSAL_ROWS if model.objects.exists()] == []
    assert counts() == fresh
    assert usable_units(o_neg_red_cells(Hospital.objects.get(name=MAIN))).count() == 1  # the MVP scenario's
