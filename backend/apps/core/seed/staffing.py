"""Doctors' and nurses' rosters for the demo network (B20): who works where, their shifts from two weeks ago
to a week ahead, and when each past shift really started and ended. All names are synthetic.

Nurses work 08-14, 14-20 or 20-08 (the hospital's shifts in config/hospital.ts), six days in seven; doctors
work 08-20 or 20-08, five days in seven. How many per shift follows each ward's beds and the usual
nurse-to-patient ratio for its kind (docs/product/demo-data.md). The first consultant of each department at
the new hospitals is also its on-call specialist (B16), so the specialist directory and the public "on duty
now" agree with the rota.
"""

import math
import random
from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.hospitals.models import BedType, Hospital, Ward
from apps.specialists.models import OnCallWindow, Specialist
from apps.staffing.models import Shift, StaffMember, StaffRole

PAST_DAYS = 14
AHEAD_DAYS = 7

NURSE_SHIFTS = [(time(8), time(14)), (time(14), time(20)), (time(20), time(8))]
DOCTOR_SHIFTS = [(time(8), time(20)), (time(20), time(8))]
# Patients per nurse on a shift, by bed type (intensive care 1:2, emergency 1:4, wards 1:8).
PATIENTS_PER_NURSE = {BedType.ICU: 2, BedType.NICU: 2, BedType.EMERGENCY: 4}
WARD_PATIENTS_PER_NURSE = 8
BEDS_PER_DOCTOR = 12

FEMALE = [
    "Ayesha",
    "Fatima",
    "Hira",
    "Sana",
    "Mahnoor",
    "Iqra",
    "Zara",
    "Nimra",
    "Maryam",
    "Rabia",
    "Saima",
    "Amna",
    "Hafsa",
    "Kiran",
    "Mehwish",
    "Sadia",
    "Uzma",
    "Farah",
    "Noor",
    "Areeba",
]
MALE = [
    "Ahmed",
    "Bilal",
    "Usman",
    "Hamza",
    "Fahad",
    "Zain",
    "Ali",
    "Imran",
    "Kashif",
    "Saad",
    "Faisal",
    "Omar",
    "Danish",
    "Junaid",
    "Asad",
    "Haris",
    "Waqas",
    "Shahzaib",
    "Arsalan",
    "Talha",
]
SURNAMES = [
    "Khan",
    "Ahmed",
    "Siddiqui",
    "Raza",
    "Qureshi",
    "Malik",
    "Shaikh",
    "Hussain",
    "Baig",
    "Memon",
    "Abbasi",
    "Ansari",
    "Chaudhry",
    "Mirza",
    "Rizvi",
    "Jafri",
    "Hashmi",
    "Butt",
    "Zaidi",
    "Naqvi",
]


def _name(rand: random.Random, used: set[str], *, doctor: bool) -> str:
    for _ in range(50):
        first = rand.choice(FEMALE if rand.random() < (0.55 if doctor else 0.8) else MALE)
        name = f"{'Dr. ' if doctor else ''}{first} {rand.choice(SURNAMES)}"
        if name not in used:
            used.add(name)
            return name
    name = f"{name} {len(used)}"
    used.add(name)
    return name


def _per_shift(ward: Ward, beds: int, bed_type: str) -> int:
    return max(1, math.ceil(beds / PATIENTS_PER_NURSE.get(bed_type, WARD_PATIENTS_PER_NURSE)))


def _shift_rows(member: StaffMember, slot: tuple[time, time], days_off: set[int], rand, now) -> list[Shift]:
    """One row per working day from PAST_DAYS ago to AHEAD_DAYS ahead, with clock times for those that
    started."""
    today = timezone.localdate(now)
    rows = []
    for offset in range(-PAST_DAYS, AHEAD_DAYS + 1):
        day = today + timedelta(days=offset)
        if day.weekday() in days_off:
            continue
        start = timezone.make_aware(datetime.combine(day, slot[0]))
        end = timezone.make_aware(
            datetime.combine(day + timedelta(days=1 if slot[1] <= slot[0] else 0), slot[1])
        )
        shift = Shift(staff=member, hospital=member.hospital, starts_at=start, ends_at=end)
        if start <= now and rand.random() > 0.03:  # about 1 in 33 past shifts was missed
            late = rand.random() < 0.06
            shift.clocked_in_at = start + timedelta(
                minutes=rand.randint(15, 45) if late else rand.randint(-12, 8)
            )
            if end <= now:
                shift.clocked_out_at = end + timedelta(minutes=rand.randint(0, 25))
        rows.append(shift)
    return rows


