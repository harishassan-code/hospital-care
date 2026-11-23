"""The hourly figures kept per hospital (B20). Counts per hour are what happened in that hour; levels are
what was true at the end of it. Bed figures are per bed type: the key is the template with the type filled
in."""

from apps.hospitals.models import BedType

# Levels (at the end of the hour)
BEDS_OCCUPIED = "beds.occupied.{bed_type}"
BEDS_IN_SERVICE = "beds.in_service.{bed_type}"
ER_WAITING = "er.waiting"
ER_WAIT_MINUTES = "er.wait_minutes"
BLOOD_RED_CELLS = "blood.red_cells"  # usable red-cell units
OR_IN_USE = "or.in_use"
OR_ROOMS = "or.rooms"
VENTILATORS_IN_USE = "equipment.ventilators_in_use"
STAFF_ON_DUTY = "staff.on_duty.{role}"

# Counts (during the hour)
ER_ARRIVALS = "er.arrivals"
ER_DEPARTURES = "er.departures"
BLOOD_ISSUED = "blood.issued"
BLOOD_DONATED = "blood.donated"
AMBULANCE_TRIPS = "ambulances.trips"

COUNTS = (ER_ARRIVALS, ER_DEPARTURES, BLOOD_ISSUED, BLOOD_DONATED, AMBULANCE_TRIPS)


def beds_occupied(bed_type: str) -> str:
    return BEDS_OCCUPIED.format(bed_type=bed_type)


def beds_in_service(bed_type: str) -> str:
    return BEDS_IN_SERVICE.format(bed_type=bed_type)


def staff_on_duty(role: str) -> str:
    return STAFF_ON_DUTY.format(role=role)


def all_metrics() -> list[str]:
    beds = [
        key for bed_type in BedType.values for key in (beds_occupied(bed_type), beds_in_service(bed_type))
    ]
    return [
        *beds,
        ER_WAITING,
        ER_WAIT_MINUTES,
        BLOOD_RED_CELLS,
        OR_IN_USE,
        OR_ROOMS,
        VENTILATORS_IN_USE,
        staff_on_duty("doctor"),
        staff_on_duty("nurse"),
        *COUNTS,
    ]
