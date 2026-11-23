"""Equipment, operating rooms and their lists, ambulances, blood stock and donors for the demo network (B20),
sized by each hospital's profile (profiles.py). Every function adds only what's missing, so a re-run changes
nothing."""

import random
from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.ambulances.models import Ambulance, AmbulanceStatus
from apps.blood.models import REQUIRED_TESTS, BloodGroup, BloodUnit, Component, Donor, TestResult, UnitStatus
from apps.equipment.models import Equipment, EquipmentStatus, EquipmentType
from apps.hospitals.models import Bed, BedStatus, BedType, Hospital, StorageLocation
from apps.operating_rooms.models import OperatingRoom, OrBooking, OrStatus

from .profiles import Profile

# component: (shelf life in days, share of stock); the same proportions as the main hospital's stock.
COMPONENT_SHARE = {
    Component.RED_CELLS: (42, 0.56),
    Component.PLASMA: (365, 0.24),
    Component.PLATELETS: (5, 0.12),
    Component.CRYO: (365, 0.08),
}
# Usable O- red cells away from the scenario hospitals expire no sooner than this, so the scenario's source
# (Seaview, whose units expire sooner) still ranks first for O- red cells: the end-to-end test asks it (B12).
O_NEG_MIN_DAYS_LEFT = 12

EQUIPMENT_NAMES = {
    EquipmentType.VENTILATOR: ["Hamilton C6", "Dräger Evita V500", "Mindray SV800"],
    EquipmentType.MONITOR: ["Philips IntelliVue MX450", "Mindray BeneVision N12", "GE Carescape B450"],
    EquipmentType.DEFIBRILLATOR: ["Zoll R Series", "Philips HeartStart XL+", "Mindray BeneHeart D6"],
    EquipmentType.DIALYSIS: ["Fresenius 5008S", "Nipro Surdial X", "B. Braun Dialog+"],
}
TAG = {
    EquipmentType.VENTILATOR: "VENT",
    EquipmentType.MONITOR: "MON",
    EquipmentType.DEFIBRILLATOR: "DEFIB",
    EquipmentType.DIALYSIS: "DIAL",
}

PROCEDURES = {
    "general": [
        "Laparoscopic cholecystectomy",
        "Appendicectomy",
        "Hernia repair",
        "Thyroidectomy",
        "Laparotomy",
    ],
    "cardiac": ["CABG", "Valve replacement", "Septal defect repair"],
    "trauma": ["Wound debridement", "Splenectomy", "External fixation"],
    "neuro": ["Craniotomy", "Burr hole evacuation", "Spinal decompression"],
    "orthopedic": ["Hip replacement", "Knee replacement", "ORIF femur", "Spinal fusion"],
    "obstetric": ["Caesarean section", "Hysterectomy", "Cervical cerclage"],
    "pediatric": ["Pyloromyotomy", "Hypospadias repair", "Cleft lip repair", "Orchidopexy"],
}
LETTERS = "ABDFGHIKMNORSTUYZ"


def poisson(rand: random.Random, lam: float) -> int:
    """A Poisson draw (Knuth for small means, a rounded normal above 30). Standard library only."""
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(rand.gauss(lam, lam**0.5)))
    limit, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        p *= rand.random()
        if p <= limit:
            return k
        k += 1


def _in_use_share(hospital: Hospital) -> float:
    """How busy the intensive care beds are: devices are used about as much."""
    icu = Bed.objects.filter(hospital=hospital, bed_type__in=(BedType.ICU, BedType.NICU))
    total = icu.exclude(status=BedStatus.OUT_OF_SERVICE).count()
    return icu.filter(status=BedStatus.OCCUPIED).count() / total if total else 0.5