def seed_roster(hospital: Hospital, rand: random.Random, now) -> list[StaffMember]:
    """The hospital's doctors and nurses and their shifts. Does nothing if it already has a roster."""
    if StaffMember.objects.filter(hospital=hospital).exists():
        return []
    used: set[str] = set()
    members: list[tuple[StaffMember, tuple[time, time], set[int]]] = []
    dept_beds: dict[str, int] = {}
    for ward in Ward.objects.filter(hospital=hospital).select_related("department"):
        beds = list(ward.beds.values_list("bed_type", flat=True))
        if not beds:
            continue
        bed_type = max(set(beds), key=beds.count)
        department = ward.department.name if ward.department else "General medicine"
        dept_beds[department] = dept_beds.get(department, 0) + len(beds)
        for slot in NURSE_SHIFTS:
            per_shift = _per_shift(ward, len(beds), bed_type)
            for n in range(per_shift + math.ceil(per_shift / 6)):  # cover the day off
                member = StaffMember(
                    hospital=hospital,
                    name=_name(rand, used, doctor=False),
                    role=StaffRole.NURSE,
                    department=department,
                )
                members.append((member, slot, {(n + len(members)) % 7}))
    if not dept_beds:  # a blood bank: transfusion staff on days
        dept_beds = {
            hospital.departments.values_list("name", flat=True).first() or "Transfusion medicine": 24
        }
    for department, beds in dept_beds.items():
        per_shift = max(1, math.ceil(beds / BEDS_PER_DOCTOR))
        for slot in DOCTOR_SHIFTS:
            for n in range(per_shift + math.ceil(per_shift * 0.4)):
                member = StaffMember(
                    hospital=hospital,
                    name=_name(rand, used, doctor=True),
                    role=StaffRole.DOCTOR,
                    department=department,
                )
                first_off = (n + len(members)) % 7
                members.append((member, slot, {first_off, (first_off + 3) % 7}))
    StaffMember.objects.bulk_create([m for m, _, _ in members])
    shifts = [row for member, slot, off in members for row in _shift_rows(member, slot, off, rand, now)]
    Shift.objects.bulk_create(shifts, batch_size=2000)
    return [m for m, _, _ in members]


def seed_consultants(hospital: Hospital, members: list[StaffMember], now, days: int):
    """At each department, the first day doctor and the first night doctor are its on-call specialists for the
    next `days` days: 08:00-20:00 and 20:00-08:00, so someone is always on call."""
    today = timezone.localdate(now)
    if Specialist.objects.filter(hospital=hospital).exists():
        _top_up_windows(hospital, today, days)
        return
    by_department: dict[str, list[StaffMember]] = {}
    for member in members:
        if member.role == StaffRole.DOCTOR:
            by_department.setdefault(member.department, []).append(member)
    windows = []
    for department, doctors in by_department.items():
        if department == "Emergency medicine" and len(by_department) > 1:
            continue  # the emergency department is staffed round the clock, not on call
        for doctor, (start, end) in zip(doctors[:1] + doctors[-1:], DOCTOR_SHIFTS, strict=False):
            specialist = Specialist.objects.create(hospital=hospital, name=doctor.name, specialty=department)
            for offset in range(days):
                day = today + timedelta(days=offset)
                starts = timezone.make_aware(datetime.combine(day, start))
                ends = timezone.make_aware(
                    datetime.combine(day + timedelta(days=1 if end <= start else 0), end)
                )
                windows.append(OnCallWindow(specialist=specialist, starts_at=starts, ends_at=ends))
    OnCallWindow.objects.bulk_create(windows)


def _top_up_windows(hospital: Hospital, today, days: int):
    """On a re-run, give each of the hospital's seeded specialists the windows of the next `days` days it
    doesn't have yet, at the same times of day as its last one, so staging never runs out of on-call doctors.
    Specialists with no window (added by staff) are left alone."""
    missing = []
    for specialist in Specialist.objects.filter(hospital=hospital):
        last = specialist.on_call_windows.order_by("-starts_at").first()
        if last is None:
            continue
        start, end = timezone.localtime(last.starts_at).time(), timezone.localtime(last.ends_at).time()
        booked = set(specialist.on_call_windows.values_list("starts_at", flat=True))
        for offset in range(days):
            day = today + timedelta(days=offset)
            starts = timezone.make_aware(datetime.combine(day, start))
            ends = timezone.make_aware(datetime.combine(day + timedelta(days=1 if end <= start else 0), end))
            if starts not in booked:
                missing.append(OnCallWindow(specialist=specialist, starts_at=starts, ends_at=ends))
    OnCallWindow.objects.bulk_create(missing)
