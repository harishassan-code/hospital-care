import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.ambulances.models import Ambulance, AmbulanceType
from apps.blood.models import BloodGroup, BloodUnit, Component, UnitStatus
from apps.blood.services import usable_units
from apps.core.management.commands.seed_demo import Command as SeedCommand
from apps.hospitals.models import Bed, BedType, Department, Hospital, StorageLocation, Ward
from apps.pharmacy.models import Medicine

pytestmark = pytest.mark.django_db

MAIN = "CityCare General Hospital"


def counts():
    models = (Hospital, Department, Ward, StorageLocation, Bed, BloodUnit, Medicine, User, Ambulance)
    return {model.__name__: model.objects.count() for model in models}


def test_seed_demo_is_repeatable():
    call_command("seed_demo", stdout=None)
    first = counts()
    call_command("seed_demo", stdout=None)
    assert first == {
        "Hospital": 3,
        "Department": 10,
        "Ward": 12,
        "StorageLocation": 10,
        "Bed": 164,
        "BloodUnit": 352,  # 320 at CityCare General, 16 at each other hospital (Sprint 7 transfers)
        "Medicine": 23,
        "User": 6,
        "Ambulance": 7,  # two per hospital, and a patient transport at CityCare General (story #50)
    }
    assert counts() == first


def test_every_hospital_has_structure_and_resources():
    call_command("seed_demo", stdout=None)
    for hospital in Hospital.objects.all():
        assert hospital.is_active and hospital.capabilities.exists()
        assert hospital.departments.exists() and hospital.locations.exists() and hospital.wards.exists()
        assert Bed.objects.filter(hospital=hospital).exists()
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
    """Story #50: advanced and basic at every hospital, and a patient transport at the main one."""
    call_command("seed_demo", stdout=None)
    main = Hospital.objects.get(name="CityCare General Hospital")
    assert Ambulance.objects.filter(hospital=main, type=AmbulanceType.PATIENT_TRANSPORT).count() == 1
    for hospital in Hospital.objects.all():
        kinds = sorted(Ambulance.objects.filter(hospital=hospital).values_list("type", flat=True))
        expected = ["advanced", "basic", "patientTransport"] if hospital == main else ["advanced", "basic"]
        assert kinds == sorted(expected)
    Ambulance.objects.filter(identifier="AMB-05").delete()
    call_command("seed_demo", stdout=None)
    assert Ambulance.objects.count() == 7
    assert Ambulance.objects.get(identifier="AMB-05").hospital.name == "Seaview Hospital"


def test_reset_starts_over():
    call_command("seed_demo", stdout=None)
    Department.objects.create(hospital=Hospital.objects.first(), name="Extra")
    call_command("seed_demo", "--reset", stdout=None)
    assert counts()["Department"] == 10


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
    """MVP scenario (B12): CityCare reserves its one local unit, and each partner has two to transfer."""
    call_command("seed_demo", stdout=None)
    main = Hospital.objects.get(name=MAIN)
    assert usable_units(o_neg_red_cells(main)).count() == 1
    partners = Hospital.objects.exclude(pk=main.pk)
    assert partners.count() == 2
    for partner in partners:
        assert usable_units(o_neg_red_cells(partner)).count() == 2


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
