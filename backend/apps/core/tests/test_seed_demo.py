import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.blood.models import BloodUnit
from apps.hospitals.models import Bed, Department, Hospital, StorageLocation, Ward
from apps.pharmacy.models import Medicine

pytestmark = pytest.mark.django_db


def counts():
    models = (Hospital, Department, Ward, StorageLocation, Bed, BloodUnit, Medicine, User)
    return {model.__name__: model.objects.count() for model in models}


def test_seed_demo_is_repeatable():
    call_command("seed_demo", stdout=None)
    first = counts()
    call_command("seed_demo", stdout=None)
    assert first == {
        "Hospital": 3,
        "Department": 9,
        "Ward": 11,
        "StorageLocation": 10,
        "Bed": 154,
        "BloodUnit": 320,
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
    assert counts()["Department"] == 9
