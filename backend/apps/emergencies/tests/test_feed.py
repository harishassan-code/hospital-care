"""Story #36: the network request feed. Active requests from every hospital, most urgent first, no
patient data."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.emergencies.models import EmergencyRequest, RequestItem, RequestStatusChange

pytestmark = pytest.mark.django_db

FEED = "emergency-feed"
ENTRY_KEYS = {"reference", "hospital", "severity", "status", "createdAt", "needs"}
BLOOD_KEYS = {"type", "group", "component", "quantity", "fulfilled"}
BED_KEYS = {"type", "bedType", "quantity", "fulfilled"}


def make_case(hospital, reference, *, severity="high", status="open", patient_ref="", minutes_ago=5):
    case = EmergencyRequest.objects.create(
        reference=reference, hospital=hospital, severity=severity, status=status, patient_ref=patient_ref
    )
    # created_at and the creation entry are set on insert; move both so the age is what the test says.
    then = timezone.now() - timedelta(minutes=minutes_ago)
    EmergencyRequest.objects.filter(pk=case.pk).update(created_at=then)
    RequestStatusChange.objects.create(
        request=case, from_status="", to_status=status, action="create", at=then
    )
    return case


def blood(case, group="O-", component="redCells", quantity=2, fulfilled=0):
    return RequestItem.objects.create(
        request=case,
        resource_type="blood",
        blood_group=group,
        component=component,
        quantity=quantity,
        fulfilled=fulfilled,
    )


def bed(case, bed_type="icu", quantity=1):
    return RequestItem.objects.create(request=case, resource_type="bed", bed_type=bed_type, quantity=quantity)


def feed(client, type_=None):
    url = reverse(FEED) + (f"?type={type_}" if type_ is not None else "")
    return client.get(url)


def references(client, type_=None):
    res = feed(client, type_)
    assert res.status_code == 200
    return [entry["reference"] for entry in res.json()]


# ── What it lists ───────────────────────────────────────────────────────────────────────────────


def test_it_lists_active_blood_requests_from_every_hospital(client_as, make_hospital, make_user):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    blood(make_case(here, "EC-2026-0001"))
    blood(make_case(there, "EC-2026-0002"))
    blood(make_case(None, "EC-2026-0003"))  # made by someone with no hospital (an admin)
    bank = client_as(Role.BLOOD_BANK, hospital=here)

    res = feed(bank)

    assert res.status_code == 200
    by_reference = {entry["reference"]: entry for entry in res.json()}
    assert set(by_reference) == {"EC-2026-0001", "EC-2026-0002", "EC-2026-0003"}
    assert by_reference["EC-2026-0002"]["hospital"] == {"id": there.pk, "name": "There"}
    assert by_reference["EC-2026-0003"]["hospital"] is None


@pytest.mark.parametrize(
    ("status", "listed"),
    [
        ("open", True),
        ("matching", True),
        ("partiallyFulfilled", True),
        ("escalated", True),
        ("fulfilled", False),
        ("closed", False),
        ("cancelled", False),
    ],
)
def test_only_active_statuses_are_listed(client_as, make_hospital, status, listed):
    blood(make_case(make_hospital(), "EC-2026-0001", status=status))

    assert references(client_as(Role.DOCTOR)) == (["EC-2026-0001"] if listed else [])


def test_a_case_with_no_blood_need_is_not_in_the_blood_feed(client_as, make_hospital):
    bed(make_case(make_hospital(), "EC-2026-0001"))
    doctor = client_as(Role.DOCTOR)

    assert references(doctor) == []
    assert references(doctor, "bed") == ["EC-2026-0001"]


def test_ordered_by_severity_then_age(client_as, make_hospital):
    hospital = make_hospital()
    blood(make_case(hospital, "EC-2026-0001", severity="low", minutes_ago=90))
    blood(make_case(hospital, "EC-2026-0002", severity="critical", minutes_ago=5))
    blood(make_case(hospital, "EC-2026-0003", severity="high", minutes_ago=30))
    blood(make_case(hospital, "EC-2026-0004", severity="critical", minutes_ago=60))
    blood(make_case(hospital, "EC-2026-0005", severity="moderate", minutes_ago=45))

    assert references(client_as(Role.BLOOD_BANK)) == [
        "EC-2026-0004",  # critical, older
        "EC-2026-0002",  # critical, newer
        "EC-2026-0003",
        "EC-2026-0005",
        "EC-2026-0001",
    ]


def test_type_bed_lists_bed_requests_and_shows_only_their_bed_needs(client_as, make_hospital):
    case = make_case(make_hospital(), "EC-2026-0001")
    blood(case)
    bed(case, "icu", 2)
    doctor = client_as(Role.DOCTOR)

    [entry] = feed(doctor, "bed").json()

    assert entry["reference"] == "EC-2026-0001"
    assert [need["type"] for need in entry["needs"]] == ["bed"]
    [blood_entry] = feed(doctor).json()
    assert [need["type"] for need in blood_entry["needs"]] == ["blood"]


@pytest.mark.parametrize("type_", ["xray", "BLOOD"])
def test_an_unknown_type_is_400(client_as, type_):
    res = feed(client_as(Role.DOCTOR), type_)

    assert res.status_code == 400
    assert "type" in res.json()


def test_the_feed_is_capped_at_the_100_most_urgent(client_as, make_hospital):
    hospital = make_hospital()
    for n in range(101):
        blood(make_case(hospital, f"EC-2026-{n:04d}", severity="low", minutes_ago=n + 1))
    blood(make_case(hospital, "EC-2026-9999", severity="critical", minutes_ago=1))

    listed = references(client_as(Role.DOCTOR))

    assert len(listed) == 100 and listed[0] == "EC-2026-9999"
    assert "EC-2026-0100" in listed  # oldest low cases stay: they have waited longest
    assert "EC-2026-0000" not in listed  # the newest low case is the one left out


# ── What each entry carries ─────────────────────────────────────────────────────────────────────


def test_entries_carry_no_patient_data_and_no_author_or_timeline(client_as, make_hospital):
    case = make_case(make_hospital(), "EC-2026-0001", patient_ref="Bay 4")
    blood(case)

    res = feed(client_as(Role.BLOOD_BANK))

    assert set(res.json()[0]) == ENTRY_KEYS
    assert set(res.json()[0]["needs"][0]) == BLOOD_KEYS
    assert "Bay 4" not in res.content.decode()


def test_each_entry_gives_its_needs_with_quantity_and_fulfilled(client_as, make_hospital):
    case = make_case(make_hospital(), "EC-2026-0001", status="matching")
    blood(case, group="A+", component="plasma", quantity=4, fulfilled=1)

    [entry] = feed(client_as(Role.BLOOD_BANK)).json()

    assert entry["severity"] == "high" and entry["status"] == "matching"
    assert entry["createdAt"]
    assert entry["needs"] == [
        {"type": "blood", "group": "A+", "component": "plasma", "quantity": 4, "fulfilled": 1}
    ]


# ── Who can read it ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", [Role.ADMIN, Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST])
def test_every_staff_role_can_read_the_feed(client_as, role):
    assert feed(client_as(role)).status_code == 200


def test_patients_and_signed_out_users_get_403(client_as, api):
    assert feed(client_as(Role.PATIENT)).status_code == 403
    assert feed(api).status_code == 403


# ── Escalation and cost ─────────────────────────────────────────────────────────────────────────


def test_reading_the_feed_runs_the_escalation_sweep(client_as, make_hospital):
    """A critical open request at another hospital, 45 minutes old, is escalated before the feed is built."""
    there = make_hospital(name="There")
    case = make_case(there, "EC-2026-0001", severity="critical", minutes_ago=45)
    blood(case)

    [entry] = feed(client_as(Role.BLOOD_BANK)).json()

    assert entry["status"] == "escalated"
    assert RequestStatusChange.objects.filter(request=case, action="escalate").exists()


def test_the_feed_query_count_does_not_grow_with_the_cases(
    client_as, make_hospital, django_assert_max_num_queries
):
    hospital = make_hospital()
    bank = client_as(Role.BLOOD_BANK, hospital=hospital)

    def count():
        with CaptureQueriesContext(connection) as context:
            assert feed(bank).status_code == 200
        return len(context.captured_queries)

    for n in range(2):
        blood(make_case(hospital, f"EC-2026-{n:04d}"), group="A+", quantity=n + 1)
    small = count()

    for n in range(2, 8):
        case = make_case(hospital, f"EC-2026-{n:04d}")
        blood(case, group="A+")
        blood(case, group="B-", component="platelets")
        bed(case)
    with django_assert_max_num_queries(3):  # the sweep's check, the cases with their hospitals, their needs
        big = count()

    assert big == small
