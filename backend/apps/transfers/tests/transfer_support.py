"""Shared setup for the transfer tests (stories #47 to #49): a case at a receiving hospital that needs
stock, a supplying hospital that has it, the staff who act at each, and helpers that walk a transfer to any
status through the real moves."""

from dataclasses import dataclass

from apps.accounts.models import Role
from apps.matching.tests.reservation_support import blood_need, case, equipment, equipment_need, staff, unit

from ..services import approve, cancel, dispatch, receive, reject, request_transfer, start_transit


@dataclass
class Scenario:
    kind: str
    receiver: object  # the case's hospital
    supplier: object  # the hospital with the stock
    case: object
    item: object  # the case's need
    stock: list  # the supplier's resources, free when the scenario starts
    requester: object  # nurse at the receiver: edits emergencies, asks for the transfer
    supplier_staff: object  # answers and ships at the supplier
    receiver_staff: object  # confirms receipt at the receiver


def scenario(make_user, make_hospital, *, kind="blood", need=2, stock=2, status="open"):
    """A case at CityCare General that needs `need` of blood (A+ red cells) or of ventilators, and `stock` of
    that resource free at Seaview. Staff: a nurse asks, and the type's own role answers and receives."""
    receiver = make_hospital(name="CityCare General")
    supplier = make_hospital(name="Seaview")
    if kind == "blood":
        spec = blood_need("A+", quantity=need)
        resources = [unit(supplier, "A+") for _ in range(stock)]
        role = Role.BLOOD_BANK
    else:
        spec = equipment_need(quantity=need)
        resources = [equipment(supplier) for _ in range(stock)]
        role = Role.NURSE
    emergency = case(receiver, spec, status=status)
    return Scenario(
        kind=kind,
        receiver=receiver,
        supplier=supplier,
        case=emergency,
        item=emergency.items.get(),
        stock=resources,
        requester=staff(make_user, receiver, Role.NURSE),
        supplier_staff=staff(make_user, supplier, role),
        receiver_staff=staff(make_user, receiver, role),
    )


def ask(s, quantity=None, *, actor=None):
    """The requester asks the supplier for `quantity` (default: the whole need)."""
    return request_transfer(
        s.item, supplier=s.supplier, quantity=quantity or s.item.quantity, actor=actor or s.requester
    )


def reach(s, status, quantity=None):
    """A transfer in `status`, reached through the real moves: asked, approved, dispatched, in transit,
    received. Rejected and cancelled are reached from requested."""
    transfer = ask(s, quantity)
    if status == "requested":
        return transfer
    if status == "rejected":
        return reject(transfer, actor=s.supplier_staff, reason="No spare stock")
    if status == "cancelled":
        return cancel(transfer, actor=s.requester, reason="Patient moved")
    transfer = approve(transfer, actor=s.supplier_staff)
    if status == "approved":
        return transfer
    transfer = dispatch(transfer, actor=s.supplier_staff)
    if status == "dispatched":
        return transfer
    transfer = start_transit(transfer, actor=s.supplier_staff)
    if status == "inTransit":
        return transfer
    return receive(transfer, actor=s.receiver_staff)


def holds(transfer):
    """The transfer's holds, oldest first."""
    return list(transfer.reservations.order_by("created_at", "id"))


def stock_statuses(s):
    """The status of every unit or piece of equipment the supplier offered, as it is now."""
    return [resource.__class__.objects.get(pk=resource.pk).status for resource in s.stock]


def location_of(resource):
    resource.refresh_from_db()
    return resource.hospital, resource.location
