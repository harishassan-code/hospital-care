"""
Fill the database with demo data matching the frontend's sample data, plus one login per staff role.

    python manage.py seed_demo            # adds data only if the tables are empty
    python manage.py seed_demo --reset    # wipes beds, blood, pharmacy, doctors first

Demo data only: never run against a database with real patients.
"""

import random
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.blood.models import BloodUnit, Component, UnitStatus
from apps.emergencies.models import EmergencyStatus, ErStatus
from apps.hospitals.models import Bed, BedStatus, DoctorShift, Ward
from apps.pharmacy.models import Batch, Medicine

DEMO_PASSWORD = "CityCare-demo-1"
DEMO_USERS = [
    ("admin@demo.citycare.pk", "Amna", "Admin", Role.ADMIN),
    ("doctor@demo.citycare.pk", "Kamran", "Shah", Role.DOCTOR),
    ("nurse@demo.citycare.pk", "Hina", "Javed", Role.NURSE),
    ("bloodbank@demo.citycare.pk", "Tariq", "Lodhi", Role.BLOOD_BANK),
    ("pharmacist@demo.citycare.pk", "Saima", "Raza", Role.PHARMACIST),
    ("patient@demo.citycare.pk", "Ali", "Patient", Role.PATIENT),
]

# code, name, kind, label prefix, size, occupancy, (min age, max age)
WARDS = [
    ("icu", "ICU", "Intensive care", "ICU", 10, 0.9, (18, 85)),
    ("hdu", "HDU", "High dependency", "HDU", 8, 0.85, (18, 85)),
    ("medA", "Medical A", "General medicine", "MA", 24, 0.8, (18, 92)),
    ("surgB", "Surgical B", "General surgery", "SB", 24, 0.75, (16, 88)),
    ("paeds", "Paediatrics", "Children", "PD", 16, 0.62, (1, 14)),
    ("maternity", "Maternity", "Obstetrics", "MT", 18, 0.7, (18, 42)),
    ("isolation", "Isolation", "Infection control", "ISO", 6, 0.67, (18, 80)),
]

DOCTORS = [
    ("Dr. Kamran Shah", "Emergency medicine", "08:00", "20:00"),
    ("Dr. Usman Farooq", "Emergency medicine", "20:00", "08:00"),
    ("Dr. Nadia Rehman", "Emergency medicine", "14:00", "02:00"),
    ("Dr. Bilal Ahmed", "General medicine", "08:00", "16:00"),
    ("Dr. Zainab Hussain", "General medicine", "16:00", "00:00"),
    ("Dr. Faisal Mirza", "General medicine", "00:00", "08:00"),
    ("Dr. Ayesha Khan", "Cardiology", "09:00", "13:00"),
    ("Dr. Omar Sheikh", "Cardiology", "16:00", "22:00"),
    ("Dr. Sana Malik", "Paediatrics", "10:00", "16:00"),
    ("Dr. Mariam Iqbal", "Paediatrics", "18:00", "23:00"),
    ("Dr. Imran Qureshi", "Orthopaedics", "09:00", "15:00"),
    ("Dr. Hamza Butt", "Orthopaedics", "15:00", "21:00"),
    ("Dr. Fatima Zaidi", "Gynaecology", "08:00", "14:00"),
    ("Dr. Rabia Anwar", "Gynaecology", "20:00", "08:00"),
]

# component: (shelf life days, storage locations, share of stock)
COMPONENTS = {
    Component.RED_CELLS: (42, ["Blood fridge 1", "Blood fridge 2"], 0.56),
    Component.PLASMA: (365, ["Plasma freezer A"], 0.24),
    Component.PLATELETS: (5, ["Platelet agitator"], 0.12),
    Component.CRYO: (365, ["Plasma freezer B"], 0.08),
}
# Approximate share of each group among donors in Pakistan.
GROUP_SHARE = {
    "B+": 0.33,
    "O+": 0.28,
    "A+": 0.22,
    "AB+": 0.07,
    "B-": 0.03,
    "O-": 0.025,
    "A-": 0.025,
    "AB-": 0.02,
}

