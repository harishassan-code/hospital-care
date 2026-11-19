"""Shared setup for the patient transfer tests (B17, stories #63 to #65): a case at a sending hospital that is
short of blood, a destination hospital that has it, the staff who act at each, and a helper that walks a stock
transfer of the case to any status through the real moves."""

from dataclasses import dataclass

from apps.accounts.models import Role
from apps.matching.tests.reservation_support import blood_need, case, staff, unit
from apps.transfers.services import approve, dispatch, request_transfer, start_transit


@dataclass
class Move:
    sending: object  # the case's hospital until the patient arrives
    destination: object  # the hospital the patient may be moved to
    emergency: object
    item: object  # the case's need: red cells
    stock: list  # the destination's units of the need's group, free when the scenario starts
    doctor: object  # doctor at the sending hospital: edits emergencies, asks for the move
    nurse: object  # nurse at the sending hospital: asks for stock from other hospitals
    sending_bank: object  # blood bank at the sending hospital: allocates its own holds
    receiver: object  # doctor at the destination: confirms arrival


def scenario(
    make_user,
    make_hospital,
    *,
    severity="critical",
    need=2,
    destination_stock=2,
    local_stock=0,
    status="open",
):
    """A case at CityCare General that needs `need` units of A+ red cells, with `local_stock` of them free
    there, and Seaview holding `destination_stock` more. Critical and open by default."""
    sending = make_hospital(name="CityCare General")
    destination = make_hospital(name="Seaview")
    emergency = case(sending, blood_need("A+", quantity=need), severity=severity, status=status)
    for _ in range(local_stock):
        unit(sending, "A+")
    stock = [unit(destination, "A+") for _ in range(destination_stock)]
    return Move(
        sending=sending,
        destination=destination,
        emergency=emergency,
        item=emergency.items.get(),
        stock=stock,
        doctor=staff(make_user, sending, Role.DOCTOR),
        nurse=staff(make_user, sending, Role.NURSE),
        sending_bank=staff(make_user, sending, Role.BLOOD_BANK),
        receiver=staff(make_user, destination, Role.DOCTOR),
    )


def stock_transfer(s: Move, make_user, supplier, *, status="requested", quantity=1):
    """A stock transfer of the case's need from `supplier`, walked to `status` (requested, approved,
    dispatched or inTransit) by the real moves. The case's nurse asks; the supplier's blood bank answers and
    ships. The supplier gets the units it needs first."""
    supplier_bank = staff(make_user, supplier, Role.BLOOD_BANK)
    for _ in range(quantity):
        unit(supplier, s.item.blood_group)
    transfer = request_transfer(s.item, supplier=supplier, quantity=quantity, actor=s.nurse)
    if status == "requested":
        return transfer
    transfer = approve(transfer, actor=supplier_bank)
    if status == "approved":
        return transfer
    transfer = dispatch(transfer, actor=supplier_bank)
    if status == "dispatched":
        return transfer
    return start_transit(transfer, actor=supplier_bank)