def seed_equipment(hospital: Hospital, profile: Profile, rand: random.Random, *, main: bool):
    """Tops each kind of equipment up to the profile's total. At the main hospital the extra ventilators are
    all in use or in maintenance: the scenario's two free ones (VENT-003, VENT-005) stay the only free
    ones."""
    busy = _in_use_share(hospital)
    prefix = "" if main else f"{profile.code}-"
    for kind, total in profile.equipment.items():
        have = Equipment.objects.filter(hospital=hospital, equipment_type=kind).count()
        rows = []
        for n in range(have + 1, total + 1):
            roll = rand.random()
            if kind == EquipmentType.VENTILATOR:
                if main:
                    status = EquipmentStatus.MAINTENANCE if roll < 0.12 else EquipmentStatus.IN_USE
                else:
                    status = (
                        EquipmentStatus.MAINTENANCE
                        if roll < 0.08
                        else EquipmentStatus.IN_USE
                        if roll < 0.08 + busy * 0.8
                        else EquipmentStatus.AVAILABLE
                    )
            elif kind == EquipmentType.MONITOR:
                status = EquipmentStatus.IN_USE if roll < 0.7 else EquipmentStatus.AVAILABLE
            elif kind == EquipmentType.DIALYSIS:
                status = EquipmentStatus.IN_USE if roll < 0.55 else EquipmentStatus.AVAILABLE
            else:
                status = EquipmentStatus.OUT_OF_SERVICE if roll < 0.05 else EquipmentStatus.AVAILABLE
            width = 3 if main else 2
            rows.append(
                Equipment(
                    hospital=hospital,
                    identifier=f"{prefix}{TAG[kind]}-{n:0{width}d}",
                    equipment_type=kind,
                    name=rand.choice(EQUIPMENT_NAMES[kind]),
                    location="Intensive care" if kind == EquipmentType.VENTILATOR else "Wards",
                    status=status,
                )
            )
        Equipment.objects.bulk_create(rows)


def seed_rooms(hospital: Hospital, profile: Profile, rand: random.Random):
    have = set(OperatingRoom.objects.filter(hospital=hospital).values_list("name", flat=True))
    OperatingRoom.objects.bulk_create(
        OperatingRoom(
            hospital=hospital,
            name=name,
            capabilities=capabilities,
            location=location,
            status=OrStatus.MAINTENANCE if rand.random() < 0.06 else OrStatus.AVAILABLE,
        )
        for name, capabilities, location in profile.rooms
        if name not in have
    )


def seed_room_lists(hospital: Hospital, rand: random.Random, now, surgeons: list[str], *, skip=()):
    """Today's and tomorrow's elective lists for each room that has none (08:00 to about 17:00, cases of one
    to three hours with half an hour between), and each room's status now: in use during a case, cleaning for
    half an hour after one, otherwise as it was. `skip` names rooms whose bookings and status are fixed
    elsewhere."""
    booked_by = User.objects.get(username="nurse@demo.citycare.pk")
    today = timezone.localdate(now)
    for room in OperatingRoom.objects.filter(hospital=hospital).exclude(name__in=skip):
        if room.status in (OrStatus.MAINTENANCE, OrStatus.OUT_OF_SERVICE) or room.bookings.exists():
            continue
        procedures = [p for cap in room.capabilities for p in PROCEDURES.get(cap, [])] or PROCEDURES[
            "general"
        ]
        bookings = []
        for day in (0, 1):
            clock = timezone.make_aware(datetime.combine(today + timedelta(days=day), time(8)))
            end_of_list = clock.replace(hour=17)
            while clock < end_of_list:
                length = timedelta(minutes=rand.choice([60, 90, 120, 150, 180]))
                if clock + length > end_of_list + timedelta(minutes=30):
                    break
                if rand.random() < 0.8:
                    bookings.append(
                        OrBooking(
                            room=room,
                            booked_by=booked_by,
                            starts_at=clock,
                            ends_at=clock + length,
                            procedure=rand.choice(procedures),
                            surgeon=rand.choice(surgeons) if surgeons else "",
                            patient_initials=f"{rand.choice(LETTERS)}.{rand.choice(LETTERS)}.",
                        )
                    )
                clock += length + timedelta(minutes=30)
        OrBooking.objects.bulk_create(bookings)
        running = any(b.starts_at <= now < b.ends_at for b in bookings)
        just_ended = any(b.ends_at <= now < b.ends_at + timedelta(minutes=30) for b in bookings)
        status = OrStatus.IN_USE if running else OrStatus.CLEANING if just_ended else room.status
        if status != room.status:
            room.status, room.status_since = status, now - timedelta(minutes=rand.randint(5, 40))
            room.save(update_fields=["status", "status_since"])


