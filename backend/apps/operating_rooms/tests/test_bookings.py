"""Story #29: Operating room scheduling. Bookings are half-open [starts, ends) in the hospital's time zone."""

from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.operating_rooms import services
from apps.operating_rooms.models import OperatingRoom, OrBooking

pytestmark = pytest.mark.django_db

KHI = ZoneInfo("Asia/Karachi")
DAY = date(2030, 1, 15)


def at(hour, minute=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=KHI)


def make_room(name="OR 1", hospital=None, status="available"):
    return OperatingRoom.objects.create(
        name=name, capabilities=["general"], location="Block B", hospital=hospital, status=status
    )


def book(client, room, starts, ends, **extra):
    body = {
        "roomId": room.pk,
        "startsAt": starts.isoformat(),
        "endsAt": ends.isoformat(),
        "procedure": "Appendicectomy",
    }
    return client.post(reverse("operating-room-bookings"), {**body, **extra}, format="json")


def cancel(client, booking_id):
    return client.post(reverse("operating-room-booking-cancel", args=[booking_id]))


def schedule(client, day=DAY):
    return client.get(reverse("operating-room-schedule"), {"date": day.isoformat()})


# ── Booking ───────────────────────────────────────────────────────────────────────────────────────


def test_booking_is_saved_and_audit_logged(client_as):
    room = make_room()
    staff = client_as(Role.NURSE, first_name="Hina", last_name="Javed")
    res = book(staff, room, at(10), at(11), surgeon="Dr. Bilal Ahmed", patientInitials="A.K.")
    assert res.status_code == 201
    assert res.json() == {
        "id": res.json()["id"],
        "roomId": room.pk,
        "startsAt": at(10).isoformat(),
        "endsAt": at(11).isoformat(),
        "procedure": "Appendicectomy",
        "surgeon": "Dr. Bilal Ahmed",
        "patientInitials": "A.K.",
        "status": "booked",
        "bookedBy": "Hina Javed",
        "canCancel": True,
    }
    entry = AuditLog.objects.get(action="orbooking.created")
    assert entry.actor_email == "nurse@example.com" and entry.target_repr == "Appendicectomy"
    assert entry.after["room"] == "OR 1" and entry.after["procedure"] == "Appendicectomy"


@pytest.mark.parametrize(
    ("start", "end"),
    [((10, 0), (11, 0)), ((10, 15), (10, 45)), ((9, 30), (10, 30)), ((10, 30), (11, 30)), ((9, 0), (12, 0))],
    ids=["same", "inside", "straddles-start", "straddles-end", "covers"],
)
def test_overlapping_booking_in_the_same_room_is_refused(client_as, start, end):
    room = make_room()
    staff = client_as(Role.NURSE)
    assert book(staff, room, at(10), at(11)).status_code == 201
    res = book(staff, room, at(*start), at(*end))
    assert res.status_code == 400
    assert res.json() == {"startsAt": ["OR 1 is already booked from 10:00 to 11:00."]}
    assert OrBooking.objects.count() == 1


@pytest.mark.skipif(connection.vendor != "postgresql", reason="The exclusion constraint is PostgreSQL-only")
def test_a_clash_the_check_misses_is_still_refused_as_a_400(client_as):
    """A race: the pre-check sees nothing free, so the database constraint has to catch the clash."""
    room = make_room()
    staff = client_as(Role.NURSE)
    assert book(staff, room, at(10), at(11)).status_code == 201
    real_clash, calls = services._clash, []

    def pre_check_misses_once(*args):
        calls.append(args)
        return None if len(calls) == 1 else real_clash(*args)

    with mock.patch.object(services, "_clash", side_effect=pre_check_misses_once):
        res = book(staff, room, at(10, 30), at(11, 30))
    assert res.status_code == 400
    assert res.json() == {"startsAt": ["OR 1 is already booked from 10:00 to 11:00."]}
    assert OrBooking.objects.count() == 1


def test_back_to_back_bookings_are_allowed(client_as):
    room = make_room()
    staff = client_as(Role.NURSE)
    assert book(staff, room, at(10), at(11)).status_code == 201
    assert book(staff, room, at(11), at(12)).status_code == 201
    assert book(staff, room, at(9), at(10)).status_code == 201


def test_different_rooms_at_the_same_time_are_allowed(client_as):
    staff = client_as(Role.NURSE)
    assert book(staff, make_room("OR 1"), at(10), at(11)).status_code == 201
    assert book(staff, make_room("OR 2"), at(10), at(11)).status_code == 201


def test_cancelled_slot_can_be_booked_again(client_as):
    room = make_room()
    staff = client_as(Role.NURSE)
    booking_id = book(staff, room, at(10), at(11)).json()["id"]
    assert cancel(staff, booking_id).status_code == 200
    assert book(staff, room, at(10), at(11)).status_code == 201


