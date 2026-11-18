"""B16 rules (stories #61 and #62): overlap, "available now" at the boundaries, overnight windows, who may
change what, and the audit trail. The clock is fixed, so nothing here depends on the real date."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.specialists import services
from apps.specialists.models import OnCallWindow, Specialist
from apps.specialists.services import SpecialistConflict, window_covering

pytestmark = pytest.mark.django_db

KARACHI = ZoneInfo("Asia/Karachi")
NOW = datetime(2030, 1, 15, 12, 0, tzinfo=KARACHI)
NAME = "Dr. Ayesha Khan"


def kt(day: int, hour: int, minute: int = 0) -> datetime:
    """A Karachi time on 15 January 2030, or on another day of that month."""
    return datetime(2030, 1, day, hour, minute, tzinfo=KARACHI)


def window(specialist, starts, ends) -> OnCallWindow:
    return OnCallWindow.objects.create(specialist=specialist, starts_at=starts, ends_at=ends)


def on_call_at(moment) -> set[str]:
    return set(Specialist.objects.available_at(moment).values_list("name", flat=True))


@pytest.fixture
def seaview(make_hospital):
    return make_hospital("Seaview")


@pytest.fixture
def cardiologist(seaview):
    return Specialist.objects.create(hospital=seaview, name=NAME, specialty="Cardiology")


@pytest.fixture
def admin(make_user):
    return make_user(Role.ADMIN)


class TestAvailableNow:
    def test_start_is_inclusive_and_end_is_exclusive(self, cardiologist):
        window(cardiologist, kt(15, 8), kt(15, 20))
        assert on_call_at(kt(15, 8)) == {NAME}
        assert on_call_at(kt(15, 19, 59)) == {NAME}
        assert on_call_at(kt(15, 20)) == set()
        assert on_call_at(kt(15, 7, 59)) == set()

    def test_overnight_window_runs_into_the_next_morning(self, cardiologist):
        window(cardiologist, kt(15, 20), kt(16, 8))
        assert on_call_at(kt(15, 23)) == {NAME}
        assert on_call_at(kt(16, 7, 59)) == {NAME}
        assert on_call_at(kt(16, 8)) == set()

    def test_windows_in_the_past_or_future_are_not_on_call(self, cardiologist):
        window(cardiologist, kt(14, 8), kt(14, 20))
        window(cardiologist, kt(16, 8), kt(16, 20))
        assert on_call_at(NOW) == set()

    def test_a_deactivated_specialist_is_never_on_call(self, cardiologist):
        window(cardiologist, kt(15, 8), kt(15, 20))
        cardiologist.is_active = False
        cardiologist.save()
        assert on_call_at(kt(15, 12)) == set()

    def test_karachi_times_are_stored_as_the_same_instant_in_utc(self, cardiologist):
        added = window(cardiologist, kt(15, 20), kt(16, 8))
        added.refresh_from_db()
        assert added.starts_at == datetime(2030, 1, 15, 15, 0, tzinfo=UTC)
        assert added.ends_at == datetime(2030, 1, 16, 3, 0, tzinfo=UTC)

    def test_the_answer_does_not_depend_on_the_viewers_zone(self, cardiologist):
        window(cardiologist, kt(15, 8), kt(15, 20))
        assert on_call_at(kt(15, 12)) == on_call_at((kt(15, 12)).astimezone(UTC)) == {NAME}

    def test_the_schedule_loads_only_windows_that_have_not_ended(self, cardiologist):
        window(cardiologist, kt(14, 8), kt(14, 20))
        current = window(cardiologist, kt(15, 8), kt(15, 20))
        upcoming = window(cardiologist, kt(16, 8), kt(16, 20))
        loaded = Specialist.objects.with_schedule(NOW).get(pk=cardiologist.pk)
        assert [w.pk for w in loaded.upcoming_windows] == [current.pk, upcoming.pk]
        assert window_covering(loaded, NOW).pk == current.pk
        assert window_covering(loaded, kt(15, 21)) is None


class TestAddingWindows:
    def add(self, specialist, starts, ends, actor, now=NOW):
        return services.add_on_call_window(
            specialist.pk, starts_at=starts, ends_at=ends, actor=actor, now=now
        )

    def test_a_window_must_end_after_it_starts(self, cardiologist, admin):
        with pytest.raises(ValidationError) as error:
            self.add(cardiologist, kt(15, 20), kt(15, 20), admin)
        assert "endsAt" in error.value.detail
        assert not OnCallWindow.objects.exists()

    def test_a_window_that_has_already_ended_is_refused(self, cardiologist, admin):
        with pytest.raises(ValidationError) as error:
            self.add(cardiologist, kt(14, 8), kt(14, 20), admin)
        assert "endsAt" in error.value.detail
        assert not OnCallWindow.objects.exists()

    def test_a_window_that_is_on_now_can_still_be_added(self, cardiologist, admin):
        assert self.add(cardiologist, kt(15, 8), kt(15, 20), admin).pk

    # The existing window is on 16 January, so every case is still in the future at NOW (15 January, noon).
    @pytest.mark.parametrize(
        ("starts", "ends"),
        [(kt(16, 6), kt(16, 9)), (kt(16, 18), kt(16, 22)), (kt(16, 9), kt(16, 10)), (kt(16, 6), kt(16, 22))],
        ids=["overlaps the start", "overlaps the end", "inside", "covers it"],
    )
    def test_an_overlapping_window_is_refused_on_its_start(self, cardiologist, admin, starts, ends):
        window(cardiologist, kt(16, 8), kt(16, 20))
        with pytest.raises(ValidationError) as error:
            self.add(cardiologist, starts, ends, admin)
        assert "startsAt" in error.value.detail
        assert OnCallWindow.objects.count() == 1

    def test_windows_that_only_touch_do_not_overlap(self, cardiologist, admin):
        window(cardiologist, kt(16, 8), kt(16, 20))
        self.add(cardiologist, kt(16, 20), kt(17, 8), admin)
        self.add(cardiologist, kt(16, 6), kt(16, 8), admin)
        assert OnCallWindow.objects.count() == 3

    def test_the_overlap_message_names_the_window_it_clashes_with(self, cardiologist, admin):
        window(cardiologist, kt(16, 8), kt(16, 20))
        with pytest.raises(ValidationError) as error:
            self.add(cardiologist, kt(16, 18), kt(16, 22), admin)
        assert str(error.value.detail["startsAt"][0]) == (
            "Overlaps an on-call window from 16 Jan 08:00 to 16 Jan 20:00."
        )

    def test_adding_a_window_is_audited(self, cardiologist, admin):
        added = self.add(cardiologist, kt(15, 8), kt(15, 20), admin)
        entry = AuditLog.objects.get(action="on_call.created")
        assert entry.target_type == "specialists.oncallwindow"
        assert entry.target_id == str(added.pk)
        assert entry.actor_email == admin.email
        assert entry.after == {"startsAt": "2030-01-15T08:00:00+05:00", "endsAt": "2030-01-15T20:00:00+05:00"}

    def test_an_unknown_specialist_is_not_found(self, admin):
        with pytest.raises(Http404):
            services.add_on_call_window(999, starts_at=kt(15, 8), ends_at=kt(15, 20), actor=admin, now=NOW)


class TestRemovingWindows:
    def test_a_window_that_has_not_started_is_removed_and_audited(self, cardiologist, admin):
        later = window(cardiologist, kt(16, 8), kt(16, 20))
        services.remove_on_call_window(cardiologist.pk, later.pk, actor=admin, now=NOW)
        assert not OnCallWindow.objects.filter(pk=later.pk).exists()
        entry = AuditLog.objects.get(action="on_call.deleted")
        assert entry.before == {
            "startsAt": "2030-01-16T08:00:00+05:00",
            "endsAt": "2030-01-16T20:00:00+05:00",
        }
        assert entry.after is None

    def test_a_window_that_has_started_stays_as_history(self, cardiologist, admin):
        current = window(cardiologist, kt(15, 8), kt(15, 20))
        with pytest.raises(SpecialistConflict):
            services.remove_on_call_window(cardiologist.pk, current.pk, actor=admin, now=NOW)
        assert OnCallWindow.objects.filter(pk=current.pk).exists()
        assert not AuditLog.objects.filter(action="on_call.deleted").exists()

    def test_a_window_can_only_be_removed_through_its_own_specialist(self, cardiologist, seaview, admin):
        other = Specialist.objects.create(hospital=seaview, name="Dr. Omar Sheikh", specialty="Cardiology")
        theirs = window(other, kt(16, 8), kt(16, 20))
        with pytest.raises(Http404):
            services.remove_on_call_window(cardiologist.pk, theirs.pk, actor=admin, now=NOW)
        assert OnCallWindow.objects.filter(pk=theirs.pk).exists()


class TestProfiles:
    def test_creating_a_profile_is_audited(self, seaview, admin):
        specialist = services.create_specialist(seaview, name=NAME, specialty="Cardiology", actor=admin)
        entry = AuditLog.objects.get(action="specialist.created")
        assert entry.target_id == str(specialist.pk)
        assert entry.after == {"name": NAME, "specialty": "Cardiology", "hospital": "Seaview"}

    def test_names_are_unique_per_hospital_in_any_case(self, seaview, make_hospital, admin, cardiologist):
        with pytest.raises(ValidationError) as error:
            services.create_specialist(seaview, name="dr. AYESHA khan", specialty="ENT", actor=admin)
        assert "name" in error.value.detail
        services.create_specialist(make_hospital("City"), name=NAME, specialty="Cardiology", actor=admin)
        assert Specialist.objects.count() == 2

    def test_a_deactivated_profile_is_kept(self, cardiologist, admin):
        services.update_specialist(cardiologist.pk, {"isActive": False}, actor=admin)
        cardiologist.refresh_from_db()
        assert cardiologist.is_active is False
        assert Specialist.objects.count() == 1

    def test_an_update_audits_only_the_fields_that_changed(self, cardiologist, admin):
        services.update_specialist(cardiologist.pk, {"name": NAME, "specialty": "Heart surgery"}, actor=admin)
        entry = AuditLog.objects.get(action="specialist.updated")
        assert entry.before == {"specialty": "Cardiology"}
        assert entry.after == {"specialty": "Heart surgery"}

    def test_an_unchanged_update_writes_nothing(self, cardiologist, admin):
        services.update_specialist(cardiologist.pk, {"name": NAME, "isActive": True}, actor=admin)
        assert not AuditLog.objects.filter(action="specialist.updated").exists()

    def test_renaming_to_a_name_the_hospital_already_has_is_refused(self, seaview, cardiologist, admin):
        other = Specialist.objects.create(hospital=seaview, name="Dr. Omar Sheikh", specialty="Cardiology")
        with pytest.raises(ValidationError):
            services.update_specialist(other.pk, {"name": "dr. ayesha KHAN"}, actor=admin)
        other.refresh_from_db()
        assert other.name == "Dr. Omar Sheikh"


class TestWhoMayChange:
    def test_a_nurse_changes_only_her_own_hospital(self, make_user, make_hospital, seaview):
        city = make_hospital("City")
        nurse = make_user(Role.NURSE, hospital=seaview)
        services.create_specialist(seaview, name=NAME, specialty="Cardiology", actor=nurse)
        with pytest.raises(PermissionDenied):
            services.create_specialist(city, name="Dr. Omar Sheikh", specialty="Cardiology", actor=nurse)
        theirs = Specialist.objects.create(hospital=city, name="Dr. Sana Malik", specialty="Paediatrics")
        with pytest.raises(PermissionDenied):
            services.update_specialist(theirs.pk, {"isActive": False}, actor=nurse)
        with pytest.raises(PermissionDenied):
            services.add_on_call_window(
                theirs.pk, starts_at=kt(15, 8), ends_at=kt(15, 20), actor=nurse, now=NOW
            )
        theirs.refresh_from_db()
        assert theirs.is_active and not OnCallWindow.objects.exists()

    def test_an_admin_changes_any_hospital(self, make_user, make_hospital, seaview, admin):
        city = make_hospital("City")
        theirs = Specialist.objects.create(hospital=city, name="Dr. Sana Malik", specialty="Paediatrics")
        services.update_specialist(theirs.pk, {"isActive": False}, actor=admin)
        services.add_on_call_window(theirs.pk, starts_at=kt(15, 8), ends_at=kt(15, 20), actor=admin, now=NOW)
        theirs.refresh_from_db()
        assert theirs.is_active is False and OnCallWindow.objects.filter(specialist=theirs).exists()

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.BLOOD_BANK, Role.PHARMACIST])
    def test_roles_that_only_view_cannot_change_even_at_their_hospital(
        self, make_user, seaview, cardiologist, role
    ):
        user = make_user(role, hospital=seaview)
        with pytest.raises(PermissionDenied):
            services.create_specialist(seaview, name="Dr. Omar Sheikh", specialty="Cardiology", actor=user)
        with pytest.raises(PermissionDenied):
            services.update_specialist(cardiologist.pk, {"isActive": False}, actor=user)
        with pytest.raises(PermissionDenied):
            services.add_on_call_window(
                cardiologist.pk, starts_at=kt(15, 8), ends_at=kt(15, 20), actor=user, now=NOW
            )
        assert Specialist.objects.count() == 1 and not OnCallWindow.objects.exists()

    def test_a_nurse_removes_windows_only_at_her_hospital(self, make_user, make_hospital, seaview):
        city = make_hospital("City")
        nurse = make_user(Role.NURSE, hospital=seaview)
        theirs = Specialist.objects.create(hospital=city, name="Dr. Sana Malik", specialty="Paediatrics")
        their_window = window(theirs, kt(16, 8), kt(16, 20))
        with pytest.raises(PermissionDenied):
            services.remove_on_call_window(theirs.pk, their_window.pk, actor=nurse, now=NOW)
        assert OnCallWindow.objects.filter(pk=their_window.pk).exists()


class TestDatabaseBackstops:
    def test_the_database_refuses_a_window_that_does_not_end_after_it_starts(self, cardiologist):
        with pytest.raises(IntegrityError), transaction.atomic():
            OnCallWindow.objects.create(specialist=cardiologist, starts_at=kt(15, 20), ends_at=kt(15, 8))

    def test_the_database_refuses_a_second_name_at_one_hospital_in_any_case(self, seaview, cardiologist):
        with pytest.raises(IntegrityError), transaction.atomic():
            Specialist.objects.create(hospital=seaview, name=NAME.upper(), specialty="ENT")
