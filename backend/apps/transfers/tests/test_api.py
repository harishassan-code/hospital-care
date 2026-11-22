"""Stories #47 to #49 in the API: the transfers endpoints, the transfers on the case page, the pinned
holds, and the whole scenario from a case to a fulfilled case. Shapes match frontend/src/api/transfers.ts."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.blood.models import BloodUnit
from apps.matching.models import Allocation
from apps.matching.reservations import reserve
from apps.matching.tests.reservation_support import bed_need, case, staff, unit

from .transfer_support import ask, reach, scenario

pytestmark = pytest.mark.django_db

TRANSFER_KEYS = {
    "id",
    "case",
    "itemId",
    "resourceType",
    "need",
    "supplier",
    "receiver",
    "quantity",
    "approved",
    "resources",
    "status",
    "reason",
    "trip",  # story #51: the latest trip, or null
    "etaMinutes",  # story #51: the route estimate
    "requestedBy",
    "createdAt",
    "history",
    "actions",
}
HISTORY_KEYS = {"fromStatus", "toStatus", "action", "note", "actor", "at"}


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def list_url():
    return reverse("transfer-list")


def detail_url(transfer):
    return reverse("transfer-detail", args=[transfer.pk])


def action(client, transfer, name, **body):
    return client.post(
        reverse("transfer-action", args=[transfer.pk]), {"action": name, **body}, format="json"
    )


def ask_via_api(client, item, supplier, quantity, **extra):
    return client.post(
        list_url(),
        {"itemId": item.pk, "supplierId": supplier.pk, "quantity": quantity, **extra},
        format="json",
    )


@pytest.fixture
def s(make_user, make_hospital):
    return scenario(make_user, make_hospital)


@pytest.fixture
def requester(s):
    return as_user(s.requester)


@pytest.fixture
def supplier(s):
    return as_user(s.supplier_staff)


@pytest.fixture
def receiver(s):
    return as_user(s.receiver_staff)


# ── Access ────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", list(Role))
def test_the_list_needs_the_transfers_module_and_nothing_else(client_as, role):
    expected = 403 if role in (Role.PHARMACIST, Role.PATIENT) else 200

    assert client_as(role).get(list_url()).status_code == expected


def test_signed_out_callers_are_refused(api):
    assert api.get(list_url()).status_code == 403
    assert api.post(list_url(), {}, format="json").status_code == 403


@pytest.mark.parametrize("role", [Role.PHARMACIST, Role.PATIENT])
def test_pharmacists_and_patients_cannot_ask_act_or_read_one(client_as, s, role):
    transfer = reach(s, "approved")
    outsider = client_as(role)

    assert ask_via_api(outsider, s.item, s.supplier, 1).status_code == 403
    assert outsider.get(detail_url(transfer)).status_code == 403
    assert action(outsider, transfer, "cancel").status_code == 403


def test_a_blood_bank_at_the_case_hospital_cannot_ask_for_stock(receiver, s):
    response = ask_via_api(receiver, s.item, s.supplier, 1)

    assert response.status_code == 403
    assert response.json()["detail"].startswith("Only staff at the case's hospital")


# ── Asking ────────────────────────────────────────────────────────────────────────────────────────


def test_asking_returns_201_with_the_request_and_the_moves_offered(requester, s):
    response = ask_via_api(requester, s.item, s.supplier, 2, note="Urgent")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == TRANSFER_KEYS
    assert body["status"] == "requested"
    assert body["approved"] == 0 and body["resources"] == []
    assert body["actions"] == ["cancel"]
    assert body["history"][0]["note"] == "Urgent"


@pytest.mark.parametrize(
    ("body_for", "field"),
    [
        (lambda s: {"supplierId": 999999}, "supplierId"),
        (lambda s: {"supplierId": s.receiver.pk}, "supplierId"),
        (lambda s: {"quantity": 0}, "quantity"),
        (lambda s: {"quantity": 3}, "quantity"),
    ],
    ids=["unknown-supplier", "own-hospital", "zero", "too-many"],
)
def test_a_request_that_breaks_a_rule_is_a_400_and_saves_nothing(requester, s, body_for, field):
    body = {"itemId": s.item.pk, "supplierId": s.supplier.pk, "quantity": 2, **body_for(s)}

    response = requester.post(list_url(), body, format="json")

    assert response.status_code == 400
    assert field in response.json()
    assert not s.item.transfers.exists()


def test_an_inactive_supplier_is_unknown(requester, s):
    s.supplier.is_active = False
    s.supplier.save(update_fields=["is_active"])

    response = ask_via_api(requester, s.item, s.supplier, 1)

    assert response.status_code == 400
    assert "supplierId" in response.json()


def test_a_bed_need_is_refused_by_name(requester, s):
    bed_case = case(s.receiver, bed_need())

    response = ask_via_api(requester, bed_case.items.get(), s.supplier, 1)

    assert response.status_code == 400
    assert response.json() == {"itemId": ["Only blood and equipment can be transferred."]}


def test_a_closed_case_refuses_with_a_detail(requester, s):
    s.case.status = "closed"
    s.case.save(update_fields=["status"])

    response = ask_via_api(requester, s.item, s.supplier, 1)

    assert response.status_code == 400
    assert response.json()["detail"] == "Can't ask for stock for a case that is closed."


def test_the_case_must_be_visible_to_the_user(client_as, s):
    elsewhere = client_as(
        Role.NURSE, hospital=s.supplier
    )  # the supplier's nurse can't see the receiver's case

    assert ask_via_api(elsewhere, s.item, s.supplier, 1).status_code == 404


def test_an_unknown_need_is_404(requester, s):
    response = requester.post(
        list_url(), {"itemId": 999999, "supplierId": s.supplier.pk, "quantity": 1}, format="json"
    )

    assert response.status_code == 404


# ── Reading ───────────────────────────────────────────────────────────────────────────────────────


def test_a_transfer_has_the_agreed_shape(requester, s):
    transfer = reach(s, "approved")

    body = requester.get(detail_url(transfer)).json()

    assert set(body) == TRANSFER_KEYS
    assert body["case"] == {"reference": s.case.reference, "severity": "high"}
    assert body["itemId"] == s.item.pk
    assert body["resourceType"] == "blood"
    assert body["need"] == "A+ red cells"
    assert body["supplier"] == {"id": s.supplier.pk, "name": "Seaview"}
    assert body["receiver"] == {"id": s.receiver.pk, "name": "CityCare General"}
    assert (body["quantity"], body["approved"], body["status"], body["reason"]) == (2, 2, "approved", "")
    assert len(body["resources"]) == 2
    assert all(name.startswith("A+ red cells DN-") for name in body["resources"])
    assert body["requestedBy"] == s.requester.email
    assert body["actions"] == ["cancel"]
    assert [change["action"] for change in body["history"]] == ["request", "approve"]
    assert all(set(change) == HISTORY_KEYS for change in body["history"])
    assert body["history"][0]["fromStatus"] == "" and body["history"][0]["toStatus"] == "requested"


def test_the_list_is_newest_first_and_filters_by_direction_and_status(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=4, stock=2)
    waiting = ask(s, 2)
    approved = reach(s, "approved", quantity=2)  # the second request, so it comes first
    requester = as_user(s.requester)
    supplier = as_user(s.supplier_staff)

    rows = requester.get(list_url()).json()
    assert [row["id"] for row in rows] == [approved.pk, waiting.pk]

    assert [r["id"] for r in requester.get(list_url(), {"direction": "outgoing"}).json()] == [
        approved.pk,
        waiting.pk,
    ]
    assert requester.get(list_url(), {"direction": "incoming"}).json() == []
    assert [r["id"] for r in supplier.get(list_url(), {"direction": "incoming"}).json()] == [
        approved.pk,
        waiting.pk,
    ]
    assert supplier.get(list_url(), {"direction": "outgoing"}).json() == []
    assert [r["id"] for r in requester.get(list_url(), {"status": "requested"}).json()] == [waiting.pk]
    assert [r["id"] for r in requester.get(list_url(), {"status": "approved"}).json()] == [approved.pk]


def test_an_admin_sees_every_transfer_and_a_stranger_sees_none(make_user, make_hospital, client_as, s):
    reach(s, "requested")
    admin = as_user(make_user(Role.ADMIN))
    stranger = client_as(Role.DOCTOR, hospital=make_hospital(name="Northside Children's"))

    assert len(admin.get(list_url()).json()) == 1
    assert len(admin.get(list_url(), {"direction": "incoming"}).json()) == 1
    assert stranger.get(list_url()).json() == []


def test_bad_filters_are_400(requester):
    assert requester.get(list_url(), {"direction": "sideways"}).status_code == 400
    assert requester.get(list_url(), {"status": "archived"}).status_code == 400


def test_a_transfer_involving_neither_hospital_is_404(client_as, make_hospital, s):
    transfer = reach(s, "requested")
    stranger = client_as(Role.DOCTOR, hospital=make_hospital(name="Northside Children's"))

    assert stranger.get(detail_url(transfer)).status_code == 404
    assert action(stranger, transfer, "approve").status_code == 404


def test_both_hospitals_read_a_transfer_and_an_admin_reads_any(requester, supplier, s, make_user):
    transfer = reach(s, "requested")

    assert requester.get(detail_url(transfer)).status_code == 200
    assert supplier.get(detail_url(transfer)).status_code == 200
    assert as_user(make_user(Role.ADMIN)).get(detail_url(transfer)).status_code == 200


def test_the_list_costs_the_same_queries_however_many_transfers(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=4, stock=4)
    client = as_user(s.requester)

    def count():
        with CaptureQueriesContext(connection) as context:
            assert client.get(list_url()).status_code == 200
        return len(context.captured_queries)

    reach(s, "approved", quantity=1)
    one = count()
    reach(s, "requested", quantity=1)
    reach(s, "rejected", quantity=1)
    assert count() == one


# ── Moves ─────────────────────────────────────────────────────────────────────────────────────────


def test_the_supplier_approves_and_the_moves_offered_change(supplier, requester, s):
    transfer = ask(s)

    response = action(supplier, transfer, "approve", note="Two set aside")

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["approved"]) == ("approved", 2)
    assert body["actions"] == ["dispatch"]
    assert requester.get(detail_url(transfer)).json()["actions"] == ["cancel"]


def test_a_doctor_at_the_supplier_cannot_approve_blood(client_as, s):
    transfer = ask(s)
    doctor = client_as(Role.DOCTOR, hospital=s.supplier)

    response = action(doctor, transfer, "approve")

    assert response.status_code == 403
    assert "detail" in response.json()
    transfer.refresh_from_db()
    assert transfer.status == "requested"


def test_the_requester_cannot_approve_its_own_request(requester, s):
    transfer = ask(s)

    assert action(requester, transfer, "approve").status_code == 403


def test_an_admin_can_approve_at_any_hospital(make_user, s):
    transfer = ask(s)

    assert action(as_user(make_user(Role.ADMIN)), transfer, "approve").status_code == 200


def test_an_unknown_action_is_400(supplier, s):
    assert action(supplier, ask(s), "archive").status_code == 400


def test_rejecting_without_a_reason_is_a_400_under_reason(supplier, s):
    transfer = ask(s)

    for body in ({}, {"reason": "   "}):
        response = action(supplier, transfer, "reject", **body)
        assert response.status_code == 400
        assert list(response.json()) == ["reason"]
    transfer.refresh_from_db()
    assert transfer.status == "requested"


def test_rejecting_with_a_reason_answers_200(supplier, s):
    transfer = ask(s)

    response = action(supplier, transfer, "reject", reason="No spare stock")

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["reason"], body["actions"]) == ("rejected", "No spare stock", [])


def test_a_move_the_lifecycle_refuses_is_409_and_changes_nothing(supplier, s):
    transfer = reach(s, "approved")

    response = action(supplier, transfer, "approve")

    assert response.status_code == 409
    assert response.json() == {"detail": "Can't approve a transfer that is approved."}


def test_receiving_before_dispatch_is_409(receiver, s):
    transfer = reach(s, "approved")

    response = action(receiver, transfer, "deliver")

    assert response.status_code == 409
    assert response.json() == {"detail": "Can't deliver a transfer that is approved."}


def test_approval_with_no_stock_free_is_409_with_the_reason(make_user, make_hospital):
    s = scenario(make_user, make_hospital, stock=0)
    transfer = ask(s)

    response = action(as_user(s.supplier_staff), transfer, "approve")

    assert response.status_code == 409
    assert response.json() == {"detail": "No matching stock is free at this hospital."}


def test_the_requester_cannot_dispatch_or_receive(requester, receiver, s):
    transfer = reach(s, "dispatched")

    assert action(requester, transfer, "deliver").status_code == 403  # a nurse can't receive blood
    assert action(receiver, transfer, "dispatch").status_code == 403  # only the supplier ships


def test_the_full_moves_by_their_names(supplier, receiver, requester, s):
    transfer = ask(s)

    for name in ("approve", "dispatch", "startTransit"):
        assert action(supplier, transfer, name).status_code == 200
    response = action(receiver, transfer, "deliver", note="Checked")

    assert response.status_code == 200
    assert response.json()["status"] == "delivered"
    assert response.json()["actions"] == []


def test_cancelling_releases_the_units_and_the_requester_sees_it(requester, supplier, s):
    transfer = reach(s, "inTransit")

    response = action(requester, transfer, "cancel", reason="Patient moved")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert [unit.status for unit in BloodUnit.objects.filter(hospital=s.supplier)] == ["available"] * 2


def test_the_moves_are_refused_for_a_transfer_that_is_over(supplier, s):
    transfer = reach(s, "delivered")

    response = action(supplier, transfer, "reject", reason="Too late")

    assert response.status_code == 409


# ── The case page ─────────────────────────────────────────────────────────────────────────────────


def detail(client, s):
    return client.get(reverse("emergency-case", args=[s.case.reference])).json()


def test_the_case_page_lists_its_transfers_and_pins_their_holds(requester, s):
    transfer = reach(s, "approved")

    body = detail(requester, s)

    assert [row["id"] for row in body["transfers"]] == [transfer.pk]
    assert set(body["transfers"][0]) == TRANSFER_KEYS
    assert body["transfers"][0]["actions"] == ["cancel"]
    assert len(body["reservations"]) == 2
    for hold in body["reservations"]:
        assert hold["transfer"] == {"id": transfer.pk, "status": "approved"}
        assert hold["canAllocate"] is False


def test_a_hold_outside_any_transfer_is_not_pinned(requester, s):
    reach(s, "approved")
    unit(s.receiver, "A+")
    s.item.quantity = 3
    s.item.save(update_fields=["quantity"])
    reserve(s.item, hospital=s.receiver, quantity=1, actor=s.requester)

    holds = detail(requester, s)["reservations"]

    assert sorted(h["transfer"] is None for h in holds) == [False, False, True]


def test_the_case_page_cannot_release_a_pinned_hold(requester, s):
    reach(s, "approved")
    pinned = detail(requester, s)["reservations"][0]

    response = requester.post(
        reverse("emergency-case-reservation-release", args=[s.case.reference, pinned["id"]]), format="json"
    )

    assert response.status_code == 409
    assert response.json()["detail"].endswith("cancel the transfer instead.")


def test_the_case_page_cannot_allocate_a_pinned_hold(requester, supplier, s):
    reach(s, "approved")
    pinned = detail(requester, s)["reservations"][0]

    response = supplier.post(reverse("reservation-allocate", args=[pinned["id"]]), {}, format="json")

    assert response.status_code == 409
    assert response.json()["detail"].endswith("receive the transfer instead.")


# ── The whole scenario ────────────────────────────────────────────────────────────────────────────


def test_a_case_is_fulfilled_by_a_transfer_from_another_hospital(make_user, make_hospital):
    receiver = make_hospital(name="CityCare General")
    supplier_hospital = make_hospital(name="Seaview")
    nurse = as_user(staff(make_user, receiver, Role.NURSE))
    supplier_bank = as_user(staff(make_user, supplier_hospital, Role.BLOOD_BANK))
    receiving_bank = as_user(staff(make_user, receiver, Role.BLOOD_BANK))
    unit(supplier_hospital, "A+")
    unit(supplier_hospital, "A+")

    opened = nurse.post(
        reverse("emergency-cases"),
        {
            "severity": "critical",
            "items": [{"type": "blood", "group": "A+", "component": "redCells", "quantity": 2}],
        },
        format="json",
    )
    assert opened.status_code == 201
    reference = opened.json()["id"]
    case_url = reverse("emergency-case", args=[reference])
    item_id = nurse.get(case_url).json()["items"][0]["itemId"]

    candidates = nurse.get(reverse("emergency-case-candidates", args=[reference])).json()
    row = next(c for c in candidates["items"][0]["candidates"] if c["hospital"]["id"] == supplier_hospital.pk)
    assert (row["available"], row["covers"]) == (2, True)

    asked = nurse.post(
        list_url(), {"itemId": item_id, "supplierId": supplier_hospital.pk, "quantity": 2}, format="json"
    )
    assert asked.status_code == 201
    transfer_id = asked.json()["id"]
    transfer_url = reverse("transfer-detail", args=[transfer_id])
    for name in ("approve", "dispatch", "startTransit"):
        response = supplier_bank.post(
            reverse("transfer-action", args=[transfer_id]), {"action": name}, format="json"
        )
        assert response.status_code == 200
    assert response.json()["status"] == "inTransit"
    assert response.json()["approved"] == 2

    on_the_way = nurse.get(case_url).json()
    assert [t["status"] for t in on_the_way["transfers"]] == ["inTransit"]
    assert all(hold["transfer"]["status"] == "inTransit" for hold in on_the_way["reservations"])

    received = receiving_bank.post(
        reverse("transfer-action", args=[transfer_id]),
        {"action": "deliver", "note": "Checked"},
        format="json",
    )
    assert received.status_code == 200
    assert received.json()["status"] == "delivered"
    assert nurse.get(transfer_url).json()["actions"] == []

    final = nurse.get(case_url).json()
    assert final["status"] == "fulfilled"
    assert final["items"][0]["fulfilled"] == 2 and final["items"][0]["remaining"] == 0
    assert [a["hospital"]["name"] for a in final["allocations"]] == ["Seaview", "Seaview"]
    assert final["transfers"][0]["status"] == "delivered"
    here = BloodUnit.objects.filter(hospital=receiver)
    assert here.count() == 2 and {u.status for u in here} == {"issued"}
    assert Allocation.objects.filter(request__reference=reference).count() == 2
