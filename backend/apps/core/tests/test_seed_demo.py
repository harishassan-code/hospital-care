from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.blood.models import BloodUnit
from apps.core.management.commands.seed_demo import DOCTORS, SPECIALIST_DAYS
from apps.hospitals.models import Bed, BedType, Department, Hospital, StorageLocation, Ward
from apps.pharmacy.models import Medicine
from apps.specialists.models import OnCallWindow, Specialist

pytestmark = pytest.mark.django_db

SEAVIEW, NORTHSIDE, MAIN = "Seaview Hospital", "Northside Children's Hospital", "CityCare General Hospital"


def counts():
    models = (Hospital, Department, Ward, StorageLocation, Bed, BloodUnit, Medicine, User)
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


def test_reset_starts_over():
    call_command("seed_demo", stdout=None)
    Department.objects.create(hospital=Hospital.objects.first(), name="Extra")
    call_command("seed_demo", "--reset", stdout=None)
    assert counts()["Department"] == 10


def test_specialists_are_the_demo_doctors_at_their_hospitals():
    call_command("seed_demo", stdout=None)
    hospital_of = {s.name: s.hospital.name for s in Specialist.objects.select_related("hospital")}
    assert set(hospital_of) == {name for name, *_ in DOCTORS}
    assert set(hospital_of.values()) == {SEAVIEW, NORTHSIDE, MAIN}
    assert hospital_of["Dr. Ayesha Khan"] == SEAVIEW  # Cardiology
    assert hospital_of["Dr. Sana Malik"] == NORTHSIDE  # Paediatrics
    assert hospital_of["Dr. Kamran Shah"] == MAIN  # Emergency medicine
    assert {s.specialty for s in Specialist.objects.all()} == {department for _, department, *_ in DOCTORS}


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
    assert first == (len(DOCTORS), len(DOCTORS) * SPECIALIST_DAYS)
    assert (Specialist.objects.count(), OnCallWindow.objects.count()) == first


def test_a_rerun_fills_in_a_missing_window_and_duplicates_nothing():
    call_command("seed_demo", stdout=None)
    OnCallWindow.objects.filter(specialist__name="Dr. Kamran Shah").order_by("starts_at").first().delete()
    call_command("seed_demo", stdout=None)
    assert OnCallWindow.objects.filter(specialist__name="Dr. Kamran Shah").count() == SPECIALIST_DAYS
    assert OnCallWindow.objects.count() == len(DOCTORS) * SPECIALIST_DAYS


def test_reset_starts_the_specialists_over():
    call_command("seed_demo", stdout=None)
    Specialist.objects.create(hospital=Hospital.objects.first(), name="Dr. Extra", specialty="ENT")
    call_command("seed_demo", "--reset", stdout=None)
    assert Specialist.objects.count() == len(DOCTORS)
    assert OnCallWindow.objects.count() == len(DOCTORS) * SPECIALIST_DAYS