# code, name, strength, form, category, unit, reorder, daily use, location, batches, high alert, controlled
# batches: (number, days until expiry, quantity)
FORMULARY = [
    (
        "pcm-tab",
        "Paracetamol",
        "500 mg",
        "Tablet",
        "Analgesic",
        "tablets",
        2000,
        450,
        "Main store A1",
        [("PCM-2405", 420, 6000), ("PCM-2311", 150, 2400)],
        False,
        False,
    ),
    (
        "pcm-iv",
        "Paracetamol",
        "1 g / 100 mL",
        "Infusion",
        "Analgesic",
        "bags",
        120,
        35,
        "Main store A2",
        [("PIV-2402", 60, 180), ("PIV-2408", 300, 220)],
        False,
        False,
    ),
    (
        "coamox",
        "Amoxicillin–clavulanate",
        "625 mg",
        "Tablet",
        "Antibiotic",
        "tablets",
        600,
        140,
        "Main store B1",
        [("AMC-2404", 280, 1900)],
        False,
        False,
    ),
    (
        "ceftriaxone",
        "Ceftriaxone",
        "1 g",
        "Injection",
        "Antibiotic",
        "vials",
        300,
        85,
        "Main store B2",
        [("CTX-2406", 510, 260)],
        False,
        False,
    ),
    (
        "metronidazole",
        "Metronidazole",
        "500 mg / 100 mL",
        "Infusion",
        "Antibiotic",
        "bags",
        150,
        40,
        "Main store B3",
        [("MTZ-2403", 200, 420)],
        False,
        False,
    ),
    (
        "insulin-glargine",
        "Insulin glargine",
        "100 units/mL",
        "Pen",
        "Antidiabetic",
        "pens",
        60,
        14,
        "Pharmacy fridge 1 (2–8 °C)",
        [("GLA-2407", 190, 21)],
        True,
        False,
    ),
    (
        "insulin-regular",
        "Insulin regular (soluble)",
        "100 units/mL",
        "Vial",
        "Antidiabetic",
        "vials",
        40,
        9,
        "Pharmacy fridge 1 (2–8 °C)",
        [("INS-2405", 150, 95)],
        True,
        False,
    ),
    (
        "heparin",
        "Heparin",
        "5,000 units/mL",
        "Injection",
        "Anticoagulant",
        "vials",
        150,
        30,
        "High-alert cabinet",
        [("HEP-2402", 330, 410)],
        True,
        False,
    ),
    (
        "enoxaparin",
        "Enoxaparin",
        "40 mg / 0.4 mL",
        "Prefilled syringe",
        "Anticoagulant",
        "syringes",
        200,
        48,
        "High-alert cabinet",
        [("ENX-2406", 400, 640)],
        True,
        False,
    ),
    (
        "kcl",
        "Potassium chloride",
        "15% (2 mmol/mL), 10 mL",
        "Concentrate",
        "Electrolyte",
        "ampoules",
        80,
        12,
        "High-alert cabinet (pharmacy only)",
        [("KCL-2309", 25, 40), ("KCL-2404", 380, 160)],
        True,
        False,
    ),
    (
        "magnesium",
        "Magnesium sulfate",
        "50%",
        "Injection",
        "Electrolyte",
        "ampoules",
        60,
        10,
        "High-alert cabinet",
        [("MGS-2405", 260, 140)],
        True,
        False,
    ),
    (
        "morphine",
        "Morphine",
        "10 mg/mL",
        "Injection",
        "Opioid analgesic",
        "ampoules",
        100,
        22,
        "CD cabinet",
        [("MOR-2403", 230, 84)],
        True,
        True,
    ),
    (
        "pethidine",
        "Pethidine",
        "50 mg/mL",
        "Injection",
        "Opioid analgesic",
        "ampoules",
        40,
        6,
        "CD cabinet",
        [("PTH-2401", 140, 72)],
        True,
        True,
    ),
    (
        "midazolam",
        "Midazolam",
        "5 mg/mL",
        "Injection",
        "Sedative",
        "ampoules",
        60,
        9,
        "CD cabinet",
        [("MDZ-2404", 310, 150)],
        True,
        True,
    ),
    (
        "oxytocin",
        "Oxytocin",
        "10 IU/mL",
        "Injection",
        "Uterotonic",
        "ampoules",
        100,
        25,
        "Pharmacy fridge 2 (2–8 °C)",
        [("OXY-2406", 40, 130), ("OXY-2408", 210, 200)],
        True,
        False,
    ),
    (
        "adrenaline",
        "Adrenaline (epinephrine)",
        "1 mg/mL",
        "Injection",
        "Emergency",
        "ampoules",
        80,
        6,
        "Main store E1 + crash carts",
        [("ADR-2405", 330, 190)],
        True,
        False,
    ),
    (
        "omeprazole",
        "Omeprazole",
        "40 mg",
        "Injection",
        "Gastrointestinal",
        "vials",
        120,
        30,
        "Main store C1",
        [("OMP-2404", 450, 380)],
        False,
        False,
    ),
    (
        "ondansetron",
        "Ondansetron",
        "4 mg / 2 mL",
        "Injection",
        "Antiemetic",
        "ampoules",
        150,
        35,
        "Main store C2",
        [("OND-2402", 75, 120), ("OND-2407", 400, 300)],
        False,
        False,
    ),
    (
        "salbutamol",
        "Salbutamol",
        "2.5 mg / 2.5 mL",
        "Nebule",
        "Respiratory",
        "nebules",
        300,
        70,
        "Main store D1",
        [("SAL-2405", 280, 900)],
        False,
        False,
    ),
    (
        "saline",
        "Sodium chloride",
        "0.9%, 1 L",
        "Infusion",
        "Fluids",
        "bags",
        400,
        110,
        "Fluids store",
        [("NS-2406", 600, 1300)],
        False,
        False,
    ),
    (
        "ringer",
        "Ringer's lactate",
        "1 L",
        "Infusion",
        "Fluids",
        "bags",
        300,
        70,
        "Fluids store",
        [("RL-2405", 560, 640)],
        False,
        False,
    ),
    (
        "txa",
        "Tranexamic acid",
        "500 mg / 5 mL",
        "Injection",
        "Haemostatic",
        "ampoules",
        100,
        18,
        "Main store E2",
        [("TXA-2403", 85, 95)],
        False,
        False,
    ),
    (
        "metformin",
        "Metformin",
        "500 mg",
        "Tablet",
        "Antidiabetic",
        "tablets",
        1500,
        320,
        "Main store A3",
        [("MET-2404", 380, 4100)],
        False,
        False,
    ),
]

