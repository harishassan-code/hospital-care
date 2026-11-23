"""Specialists in the API (B16, stories #61 and #62): every endpoint for every role, hospital scoping on
writes, validation, the filters, the conflict and not-found answers, and the audit trail. Windows that the
tests build from objects sit relative to the real clock. Typed input uses 2099, out of the clock's reach."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.specialists.models import OnCallWindow, Specialist

pytestmark = pytest.mark.django_db

STAFF = [Role.ADMIN, Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST]
VIEW_ONLY = [Role.DOCTOR, Role.BLOOD_BANK, Role.PHARMACIST]
BODY = {"name": "Dr. Ayesha Khan", "specialty": "Cardiology"}


def hours(n: float) -> datetime:
    """A moment `n` hours from the real clock now."""
    return timezone.now() + timedelta(hours=n)


def make(hospital, name, specialty="Cardiology", **extra) -> Specialist:
    return Specialist.objects.create(hospital=hospital, name=name, specialty=specialty, **extra)


def window(specialist, starts, ends) -> OnCallWindow:
    return OnCallWindow.objects.create(specialist=specialist, starts_at=starts, ends_at=ends)


def names_of(response) -> list[str]:
    return [row["name"] for row in response.json()]


class TestList:
    @pytest.mark.parametrize("role", STAFF)
    def test_every_staff_role_reads_the_whole_network(self, client_as, make_hospital, role):
        make(make_hospital("Here"), "Dr. Here")
        make(make_hospital("There"), "Dr. There")
        assert sorted(names_of(client_as(role).get(reverse("specialist-list")))) == ["Dr. Here", "Dr. There"]

    def test_a_patient_cannot_read_the_list(self, client_as):
        assert client_as(Role.PATIENT).get(reverse("specialist-list")).status_code == 403

    def test_each_row_says_whether_the_specialist_is_on_call_and_until_when(self, client_as, make_hospital):
        seaview = make_hospital("Seaview")
        on = make(seaview, "Dr. On")
        covering = window(on, hours(-1), hours(2))
        make(seaview, "Dr. Off")
        rows = {row["name"]: row for row in client_as(Role.DOCTOR).get(reverse("specialist-list")).json()}
        assert rows["Dr. On"]["onCallNow"] is True
        assert datetime.fromisoformat(rows["Dr. On"]["onCallUntil"]) == covering.ends_at
        assert rows["Dr. On"]["onCallUntil"].endswith("+05:00")  # the hospital's offset, not the viewer's
        assert rows["Dr. On"]["hospital"] == {"id": seaview.pk, "name": "Seaview"}
        assert rows["Dr. Off"]["onCallNow"] is False and rows["Dr. Off"]["onCallUntil"] is None

    def test_available_now_keeps_only_those_on_call_at_the_request(self, client_as, make_hospital):
        seaview = make_hospital("Seaview")
        window(make(seaview, "Dr. Now"), hours(-1), hours(2))
        window(make(seaview, "Dr. Later"), hours(3), hours(6))
        window(make(seaview, "Dr. Ended"), hours(-6), hours(-2))
        window(make(seaview, "Dr. Off duty", is_active=False), hours(-1), hours(2))
        url = reverse("specialist-list")
        client = client_as(Role.NURSE)
        assert names_of(client.get(url, {"availableNow": "true"})) == ["Dr. Now"]
        assert len(client.get(url).json()) == 4  # without the filter, everyone; deactivated profiles too
        assert len(client.get(url, {"availableNow": "false"}).json()) == 4

    def test_a_deactivated_profile_stays_in_the_list_marked(self, client_as, make_hospital):
        make(make_hospital("Seaview"), "Dr. Retired", is_active=False)
        (row,) = client_as(Role.DOCTOR).get(reverse("specialist-list")).json()
        assert row["name"] == "Dr. Retired" and row["isActive"] is False and row["onCallNow"] is False

    def test_filters_by_hospital_and_by_specialty_and_both(self, client_as, make_hospital):
        seaview, northside = make_hospital("Seaview"), make_hospital("Northside")
        make(seaview, "Dr. A", "Cardiology")
        make(seaview, "Dr. B", "Paediatrics")
        make(northside, "Dr. C", "cardiology")
        client, url = client_as(Role.ADMIN), reverse("specialist-list")
        assert sorted(names_of(client.get(url, {"hospital": seaview.pk}))) == ["Dr. A", "Dr. B"]
        assert sorted(names_of(client.get(url, {"specialty": "CARDIOLOGY"}))) == ["Dr. A", "Dr. C"]
        assert names_of(client.get(url, {"hospital": seaview.pk, "specialty": "cardiology"})) == ["Dr. A"]
        assert client.get(url, {"hospital": 999_999}).json() == []

    def test_rows_are_ordered_by_hospital_then_specialty_then_name(self, client_as, make_hospital):
        seaview, northside = make_hospital("Seaview"), make_hospital("Northside")
        make(seaview, "Dr. Z", "Cardiology")
        make(seaview, "Dr. A", "Paediatrics")
        make(northside, "Dr. M", "Neonatology")
        assert names_of(client_as(Role.DOCTOR).get(reverse("specialist-list"))) == ["Dr. M", "Dr. Z", "Dr. A"]

    def test_a_bad_filter_is_a_400_naming_the_field(self, client_as):
        res = client_as(Role.ADMIN).get(reverse("specialist-list"), {"hospital": "seaview"})
        assert res.status_code == 400 and "hospital" in res.json()

    def test_the_list_costs_the_same_queries_however_many_specialists(self, client_as, make_hospital):
        seaview = make_hospital("Seaview")
        client, url = client_as(Role.DOCTOR), reverse("specialist-list")

        def queries() -> int:
            with CaptureQueriesContext(connection) as captured:
                client.get(url)
            return len(captured)

        window(make(seaview, "Dr. 1"), hours(-1), hours(2))
        few = queries()
        for index in range(2, 12):
            window(make(seaview, f"Dr. {index}"), hours(-1), hours(2))
        assert queries() == few


class TestCreate:
    def test_admin_lists_a_specialist_at_any_hospital(self, client_as, make_hospital):
        city = make_hospital("City")
        res = client_as(Role.ADMIN).post(
            reverse("specialist-list"), {**BODY, "hospitalId": city.pk}, format="json"
        )
        assert res.status_code == 201
        assert res.json()["hospital"] == {"id": city.pk, "name": "City"}
        assert res.json()["onCall"] == [] and res.json()["onCallNow"] is False
        assert AuditLog.objects.filter(action="specialist.created", target_id=res.json()["id"]).exists()

    def test_nurse_lists_a_specialist_at_her_own_hospital(self, client_as, make_hospital):
        here = make_hospital("Here")
        res = client_as(Role.NURSE, hospital=here).post(
            reverse("specialist-list"), {**BODY, "hospitalId": here.pk}, format="json"
        )
        assert res.status_code == 201

    def test_nurse_cannot_list_at_another_hospital(self, client_as, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        res = client_as(Role.NURSE, hospital=here).post(
            reverse("specialist-list"), {**BODY, "hospitalId": there.pk}, format="json"
        )
        assert res.status_code == 403
        assert not Specialist.objects.exists()

    @pytest.mark.parametrize("role", [*VIEW_ONLY, Role.PATIENT])
    def test_roles_that_only_view_cannot_list(self, client_as, make_hospital, role):
        here = make_hospital("Here")
        res = client_as(role, hospital=here).post(
            reverse("specialist-list"), {**BODY, "hospitalId": here.pk}, format="json"
        )
        assert res.status_code == 403
        assert not Specialist.objects.exists()

    @pytest.mark.parametrize(
        ("change", "field"),
        [
            ({"name": ""}, "name"),
            ({"name": "x" * 151}, "name"),
            ({"specialty": "   "}, "specialty"),
            ({"hospitalId": 999_999}, "hospitalId"),
            ({"hospitalId": "seaview"}, "hospitalId"),
        ],
    )
    def test_invalid_input_is_a_400_naming_the_field(self, client_as, make_hospital, change, field):
        here = make_hospital("Here")
        body = {**BODY, "hospitalId": here.pk, **change}
        res = client_as(Role.ADMIN).post(reverse("specialist-list"), body, format="json")
        assert res.status_code == 400 and field in res.json()
        assert not Specialist.objects.exists()

    def test_a_deactivated_hospital_takes_no_new_specialists(self, client_as, make_hospital):
        closed = make_hospital("Closed", is_active=False)
        res = client_as(Role.ADMIN).post(
            reverse("specialist-list"), {**BODY, "hospitalId": closed.pk}, format="json"
        )
        assert res.status_code == 400 and "hospitalId" in res.json()

    def test_a_name_the_hospital_already_has_is_a_400(self, client_as, make_hospital):
        here = make_hospital("Here")
        make(here, "Dr. Ayesha Khan")
        res = client_as(Role.ADMIN).post(
            reverse("specialist-list"),
            {**BODY, "name": "dr. ayesha khan", "hospitalId": here.pk},
            format="json",
        )
        assert res.status_code == 400 and "name" in res.json()


class TestDetail:
    def test_shows_only_windows_that_have_not_ended_in_start_order(self, client_as, make_hospital):
        doctor = make(make_hospital("Seaview"), "Dr. A")
        window(doctor, hours(-6), hours(-2))
        later = window(doctor, hours(30), hours(38))
        now_ = window(doctor, hours(-1), hours(2))
        res = client_as(Role.NURSE).get(reverse("specialist-detail", args=[doctor.pk]))
        assert res.status_code == 200
        assert [w["id"] for w in res.json()["onCall"]] == [now_.pk, later.pk]
        assert res.json()["onCallNow"] is True

    @pytest.mark.parametrize("role", STAFF)
    def test_every_staff_role_reads_one(self, client_as, make_hospital, role):
        doctor = make(make_hospital("Seaview"), "Dr. A")
        assert client_as(role).get(reverse("specialist-detail", args=[doctor.pk])).status_code == 200

    def test_a_patient_cannot_read_one(self, client_as, make_hospital):
        doctor = make(make_hospital("Seaview"), "Dr. A")
        assert client_as(Role.PATIENT).get(reverse("specialist-detail", args=[doctor.pk])).status_code == 403

    def test_an_unknown_specialist_is_404(self, client_as):
        assert client_as(Role.ADMIN).get(reverse("specialist-detail", args=[999_999])).status_code == 404

    def test_nurse_edits_a_profile_at_her_own_hospital_and_it_is_audited(self, client_as, make_hospital):
        here = make_hospital("Here")
        doctor = make(here, "Dr. A")
        res = client_as(Role.NURSE, hospital=here).patch(
            reverse("specialist-detail", args=[doctor.pk]), {"specialty": "Heart surgery"}, format="json"
        )
        assert res.status_code == 200 and res.json()["specialty"] == "Heart surgery"
        entry = AuditLog.objects.get(action="specialist.updated")
        assert (entry.before, entry.after) == ({"specialty": "Cardiology"}, {"specialty": "Heart surgery"})

    def test_nurse_cannot_edit_another_hospitals_profile_and_nothing_changes(self, client_as, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        doctor = make(there, "Dr. A")
        res = client_as(Role.NURSE, hospital=here).patch(
            reverse("specialist-detail", args=[doctor.pk]), {"isActive": False}, format="json"
        )
        assert res.status_code == 403
        doctor.refresh_from_db()
        assert doctor.is_active is True

    @pytest.mark.parametrize("role", VIEW_ONLY)
    def test_roles_that_only_view_cannot_edit_even_at_their_hospital(self, client_as, make_hospital, role):
        here = make_hospital("Here")
        doctor = make(here, "Dr. A")
        res = client_as(role, hospital=here).patch(
            reverse("specialist-detail", args=[doctor.pk]), {"isActive": False}, format="json"
        )
        assert res.status_code == 403

    def test_admin_edits_any_hospital(self, client_as, make_hospital):
        doctor = make(make_hospital("There"), "Dr. A")
        res = client_as(Role.ADMIN).patch(
            reverse("specialist-detail", args=[doctor.pk]), {"name": "Dr. B"}, format="json"
        )
        assert res.status_code == 200 and res.json()["name"] == "Dr. B"

    def test_deactivating_takes_a_specialist_off_call_at_once(self, client_as, make_hospital):
        seaview = make_hospital("Seaview")
        doctor = make(seaview, "Dr. A")
        window(doctor, hours(-1), hours(2))
        res = client_as(Role.ADMIN).patch(
            reverse("specialist-detail", args=[doctor.pk]), {"isActive": False}, format="json"
        )
        assert res.json()["isActive"] is False
        assert res.json()["onCallNow"] is False and res.json()["onCallUntil"] is None

    @pytest.mark.parametrize(
        ("body", "field"),
        [({"name": ""}, "name"), ({"specialty": ""}, "specialty"), ({"isActive": "maybe"}, "isActive")],
    )
    def test_invalid_edits_are_400_naming_the_field(self, client_as, make_hospital, body, field):
        doctor = make(make_hospital("Seaview"), "Dr. A")
        res = client_as(Role.ADMIN).patch(reverse("specialist-detail", args=[doctor.pk]), body, format="json")
        assert res.status_code == 400 and field in res.json()

    def test_a_name_taken_at_the_hospital_is_a_400(self, client_as, make_hospital):
        seaview = make_hospital("Seaview")
        make(seaview, "Dr. A")
        other = make(seaview, "Dr. B")
        res = client_as(Role.ADMIN).patch(
            reverse("specialist-detail", args=[other.pk]), {"name": "dr. a"}, format="json"
        )
        assert res.status_code == 400 and "name" in res.json()

    def test_an_unknown_specialist_is_404_on_edit(self, client_as):
        res = client_as(Role.ADMIN).patch(
            reverse("specialist-detail", args=[999_999]), {"isActive": False}, format="json"
        )
        assert res.status_code == 404


class TestOnCallWindows:
    FAR = ("2099-01-15T20:00+05:00", "2099-01-16T08:00+05:00")

    def add(self, client, pk, starts, ends):
        return client.post(
            reverse("specialist-on-call", args=[pk]), {"startsAt": starts, "endsAt": ends}, format="json"
        )

    def test_nurse_adds_a_window_at_her_hospital_and_it_is_stored_in_utc(self, client_as, make_hospital):
        here = make_hospital("Here")
        doctor = make(here, "Dr. A")
        res = self.add(client_as(Role.NURSE, hospital=here), doctor.pk, *self.FAR)
        assert res.status_code == 201
        assert res.json()["startsAt"] == "2099-01-15T20:00:00+05:00"
        assert res.json()["endsAt"] == "2099-01-16T08:00:00+05:00"
        assert OnCallWindow.objects.get().starts_at == datetime(2099, 1, 15, 15, 0, tzinfo=UTC)

    def test_a_window_must_end_after_it_starts(self, client_as, make_hospital):
        doctor = make(make_hospital("Here"), "Dr. A")
        res = self.add(client_as(Role.ADMIN), doctor.pk, "2099-01-15T20:00+05:00", "2099-01-15T20:00+05:00")
        assert res.status_code == 400 and "endsAt" in res.json()

    def test_a_window_that_has_already_ended_is_a_400(self, client_as, make_hospital):
        doctor = make(make_hospital("Here"), "Dr. A")
        res = self.add(client_as(Role.ADMIN), doctor.pk, "2000-01-15T08:00+05:00", "2000-01-15T20:00+05:00")
        assert res.status_code == 400 and "endsAt" in res.json()

    def test_an_overlapping_window_is_a_400_on_startsAt(self, client_as, make_hospital):
        admin = client_as(Role.ADMIN)
        doctor = make(make_hospital("Here"), "Dr. A")
        self.add(admin, doctor.pk, *self.FAR)
        res = self.add(admin, doctor.pk, "2099-01-15T18:00+05:00", "2099-01-15T22:00+05:00")
        assert res.status_code == 400 and "startsAt" in res.json()
        assert OnCallWindow.objects.count() == 1

    def test_a_window_that_starts_as_another_ends_is_allowed(self, client_as, make_hospital):
        admin = client_as(Role.ADMIN)
        doctor = make(make_hospital("Here"), "Dr. A")
        self.add(admin, doctor.pk, *self.FAR)
        res = self.add(admin, doctor.pk, "2099-01-16T08:00+05:00", "2099-01-16T12:00+05:00")
        assert res.status_code == 201

    def test_unreadable_times_are_a_400_on_the_field(self, client_as, make_hospital):
        doctor = make(make_hospital("Here"), "Dr. A")
        res = self.add(client_as(Role.ADMIN), doctor.pk, "soon", "2099-01-16T08:00+05:00")
        assert res.status_code == 400 and "startsAt" in res.json()

    def test_a_nurse_at_another_hospital_cannot_add_a_window(self, client_as, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        doctor = make(there, "Dr. A")
        res = self.add(client_as(Role.NURSE, hospital=here), doctor.pk, *self.FAR)
        assert res.status_code == 403
        assert not OnCallWindow.objects.exists()

    @pytest.mark.parametrize("role", VIEW_ONLY)
    def test_roles_that_only_view_cannot_add_windows(self, client_as, make_hospital, role):
        here = make_hospital("Here")
        doctor = make(here, "Dr. A")
        assert self.add(client_as(role, hospital=here), doctor.pk, *self.FAR).status_code == 403

    def test_an_unknown_specialist_is_404_on_add(self, client_as):
        assert self.add(client_as(Role.ADMIN), 999_999, *self.FAR).status_code == 404

    def test_removing_a_window_that_has_not_started_is_audited_and_the_detail_forgets_it(
        self, client_as, make_hospital
    ):
        doctor = make(make_hospital("Here"), "Dr. A")
        later = window(doctor, hours(30), hours(38))
        client = client_as(Role.ADMIN)
        res = client.delete(reverse("specialist-on-call-detail", args=[doctor.pk, later.pk]))
        assert res.status_code == 204
        assert not OnCallWindow.objects.filter(pk=later.pk).exists()
        assert AuditLog.objects.filter(action="on_call.deleted", target_id=str(later.pk)).exists()
        detail = client.get(reverse("specialist-detail", args=[doctor.pk]))
        assert detail.json()["onCall"] == []

    def test_a_window_that_has_started_cannot_be_removed(self, client_as, make_hospital):
        doctor = make(make_hospital("Here"), "Dr. A")
        current = window(doctor, hours(-1), hours(2))
        res = client_as(Role.ADMIN).delete(reverse("specialist-on-call-detail", args=[doctor.pk, current.pk]))
        assert res.status_code == 409 and "detail" in res.json()
        assert OnCallWindow.objects.filter(pk=current.pk).exists()

    def test_a_window_is_reached_only_through_its_own_specialist(self, client_as, make_hospital):
        seaview = make_hospital("Seaview")
        mine, theirs = make(seaview, "Dr. A"), make(seaview, "Dr. B")
        their_window = window(theirs, hours(30), hours(38))
        res = client_as(Role.ADMIN).delete(
            reverse("specialist-on-call-detail", args=[mine.pk, their_window.pk])
        )
        assert res.status_code == 404
        assert OnCallWindow.objects.filter(pk=their_window.pk).exists()

    def test_a_nurse_cannot_remove_another_hospitals_window(self, client_as, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        doctor = make(there, "Dr. A")
        their_window = window(doctor, hours(30), hours(38))
        res = client_as(Role.NURSE, hospital=here).delete(
            reverse("specialist-on-call-detail", args=[doctor.pk, their_window.pk])
        )
        assert res.status_code == 403
        assert OnCallWindow.objects.filter(pk=their_window.pk).exists()

    @pytest.mark.parametrize("role", VIEW_ONLY)
    def test_roles_that_only_view_cannot_remove_windows(self, client_as, make_hospital, role):
        here = make_hospital("Here")
        doctor = make(here, "Dr. A")
        later = window(doctor, hours(30), hours(38))
        res = client_as(role, hospital=here).delete(
            reverse("specialist-on-call-detail", args=[doctor.pk, later.pk])
        )
        assert res.status_code == 403

    def test_an_unknown_window_is_404(self, client_as, make_hospital):
        doctor = make(make_hospital("Here"), "Dr. A")
        res = client_as(Role.ADMIN).delete(reverse("specialist-on-call-detail", args=[doctor.pk, 999_999]))
        assert res.status_code == 404


def test_the_public_hospital_page_shows_specialties_but_not_names(api, make_hospital):
    seaview = make_hospital("Seaview")
    window(make(seaview, "Dr. Staff Only"), hours(-1), hours(2))
    res = api.get(reverse("public-hospital", args=[seaview.pk]))
    assert res.status_code == 200
    assert "Staff Only" not in res.content.decode()
