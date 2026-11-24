"""GET /api/metrics/ (B22): the hourly figures behind the trend charts, scoped like every other read."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.metrics.models import MetricSnapshot

pytestmark = pytest.mark.django_db
URL = reverse("metrics")


def hour(n=0):
    return timezone.localtime().replace(minute=0, second=0, microsecond=0) - timedelta(hours=n)


@pytest.fixture
def two(make_hospital):
    home, other = make_hospital(), make_hospital(name="Seaview Hospital")
    for h, base in ((home, 10), (other, 100)):
        for n in range(48):
            MetricSnapshot.objects.create(hospital=h, metric="er.arrivals", at=hour(n), value=base)
            MetricSnapshot.objects.create(hospital=h, metric="beds.occupied.icu", at=hour(n), value=base)
            MetricSnapshot.objects.create(
                hospital=h, metric="beds.occupied.general", at=hour(n), value=2 * base
            )
    return home, other


def test_staff_read_their_own_hospital_and_families_add_up(client_as, two):
    home, _ = two
    body = client_as(Role.NURSE, hospital=home).get(URL, {"metrics": "er.arrivals,beds.occupied"}).json()
    assert len(body["series"]["er.arrivals"]) == 24
    assert {p["value"] for p in body["series"]["er.arrivals"]} == {10}
    assert {p["value"] for p in body["series"]["beds.occupied"]} == {30}  # icu + general


def test_by_day_counts_add_up_and_levels_average(client_as, two):
    home, _ = two
    body = (
        client_as(Role.NURSE, hospital=home)
        .get(URL, {"metrics": "er.arrivals,beds.occupied", "days": 2, "bucket": "day"})
        .json()
    )
    full_days = [p for p in body["series"]["er.arrivals"] if p["value"] == 240]
    assert full_days  # 24 hours of 10
    assert {p["value"] for p in body["series"]["beds.occupied"]} == {30}


def test_the_typical_day_is_the_average_by_hour(client_as, two):
    home, _ = two
    body = (
        client_as(Role.DOCTOR, hospital=home).get(URL, {"metrics": "er.arrivals", "typical": "true"}).json()
    )
    assert {p["value"] for p in body["typical"]["er.arrivals"]} == {10}


def test_the_network_admin_reads_the_network_or_each_hospital(client_as, two):
    home, other = two
    admin = client_as(Role.ADMIN, email="network@example.com")
    network = admin.get(URL, {"metrics": "er.arrivals"}).json()
    assert {p["value"] for p in network["series"]["er.arrivals"]} == {110}
    one = admin.get(URL, {"metrics": "er.arrivals", "hospital": other.pk}).json()
    assert {p["value"] for p in one["series"]["er.arrivals"]} == {100}
    apart = admin.get(URL, {"metrics": "er.arrivals", "perHospital": "true"}).json()
    assert set(apart["series"]) == {f"er.arrivals@{home.pk}", f"er.arrivals@{other.pk}"}


def test_another_hospital_is_a_404_and_unknown_figures_a_400(client_as, two):
    home, other = two
    nurse = client_as(Role.NURSE, hospital=home)
    assert nurse.get(URL, {"metrics": "er.arrivals", "hospital": other.pk}).status_code == 404
    assert nurse.get(URL, {"metrics": "er.arrivals,patients.names"}).status_code == 400
    assert nurse.get(URL, {"metrics": "er.arrivals", "days": 90}).status_code == 400


@pytest.mark.parametrize(
    ("role", "code"), [(Role.PHARMACIST, 200), (Role.BLOOD_BANK, 200), (Role.PATIENT, 403)]
)
def test_every_staff_role_reads_figures(client_as, make_hospital, role, code):
    hospital = make_hospital()
    extra = {} if role == Role.PATIENT else {"hospital": hospital}
    assert client_as(role, **extra).get(URL, {"metrics": "er.arrivals"}).status_code == code