def seed_fleet(hospital: Hospital, profile: Profile, rand: random.Random):
    have = set(Ambulance.objects.filter(hospital=hospital).values_list("identifier", flat=True))
    rows, n = [], 0
    for kind, count in profile.ambulances:
        for _ in range(count):
            n += 1
            tag = f"{profile.code}-AMB-{n:02d}"
            if tag in have:
                continue
            status = AmbulanceStatus.MAINTENANCE if rand.random() < 0.12 else AmbulanceStatus.AVAILABLE
            rows.append(Ambulance(hospital=hospital, identifier=tag, type=kind, status=status))
    Ambulance.objects.bulk_create(rows)


def _location(hospital: Hospital, component: str) -> StorageLocation | None:
    names = list(StorageLocation.objects.filter(hospital=hospital).values_list("name", flat=True))
    wanted = {"plasma": "Plasma freezer", "cryo": "Plasma freezer", "platelets": "Platelet agitator"}.get(
        component
    )
    pick = next((n for n in names if wanted and n.startswith(wanted)), None) or next(
        (n for n in names if "fridge" in n.lower()), names[0] if names else None
    )
    return StorageLocation.objects.filter(hospital=hospital, name=pick).first()


def seed_bank_stock(
    hospital: Hospital,
    count: int,
    number_base: int,
    rand: random.Random,
    now,
    group_share,
    *,
    no_o_neg_red_cells=False,
):
    """A blood bank's stock: units of every component in the usual shares, of every age up to its shelf life,
    each with its screening results. Units collected in the last day are still in quarantine. With
    `no_o_neg_red_cells` (the scenario's partner hospitals), O- red cells are left to the scenario stock."""
    locations = {c: _location(hospital, c) for c in COMPONENT_SHARE}
    shares = {c: share for c, (_, share) in COMPONENT_SHARE.items()}
    units = []
    for i in range(count):
        component = rand.choices(list(shares), weights=list(shares.values()))[0]
        group = rand.choices(list(group_share), weights=list(group_share.values()))[0]
        if no_o_neg_red_cells and group == BloodGroup.O_NEG and component == Component.RED_CELLS:
            group = BloodGroup.O_POS
        shelf_life = COMPONENT_SHARE[component][0]
        age = timedelta(days=rand.random() * shelf_life * 1.03)
        if group == BloodGroup.O_NEG and component == Component.RED_CELLS:
            age = min(age, timedelta(days=shelf_life - O_NEG_MIN_DAYS_LEFT))
        collected = now - age
        expires = collected + timedelta(days=shelf_life)
        roll = rand.random()
        if expires <= now:
            status = UnitStatus.EXPIRED
        elif age < timedelta(days=1):
            status = UnitStatus.QUARANTINED
        elif roll < 0.06:
            status = UnitStatus.RESERVED
        elif roll < 0.1:
            status = UnitStatus.ISSUED
        else:
            status = UnitStatus.AVAILABLE
        location = locations[component]
        units.append(
            BloodUnit(
                hospital=hospital,
                storage_location=location,
                donation_number=f"G7731 26 {number_base + i:06d}",
                group=group,
                component=component,
                collected_at=collected,
                expires_at=expires,
                status=status,
                location=location.name if location else "Blood fridge",
            )
        )
    created = BloodUnit.objects.bulk_create(units)
    TestResult.objects.bulk_create(
        TestResult(unit=unit, test=test, passed=True)
        for unit in created
        if unit.status != UnitStatus.QUARANTINED
        for test in REQUIRED_TESTS
    )


FIRST = [
    "Ahmed",
    "Sana",
    "Bilal",
    "Hira",
    "Usman",
    "Ayesha",
    "Fahad",
    "Mahnoor",
    "Zain",
    "Iqra",
    "Hamza",
    "Areeba",
]
LAST = ["Khan", "Ahmed", "Siddiqui", "Raza", "Qureshi", "Malik", "Shaikh", "Hussain", "Ali", "Baig", "Memon"]


def seed_donors(hospital: Hospital, count: int, first_code: int, rand: random.Random, group_share):
    """Registered donors at a blood bank, all synthetic and marked "(demo)"."""
    Donor.objects.bulk_create(
        Donor(
            code=f"DNR-{first_code + i:05d}",
            hospital=hospital,
            full_name=f"{rand.choice(FIRST)} {rand.choice(LAST)} (demo)",
            blood_group=rand.choices(list(group_share), weights=list(group_share.values()))[0],
            phone=f"0300 {rand.randint(1_000_000, 9_999_999)}",
        )
        for i in range(count)
    )
