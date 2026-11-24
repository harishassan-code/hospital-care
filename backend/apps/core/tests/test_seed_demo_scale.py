"""B13 search performance (spec seed section): `seed_demo --hospitals N` adds synthetic hospitals to the demo
network for the load test. The ten named hospitals (B20) keep their data at any N, running it again adds
nothing, and N below 3 (the scenario's hospitals) is refused."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.blood.models import BloodUnit, DonationAppointment
from apps.core.management.commands.seed_demo import HOSPITALS
from apps.emergencies.models import EmergencyRequest
from apps.equipment.models import Equipment
from apps.hospitals.models import Bed, Hospital, Ward
from apps.operating_rooms.models import OperatingRoom

pytestmark = pytest.mark.django_db

NAMED = [spec[0] for spec in HOSPITALS]


def seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def named_hospital_data():
    """What the named hospitals hold: bed labels and states, and blood unit ids. Times are left out, since
    each run reads the clock."""
    data = {}
    for hospital in Hospital.objects.filter(name__in=NAMED).order_by("name"):
        data[hospital.name] = {
            "beds": list(
                Bed.objects.filter(hospital=hospital)
                .order_by("label")
                .values_list("label", "bed_type", "status")
            ),
            "units": list(
                BloodUnit.objects.filter(hospital=hospital)
                .order_by("donation_number")
                .values_list("donation_number", "group", "component")
            ),
        }
    return data


def counts():
    models = (Hospital, Ward, Bed, BloodUnit, DonationAppointment, Equipment, OperatingRoom, EmergencyRequest)
    return {model.__name__: model.objects.count() for model in models}


def test_the_default_is_the_named_hospitals():
    seed()
    assert sorted(Hospital.objects.values_list("name", flat=True)) == sorted(NAMED)


def test_hospitals_after_the_named_ones_are_synthetic_and_complete():
    seed("--hospitals", "13")
    synthetic = Hospital.objects.exclude(name__in=NAMED).order_by("name")
    assert [hospital.name for hospital in synthetic] == [
        "Synthetic Hospital 11",
        "Synthetic Hospital 12",
        "Synthetic Hospital 13",
    ]
    for hospital in synthetic:
        assert hospital.address == "Karachi (synthetic)"
        assert hospital.capabilities.exists()
        assert hospital.departments.exists() and hospital.locations.exists() and hospital.wards.exists()
        assert Bed.objects.filter(hospital=hospital).exists()
        assert BloodUnit.objects.filter(hospital=hospital).count() == 16  # the partner stock, as before
        assert 24.5 < float(hospital.latitude) < 25.2 and 66.7 < float(hospital.longitude) < 67.3


def test_synthetic_wards_never_share_a_code_or_a_bed_label():
    seed("--hospitals", "14")
    codes = list(Ward.objects.values_list("code", flat=True))
    assert len(codes) == len(set(codes))
    assert Ward.objects.filter(hospital__name="Synthetic Hospital 14").exists()


def test_the_named_hospitals_keep_their_data_at_any_size():
    seed()
    default = named_hospital_data()
    seed("--reset", "--hospitals", "12")
    assert named_hospital_data() == default
    assert Hospital.objects.count() == 12


def test_running_it_again_at_the_same_size_adds_nothing():
    seed("--hospitals", "12")
    first = counts()
    seed("--hospitals", "12")
    assert counts() == first


def test_fewer_than_three_hospitals_is_refused_before_anything_is_written():
    with pytest.raises(CommandError, match="3 or more"):
        seed("--hospitals", "2")
    assert not Hospital.objects.exists()
