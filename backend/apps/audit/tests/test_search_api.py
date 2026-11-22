"""B10 (#56): audit search: each filter, paging bounds, order, response shape, query count, access."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.audit.services import record

from .helpers import stamp

pytestmark = pytest.mark.django_db

URL = "/api/audit/entries/"


@pytest.fixture
def admin(client_as):
    return client_as(Role.ADMIN)


def ids(response) -> list[int]:
    return [row["id"] for row in response.json()["results"]]


def test_actor_matches_the_email_exactly_and_ignoring_case(admin):
    mine = stamp(actor_email="hina.javed@example.com")
    stamp(actor_email="hina.javed@example.com.pk")
    assert ids(admin.get(URL, {"actor": "HINA.Javed@example.COM"})) == [mine.id]


def test_actor_still_matches_after_the_account_is_deleted(admin, make_user):
    nurse = make_user(Role.NURSE)
    entry = record(nurse, "user.updated", nurse)
    nurse.delete()
    assert ids(admin.get(URL, {"actor": "nurse@example.com"})) == [entry.id]


def test_action_is_a_starts_with_match(admin):
    family = stamp(action="bed.status_changed")
    other = stamp(action="bed.reserved")
    stamp(action="bedding.changed")
    assert ids(admin.get(URL, {"action": "bed."})) == [other.id, family.id]
    assert ids(admin.get(URL, {"action": "bed.status_changed"})) == [family.id]
    assert ids(admin.get(URL, {"action": "status_changed"})) == []


def test_target_type_and_id_show_one_objects_history(admin):
    hospital = stamp(target_type="hospitals.hospital", target_id="3")
    stamp(target_type="hospitals.hospital", target_id="30")
    stamp(target_type="beds.bed", target_id="3")
    assert ids(admin.get(URL, {"targetType": "hospitals.hospital", "targetId": "3"})) == [hospital.id]
    assert len(ids(admin.get(URL, {"targetType": "hospitals.hospital"}))) == 2


def test_dates_are_whole_days_in_karachi_time(admin):
    # Karachi is UTC+5, so 19:00 UTC is midnight at the start of the next day there.
    before_midnight = stamp("2026-11-17T18:59:59+00:00")  # 17 Nov 23:59:59 PKT
    first = stamp("2026-11-17T19:00:00+00:00")  # 18 Nov 00:00:00 PKT
    last = stamp("2026-11-18T18:59:59+00:00")  # 18 Nov 23:59:59 PKT
    after = stamp("2026-11-18T19:00:00+00:00")  # 19 Nov 00:00:00 PKT

    assert ids(admin.get(URL, {"from": "2026-11-18", "to": "2026-11-18"})) == [last.id, first.id]
    assert ids(admin.get(URL, {"to": "2026-11-17"})) == [before_midnight.id]
    assert ids(admin.get(URL, {"from": "2026-11-19"})) == [after.id]


@pytest.mark.parametrize(
    "params",
    [
        {"from": "18-11-2026"},
        {"from": "20261118"},
        {"to": "2026-02-30"},
        {"from": "2026-11-18", "to": "2026-11-17"},
        {"from": "0001-01-01"},
        {"to": "9999-12-31"},
    ],
)
def test_a_date_that_does_not_parse_or_a_range_backwards_is_400(admin, params):
    response = admin.get(URL, params)
    assert response.status_code == 400
    assert "detail" in response.json()


def test_text_search_covers_five_fields_and_ignores_case(admin):
    by_email = stamp(actor_email="NEEDLE-user@example.com")
    by_action = stamp(action="needle.done")
    by_repr = stamp(target_repr="Needle bed")
    by_id = stamp(target_id="needle-7")
    by_reason = stamp(reason="Needle reason")
    hidden = stamp(before={"status": "needle"}, after={"status": "needle"})
    found = ids(admin.get(URL, {"q": "needle"}))
    assert set(found) == {by_email.id, by_action.id, by_repr.id, by_id.id, by_reason.id}
    assert hidden.id not in found


def test_filters_combine_with_and(admin):
    hit = stamp(actor_email="a@example.com", action="bed.reserved", target_type="beds.bed")
    stamp(actor_email="b@example.com", action="bed.reserved", target_type="beds.bed")
    stamp(actor_email="a@example.com", action="hospital.updated", target_type="beds.bed")
    params = {"actor": "a@example.com", "action": "bed.", "targetType": "beds.bed"}
    assert ids(admin.get(URL, params)) == [hit.id]


def test_newest_first_with_ties_broken_by_id(admin):
    early = stamp("2026-11-18T09:00:00+00:00")
    tie_a = stamp("2026-11-18T10:00:00+00:00")
    tie_b = stamp("2026-11-18T10:00:00+00:00")
    assert ids(admin.get(URL)) == [tie_b.id, tie_a.id, early.id]


@pytest.fixture
def sixty(admin):
    for number in range(60):
        stamp(reason=f"row {number}")


def test_paging_defaults_to_fifty_and_walks_the_set(admin, sixty):
    first = admin.get(URL).json()
    assert (first["count"], first["limit"], first["offset"], len(first["results"])) == (60, 50, 0, 50)
    second = admin.get(URL, {"offset": 50}).json()
    assert (second["count"], second["offset"], len(second["results"])) == (60, 50, 10)
    everything = ids(admin.get(URL, {"limit": 200}))
    assert ids(admin.get(URL, {"limit": 5, "offset": 10})) == everything[10:15]


def test_a_limit_above_the_maximum_is_cut_to_200(admin, sixty):
    body = admin.get(URL, {"limit": 500}).json()
    assert body["limit"] == 200 and len(body["results"]) == 60


def test_a_zero_limit_returns_no_rows_but_the_count(admin, sixty):
    body = admin.get(URL, {"limit": 0}).json()
    assert body["count"] == 60 and body["results"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "-1"},
        {"limit": "abc"},
        {"limit": "1.5"},
        {"offset": "-3"},
        {"offset": "x"},
        {"offset": "1234567890"},
    ],
)
def test_paging_values_that_are_not_whole_numbers_are_400(admin, params):
    assert admin.get(URL, params).status_code == 400


def test_each_row_has_the_camel_case_fields_and_utc_times(admin):
    stamp(
        "2026-11-18T19:00:00+00:00",
        target_type="hospitals.hospital",
        target_id="3",
        target_repr="CityCare",
        reason="Renamed",
        before={"name": "Old"},
        after=None,
    )
    body = admin.get(URL).json()
    assert set(body) == {"count", "limit", "offset", "results"}
    row = body["results"][0]
    assert set(row) == {
        "id",
        "at",
        "actorEmail",
        "action",
        "targetType",
        "targetId",
        "targetRepr",
        "reason",
        "before",
        "after",
    }
    assert row["at"] == "2026-11-18T19:00:00Z"
    assert (row["actorEmail"], row["targetType"], row["targetId"], row["targetRepr"]) == (
        "admin@example.com",
        "hospitals.hospital",
        "3",
        "CityCare",
    )
    assert row["before"] == {"name": "Old"} and row["after"] is None


def test_a_page_runs_two_queries_however_many_rows_it_holds(admin):
    stamp()
    with CaptureQueriesContext(connection) as one_row:
        admin.get(URL)
    for number in range(40):
        stamp(reason=f"row {number}")
    with CaptureQueriesContext(connection) as many_rows:
        admin.get(URL)
    assert len(one_row) == len(many_rows) == 2


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_only_admins_can_search(client_as, role):
    assert client_as(role).get(URL).status_code == 403


def test_signed_out_users_get_403(api):
    assert api.get(URL).status_code == 403


def test_a_superuser_reads_as_an_admin(api, make_user):
    api.force_authenticate(make_user(Role.NURSE, is_superuser=True))
    assert api.get(URL).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_answer_405(admin, method):
    assert getattr(admin, method)(URL, {}, format="json").status_code == 405
    assert AuditLog.objects.count() == 0