@pytest.mark.parametrize(
    ("starts", "ends", "field"),
    [
        (at(10), at(10), "endsAt"),
        (at(11), at(10), "endsAt"),
        (at(8), at(8) + (at(9) - at(8)) * 25, "endsAt"),  # more than 24 hours
        (at(10, day=date(2020, 1, 1)), at(11, day=date(2020, 1, 1)), "startsAt"),  # in the past
    ],
    ids=["empty", "backwards", "too-long", "past"],
)
def test_invalid_times_are_refused(client_as, starts, ends, field):
    room = make_room()
    res = book(client_as(Role.NURSE), room, starts, ends)
    assert res.status_code == 400 and field in res.json()
    assert not OrBooking.objects.exists()


def test_a_full_24_hour_booking_is_allowed(client_as):
    room = make_room()
    assert book(client_as(Role.NURSE), room, at(0), at(0, day=date(2030, 1, 16))).status_code == 201


def test_out_of_service_room_is_refused(client_as):
    room = make_room(status="outOfService")
    res = book(client_as(Role.NURSE), room, at(10), at(11))
    assert res.status_code == 400 and res.json() == {"roomId": ["OR 1 is out of service."]}
    assert not OrBooking.objects.exists()


def test_another_hospitals_room_is_not_found(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    room = make_room(hospital=city)
    assert book(client_as(Role.NURSE, hospital=seaview), room, at(10), at(11)).status_code == 404
    assert not OrBooking.objects.exists()


def test_staff_without_a_hospital_cannot_book_a_hospitals_room(client_as, make_hospital):
    room = make_room(hospital=make_hospital("City"))
    assert book(client_as(Role.NURSE), room, at(10), at(11)).status_code == 404


def test_admin_can_book_any_hospitals_room(client_as, make_hospital):
    room = make_room(hospital=make_hospital("City"))
    admin = client_as(Role.ADMIN, hospital=make_hospital("Seaview"))
    assert book(admin, room, at(10), at(11)).status_code == 201


def test_doctor_can_book(client_as):
    assert book(client_as(Role.DOCTOR), make_room(), at(10), at(11)).status_code == 201


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_roles_without_access_get_403(client_as, role):
    client = client_as(role)
    assert book(client, make_room(), at(10), at(11)).status_code == 403
    assert schedule(client).status_code == 403
    assert not OrBooking.objects.exists()


# ── Cancelling ────────────────────────────────────────────────────────────────────────────────────


def test_cancel_keeps_the_row_and_audit_logs_it(client_as):
    staff = client_as(Role.NURSE)
    booking_id = book(staff, make_room(), at(10), at(11)).json()["id"]
    res = cancel(staff, booking_id)
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert OrBooking.objects.get(pk=booking_id).status == "cancelled"
    assert AuditLog.objects.filter(action="orbooking.cancelled", target_id=str(booking_id)).exists()


def test_cancelling_twice_is_409(client_as):
    staff = client_as(Role.NURSE)
    booking_id = book(staff, make_room(), at(10), at(11)).json()["id"]
    cancel(staff, booking_id)
    res = cancel(staff, booking_id)
    assert res.status_code == 409 and res.json() == {"detail": "This booking is already cancelled."}


def test_doctor_can_cancel_and_blood_bank_cannot(client_as):
    doctor = client_as(Role.DOCTOR)
    booking_id = book(doctor, make_room(), at(10), at(11)).json()["id"]
    assert cancel(client_as(Role.BLOOD_BANK), booking_id).status_code == 403
    assert cancel(doctor, booking_id).status_code == 200


def test_doctor_cannot_cancel_a_colleagues_booking_but_a_nurse_can(client_as):
    room = make_room()
    booking_id = book(client_as(Role.DOCTOR), room, at(10), at(11)).json()["id"]
    other_doctor = client_as(Role.DOCTOR, email="surgeon2@example.com")
    assert schedule(other_doctor).json()["rooms"][0]["bookings"][0]["canCancel"] is False
    assert cancel(other_doctor, booking_id).status_code == 403
    assert OrBooking.objects.get(pk=booking_id).status == "booked"
    nurse = client_as(Role.NURSE)
    assert schedule(nurse).json()["rooms"][0]["bookings"][0]["canCancel"] is True
    assert cancel(nurse, booking_id).status_code == 200


def test_another_hospitals_booking_cannot_be_cancelled(client_as, make_hospital):
    room = make_room(hospital=make_hospital("City"))
    booking_id = book(client_as(Role.ADMIN), room, at(10), at(11)).json()["id"]
    assert cancel(client_as(Role.NURSE, hospital=make_hospital("Seaview")), booking_id).status_code == 404
    assert OrBooking.objects.get(pk=booking_id).status == "booked"


# ── Day schedule ──────────────────────────────────────────────────────────────────────────────────


def test_schedule_groups_each_rooms_bookings_in_time_order(client_as):
    staff = client_as(Role.NURSE)
    or1, cardiac = make_room("OR 1"), make_room("Cardiac theatre")
    make_room("Trauma theatre", status="cleaning")
    book(staff, or1, at(11), at(12), procedure="Late case")
    book(staff, or1, at(8), at(9), procedure="Early case", surgeon="Dr. Bilal Ahmed")
    book(staff, cardiac, at(9), at(13), procedure="CABG")

    res = schedule(client_as(Role.DOCTOR))
    assert res.status_code == 200
    data = res.json()
    assert data["date"] == DAY.isoformat()
    assert [room["name"] for room in data["rooms"]] == ["Cardiac theatre", "OR 1", "Trauma theatre"]
    cardiac_row, or1_row, trauma_row = data["rooms"]
    assert [b["procedure"] for b in or1_row["bookings"]] == ["Early case", "Late case"]
    assert or1_row["bookings"][0] == {
        "id": or1_row["bookings"][0]["id"],
        "roomId": or1.pk,
        "startsAt": at(8).isoformat(),
        "endsAt": at(9).isoformat(),
        "procedure": "Early case",
        "surgeon": "Dr. Bilal Ahmed",
        "patientInitials": "",
        "status": "booked",
        "bookedBy": "",
        "canCancel": False,  # a doctor viewing a nurse's booking
    }
    assert [b["procedure"] for b in cardiac_row["bookings"]] == ["CABG"]
    assert trauma_row["bookings"] == [] and trauma_row["status"] == "cleaning"
    assert cardiac_row["capabilities"] == ["general"]


def test_schedule_shows_only_that_local_day(client_as):
    staff = client_as(Role.NURSE)
    room = make_room()
    book(staff, room, at(23, 30), at(23, 45), procedure="Tonight")
    book(staff, room, at(0, 30, day=date(2030, 1, 16)), at(1, 0, day=date(2030, 1, 16)), procedure="Tomorrow")
    book(staff, room, at(23, day=date(2030, 1, 14)), at(1, day=DAY), procedure="Runs past midnight")

    def procedures(day):
        return [b["procedure"] for b in schedule(staff, day).json()["rooms"][0]["bookings"]]

    assert procedures(DAY) == ["Runs past midnight", "Tonight"]  # the 14th's late case ends on the 15th
    assert procedures(date(2030, 1, 14)) == ["Runs past midnight"]
    assert procedures(date(2030, 1, 16)) == ["Tomorrow"]


def test_schedule_leaves_out_cancelled_bookings(client_as):
    staff = client_as(Role.NURSE)
    room = make_room()
    booking_id = book(staff, room, at(10), at(11)).json()["id"]
    cancel(staff, booking_id)
    assert schedule(staff).json()["rooms"][0]["bookings"] == []


def test_schedule_is_scoped_to_the_users_hospital(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make_room("OR 1", hospital=seaview)
    make_room("OR 2", hospital=city)
    names = [r["name"] for r in schedule(client_as(Role.NURSE, hospital=seaview)).json()["rooms"]]
    assert names == ["OR 1"]


@pytest.mark.parametrize("bad", ["2030-02-30", "tomorrow", "15-01-2030"])
def test_bad_date_is_400(client_as, bad):
    res = client_as(Role.NURSE).get(reverse("operating-room-schedule"), {"date": bad})
    assert res.status_code == 400 and "date" in res.json()


def test_schedule_defaults_to_today(client_as):
    res = client_as(Role.NURSE).get(reverse("operating-room-schedule"))
    assert res.status_code == 200 and res.json()["date"] == timezone.localdate().isoformat()


# ── The database itself ───────────────────────────────────────────────────────────────────────────


def test_database_refuses_a_booking_that_ends_before_it_starts(make_user):
    room, user = make_room(), make_user(Role.NURSE)
    with pytest.raises(IntegrityError), transaction.atomic():
        OrBooking.objects.create(room=room, starts_at=at(11), ends_at=at(10), procedure="X", booked_by=user)


@pytest.mark.skipif(connection.vendor != "postgresql", reason="The exclusion constraint is PostgreSQL-only")
def test_database_refuses_overlapping_booked_rows_in_one_room(make_user):
    """The DB, not the service, is the last line of defence: rows written directly must still not overlap."""
    user = make_user(Role.NURSE)
    room, other_room = make_room("OR 1"), make_room("OR 2")
    OrBooking.objects.create(room=room, starts_at=at(10), ends_at=at(11), procedure="First", booked_by=user)

    with pytest.raises(IntegrityError), transaction.atomic():
        OrBooking.objects.create(
            room=room, starts_at=at(10, 30), ends_at=at(11, 30), procedure="Clash", booked_by=user
        )

    # A cancelled row is outside the constraint's condition, so it may overlap a booked one...
    OrBooking.objects.create(
        room=room,
        starts_at=at(10, 30),
        ends_at=at(11, 30),
        procedure="Cancelled",
        booked_by=user,
        status="cancelled",
    )
    # ...and the same time in another room is fine, as is a back-to-back slot.
    OrBooking.objects.create(
        room=other_room, starts_at=at(10), ends_at=at(11), procedure="Other", booked_by=user
    )
    OrBooking.objects.create(room=room, starts_at=at(11), ends_at=at(12), procedure="Next", booked_by=user)
    assert OrBooking.objects.filter(status="booked").count() == 3