LETTERS = "ABDFGHIKMNORSTUYZ"


def weighted(rand: random.Random, shares: dict):
    return rand.choices(list(shares), weights=list(shares.values()))[0]


class Command(BaseCommand):
    help = "Load demo wards, beds, blood units, medicines, doctors and one login per role."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo-module data first.")
        parser.add_argument("--seed", type=int, default=7, help="Random seed, for repeatable data.")

    @transaction.atomic
    def handle(self, *args, reset=False, seed=7, **options):
        rand = random.Random(seed)
        now = timezone.now()
        if reset:
            for model in (Bed, Ward, BloodUnit, Batch, Medicine, DoctorShift):
                model.objects.all().delete()

        self.seed_users()
        if not Ward.objects.exists():
            self.seed_beds(rand, now)
        if not BloodUnit.objects.exists():
            self.seed_blood(rand, now)
        if not Medicine.objects.exists():
            self.seed_pharmacy(now)
        if not DoctorShift.objects.exists():
            DoctorShift.objects.bulk_create(
                DoctorShift(name=n, department=d, start=time.fromisoformat(s), end=time.fromisoformat(e))
                for n, d, s, e in DOCTORS
            )
        er = EmergencyStatus.current()
        if reset or er.wait_minutes == 0:
            er.status, er.wait_minutes, er.waiting_count = ErStatus.ACCEPTING, 24, 7
            er.save()

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"Demo logins (password for all: {DEMO_PASSWORD}):")
        for email, *_, role in DEMO_USERS:
            self.stdout.write(f"  {role:<11} {email}")

    def seed_users(self):
        for email, first, last, role in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=email,
                defaults={"email": email, "first_name": first, "last_name": last, "role": role},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.is_staff = role == Role.ADMIN  # demo admin can open /admin/ too
                user.is_superuser = role == Role.ADMIN
                user.save()

    def seed_beds(self, rand: random.Random, now):
        beds = []
        for order, (code, name, kind, prefix, size, occupancy, (lo, hi)) in enumerate(WARDS):
            ward = Ward.objects.create(code=code, name=name, kind=kind, sort_order=order)
            for n in range(1, size + 1):
                bed = Bed(ward=ward, label=f"{prefix}-{n:02d}", status=BedStatus.FREE)
                bed.status_since = now - timedelta(minutes=rand.randint(10, 600))
                if rand.random() < occupancy:
                    stay = timedelta(minutes=rand.randint(120, 60 * 24 * 12))
                    bed.status = BedStatus.OCCUPIED
                    bed.status_since = bed.admitted_at = now - stay
                    bed.patient_initials = f"{rand.choice(LETTERS)}.{rand.choice(LETTERS)}."
                    bed.patient_age = rand.randint(lo, hi)
                    bed.patient_sex = "F" if code == "maternity" else rand.choice("FM")
                    days = rand.choice([0, 0, 1, 1, 2, 3, 5])
                    bed.expected_discharge = timezone.localdate(now) + timedelta(days=days)
                    if code == "isolation":
                        bed.isolation = rand.choice(["airborne", "droplet", "contact"])
                    elif rand.random() < 0.08:
                        bed.isolation = "contact"
                else:
                    roll = rand.random()
                    if roll < 0.3:
                        bed.status = BedStatus.CLEANING
                        bed.status_since = now - timedelta(minutes=rand.randint(5, 75))
                    elif roll < 0.5:
                        bed.status = BedStatus.RESERVED
                    elif roll >= 0.95:
                        bed.status = BedStatus.OUT_OF_SERVICE
                beds.append(bed)
        Bed.objects.bulk_create(beds)

    def seed_blood(self, rand: random.Random, now, count=320):
        shares = {c: share for c, (_, _, share) in COMPONENTS.items()}
        units = []
        for i in range(count):
            component = weighted(rand, shares)
            shelf_life, locations, _ = COMPONENTS[component]
            age = timedelta(days=rand.random() * shelf_life * 1.04)
            collected = now - age
            expires = collected + timedelta(days=shelf_life)
            roll = rand.random()
            if expires <= now:
                status = UnitStatus.EXPIRED
            elif age < timedelta(days=1):
                status = UnitStatus.QUARANTINED
            elif roll < 0.08:
                status = UnitStatus.RESERVED
            elif roll < 0.11:
                status = UnitStatus.ISSUED
            else:
                status = UnitStatus.AVAILABLE
            units.append(
                BloodUnit(
                    donation_number=f"G7731 26 {100_000 + i * 37:06d}",
                    group=weighted(rand, GROUP_SHARE),
                    component=component,
                    collected_at=collected,
                    expires_at=expires,
                    status=status,
                    location=rand.choice(locations),
                )
            )
        BloodUnit.objects.bulk_create(units)

    def seed_pharmacy(self, now):
        today: date = timezone.localdate(now)
        for (
            code,
            name,
            strength,
            form,
            category,
            unit,
            reorder,
            daily,
            location,
            batches,
            high,
            cd,
        ) in FORMULARY:
            medicine = Medicine.objects.create(
                code=code,
                name=name,
                strength=strength,
                form=form,
                category=category,
                unit=unit,
                reorder_level=reorder,
                daily_use=daily,
                location=location,
                high_alert=high,
                controlled=cd,
            )
            Batch.objects.bulk_create(
                Batch(medicine=medicine, number=n, expires_on=today + timedelta(days=d), quantity=q)
                for n, d, q in batches
            )
