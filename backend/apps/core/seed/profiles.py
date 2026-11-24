"""The CityCare demo network (B20): ten made-up hospitals in real Karachi areas, and what each one has.

Names are invented (checked against the hospitals listed for Karachi, 23 Nov 2026), addresses are areas, not
buildings, and every person is synthetic. The first three hospitals are the ones the demo scenario and the
end-to-end test were written for: their scenario stock stays exactly as it was, and they gain the wards,
rooms and equipment a hospital of their kind would have. docs/product/demo-data.md gives the proportions and
their sources.
"""

from dataclasses import dataclass, field

from apps.equipment.models import EquipmentType
from apps.hospitals.models import BedType

# ── The seven new hospitals ─────────────────────────────────────────────────────────────────────────────
# Same shape as seed_demo.HOSPITALS: name, type, address, latitude, longitude, phone, capabilities,
# departments, storage locations, wards (code, name, kind, label prefix, size, occupancy, (min age, max age),
# department).

EM, GM, SURG, PAEDS, OBS = "Emergency medicine", "General medicine", "Surgery", "Paediatrics", "Obstetrics"

NEW_HOSPITALS = [
    (
        "Eastgate Trauma Centre",
        "hospital",
        "Korangi Industrial Area, Karachi",
        "24.831500",
        "67.126800",
        "+92 21 111 000 444",
        ["trauma", "icu", "bloodBank", "ct", "burns"],
        [EM, "Trauma surgery", "Orthopaedics", "Neurosurgery", "Burns"],
        ["Blood fridge", "Plasma freezer", "Main store"],
        [
            ("et-ed", "Emergency", "Emergency department", "ET-ED", 36, 0.8, (5, 90), EM),
            ("et-icu", "Trauma ICU", "Intensive care", "ET-ICU", 14, 0.93, (14, 85), "Trauma surgery"),
            ("et-trauma", "Trauma ward", "Trauma surgery", "ET-TR", 40, 0.9, (10, 85), "Trauma surgery"),
            ("et-ortho", "Orthopaedics", "Orthopaedic surgery", "ET-OR", 36, 0.91, (10, 90), "Orthopaedics"),
            ("et-neuro", "Neurosurgery", "Neurosurgery", "ET-NS", 20, 0.88, (10, 85), "Neurosurgery"),
            ("et-burns", "Burns unit", "Burns care", "ET-BU", 14, 0.85, (1, 80), "Burns"),
        ],
    ),
    (
        "Lotus Women's Hospital",
        "hospital",
        "Gulshan-e-Iqbal Block 13, Karachi",
        "24.922300",
        "67.093400",
        "+92 21 111 000 555",
        ["maternity", "nicu", "bloodBank"],
        [EM, OBS, "Gynaecology", "Neonatology"],
        ["Blood fridge", "Main store"],
        [
            ("lw-ed", "Obstetric emergency", "Emergency department", "LW-ED", 10, 0.6, (16, 45), EM),
            ("lw-labour", "Labour ward", "Labour and delivery", "LW-LD", 16, 0.75, (16, 45), OBS),
            ("lw-mat", "Maternity", "Postnatal care", "LW-MT", 44, 0.86, (16, 45), OBS),
            ("lw-gyn", "Gynaecology", "Gynaecology", "LW-GY", 24, 0.8, (16, 70), "Gynaecology"),
            ("lw-nicu", "NICU", "Neonatal intensive care", "LW-NICU", 16, 0.9, (0, 0), "Neonatology"),
        ],
    ),
    (
        "Harbourline District Hospital",
        "hospital",
        "Kemari Town, Karachi",
        "24.818900",
        "66.986100",
        "+92 21 111 000 666",
        ["icu", "paediatrics", "maternity"],
        [EM, GM, SURG, PAEDS, OBS],
        ["Blood fridge", "Main store"],
        [
            ("hl-ed", "Emergency", "Emergency department", "HL-ED", 20, 0.78, (1, 90), EM),
            ("hl-icu", "ICU", "Intensive care", "HL-ICU", 6, 0.95, (16, 85), GM),
            ("hl-med", "Medical", "General medicine", "HL-MED", 36, 0.94, (16, 92), GM),
            ("hl-surg", "Surgical", "General surgery", "HL-SRG", 28, 0.9, (14, 88), SURG),
            ("hl-paeds", "Children's ward", "Children", "HL-PD", 20, 0.88, (1, 14), PAEDS),
            ("hl-mat", "Maternity", "Obstetrics", "HL-MT", 20, 0.9, (16, 45), OBS),
        ],
    ),
    (
        "Orangi Hills Hospital",
        "hospital",
        "Orangi Town Sector 11, Karachi",
        "24.951200",
        "66.998700",
        "+92 21 111 000 777",
        ["paediatrics", "maternity"],
        [EM, GM, SURG, PAEDS, OBS],
        ["Main store"],
        [
            ("oh-ed", "Emergency", "Emergency department", "OH-ED", 16, 0.82, (1, 90), EM),
            ("oh-med", "Medical", "General medicine", "OH-MED", 30, 0.95, (16, 92), GM),
            ("oh-surg", "Surgical", "General surgery", "OH-SRG", 20, 0.9, (14, 88), SURG),
            ("oh-paeds", "Children's ward", "Children", "OH-PD", 16, 0.9, (1, 14), PAEDS),
            ("oh-mat", "Maternity", "Obstetrics", "OH-MT", 14, 0.9, (16, 45), OBS),
        ],
    ),
    (
        "Malir Valley Hospital",
        "hospital",
        "Malir Cantonment Road, Karachi",
        "24.893900",
        "67.198400",
        "+92 21 111 000 888",
        ["icu", "dialysis", "bloodBank", "paediatrics"],
        [EM, GM, SURG, "Nephrology", PAEDS],
        ["Blood fridge", "Main store"],
        [
            ("mv-ed", "Emergency", "Emergency department", "MV-ED", 18, 0.76, (1, 90), EM),
            ("mv-icu", "ICU", "Intensive care", "MV-ICU", 8, 0.9, (16, 85), GM),
            ("mv-med", "Medical", "General medicine", "MV-MED", 34, 0.92, (16, 92), GM),
            ("mv-surg", "Surgical", "General surgery", "MV-SRG", 26, 0.88, (14, 88), SURG),
            ("mv-renal", "Renal unit", "Nephrology", "MV-RU", 12, 0.85, (18, 85), "Nephrology"),
            ("mv-paeds", "Children's ward", "Children", "MV-PD", 18, 0.85, (1, 14), PAEDS),
        ],
    ),
    (
        "Bahadurabad Medical Centre",
        "hospital",
        "Bahadurabad, Karachi",
        "24.882900",
        "67.069600",
        "+92 21 111 000 999",
        ["icu", "ct", "mri", "cathLab", "dialysis", "bloodBank"],
        [EM, GM, SURG, "Cardiology", "Nephrology"],
        ["Blood fridge", "Main store"],
        [
            ("bm-ed", "Emergency", "Emergency department", "BM-ED", 10, 0.5, (1, 90), EM),
            ("bm-icu", "ICU", "Intensive care", "BM-ICU", 10, 0.8, (16, 90), GM),
            ("bm-med", "Medical", "General medicine", "BM-MED", 26, 0.74, (16, 92), GM),
            ("bm-surg", "Surgical", "General surgery", "BM-SRG", 24, 0.72, (14, 88), SURG),
            ("bm-card", "Cardiology", "Cardiology", "BM-CD", 16, 0.75, (30, 90), "Cardiology"),
            ("bm-private", "Private rooms", "Private rooms", "BM-PR", 20, 0.65, (16, 92), GM),
        ],
    ),
    (
        "Metro Blood Centre",
        "bloodBank",
        "Saddar, Karachi",
        "24.856900",
        "67.028700",
        "+92 21 111 001 000",
        ["bloodBank"],
        ["Transfusion medicine"],
        ["Blood fridge 1", "Blood fridge 2", "Plasma freezer", "Platelet agitator", "Main store"],
        [],
    ),
]

# ── Wards the first three hospitals gain (seeded from their own random stream, so nothing before changes) ──

EXTRA_WARDS = {
    "CityCare General Hospital": [
        ("ed", "Emergency", "Emergency department", "ED", 24, 0.75, (1, 92), EM),
        ("medB", "Medical B", "General medicine", "MB", 30, 0.93, (18, 92), GM),
        ("surgA", "Surgical A", "General surgery", "SA", 24, 0.86, (16, 88), SURG),
        ("ortho", "Orthopaedics", "Orthopaedic surgery", "ORT", 24, 0.88, (12, 90), SURG),
    ],
    "Seaview Hospital": [
        ("sv-card", "Cardiology", "Cardiology", "SV-CW", 32, 0.88, (30, 90), "Cardiology"),
        ("sv-csurg", "Cardiac surgery", "Cardiac surgery", "SV-CS", 20, 0.85, (25, 85), "Cardiac surgery"),
    ],
    "Northside Children's Hospital": [
        ("ns-er", "Children's emergency", "Emergency department", "NS-ED", 14, 0.7, (0, 14), PAEDS),
        ("ns-picu", "PICU", "Paediatric intensive care", "NS-PICU", 10, 0.9, (0, 14), PAEDS),
        ("ns-burns", "Burns unit", "Burns care", "NS-BU", 12, 0.83, (0, 14), PAEDS),
        ("ns-surg", "Children's surgery", "Paediatric surgery", "NS-PS", 16, 0.82, (0, 14), PAEDS),
    ],
}
# Departments the first three gain for those wards.
EXTRA_DEPARTMENTS = {"Seaview Hospital": ["Cardiac surgery"]}

# Ward code → bed type for the wards above; anything else is general (as in seed_demo).
WARD_BED_TYPES = {
    **{
        code: BedType.EMERGENCY
        for code in ("ed", "ns-er", "et-ed", "lw-ed", "hl-ed", "oh-ed", "mv-ed", "bm-ed")
    },
    **{code: BedType.ICU for code in ("ns-picu", "et-icu", "hl-icu", "mv-icu", "bm-icu")},
    "lw-nicu": BedType.NICU,
}


@dataclass(frozen=True)
class Profile:
    """What a hospital has besides beds. `code` prefixes its equipment and ambulance tags."""

    code: str
    equipment: dict = field(default_factory=dict)  # type → how many in total
    rooms: tuple = ()  # (name, capabilities, location)
    ambulances: tuple = ()  # (type, how many)
    blood_units: int = 0  # 0: keeps no blood
    donors: int = 0
    er_arrivals_per_day: int = 0  # for the history and the simulation (B21)


V, M, D, DI = (
    EquipmentType.VENTILATOR,
    EquipmentType.MONITOR,
    EquipmentType.DEFIBRILLATOR,
    EquipmentType.DIALYSIS,
)
GEN, CARD, TRAUMA, NEURO, ORTHO, OBST, PAED = (
    "general",
    "cardiac",
    "trauma",
    "neuro",
    "orthopedic",
    "obstetric",
    "pediatric",
)

PROFILES = {
    # The first three: totals including what seed_demo already gives them (main: 5 ventilators, 4 monitors,
    # 3 defibrillators, 3 dialysis machines and 3 rooms; partners: a ventilator, a monitor and 3 rooms).
    "CityCare General Hospital": Profile(
        "CG",
        equipment={V: 14, M: 24, D: 8, DI: 6},
        rooms=(
            ("OR 2", [GEN], "Block B, floor 2"),
            ("OR 3", [GEN], "Block B, floor 2"),
            ("Orthopaedic theatre", [ORTHO, TRAUMA], "Block B, floor 2"),
            ("Obstetric theatre", [OBST], "Maternity block"),
            ("Paediatric theatre", [PAED, GEN], "Block C, floor 1"),
            ("Neuro theatre", [NEURO, TRAUMA], "Block B, floor 3"),
        ),
        ambulances=(("advanced", 2), ("basic", 2)),
        er_arrivals_per_day=210,
    ),
    "Seaview Hospital": Profile(
        "SV",
        equipment={V: 12, M: 30, D: 8},
        rooms=(("Cardiac theatre 2", [CARD, GEN], "Block A, floor 3"),),
        ambulances=(("advanced", 1),),
        blood_units=90,
        er_arrivals_per_day=70,
    ),
    "Northside Children's Hospital": Profile(
        "NS",
        equipment={V: 14, M: 22, D: 5},
        rooms=(
            ("Paediatric theatre 1", [PAED, GEN], "Theatre suite"),
            ("Paediatric theatre 2", [PAED], "Theatre suite"),
        ),
        ambulances=(("basic", 1),),
        blood_units=70,
        er_arrivals_per_day=95,
    ),
    "Eastgate Trauma Centre": Profile(
        "ET",
        equipment={V: 18, M: 34, D: 10, DI: 2},
        rooms=(
            ("Trauma theatre 1", [TRAUMA, GEN], "Emergency block"),
            ("Trauma theatre 2", [TRAUMA, ORTHO], "Emergency block"),
            ("Orthopaedic theatre", [ORTHO], "Theatre suite"),
            ("Neuro theatre", [NEURO, TRAUMA], "Theatre suite"),
            ("Burns theatre", [GEN], "Burns unit"),
        ),
        ambulances=(("advanced", 3), ("basic", 3)),
        blood_units=220,
        donors=40,
        er_arrivals_per_day=240,
    ),
    "Lotus Women's Hospital": Profile(
        "LW",
        equipment={V: 10, M: 20, D: 4},
        rooms=(
            ("Obstetric theatre 1", [OBST], "Labour suite"),
            ("Obstetric theatre 2", [OBST], "Labour suite"),
            ("Gynae theatre", [GEN], "Theatre suite"),
        ),
        ambulances=(("advanced", 1), ("basic", 1)),
        blood_units=140,
        donors=30,
        er_arrivals_per_day=45,
    ),
    "Harbourline District Hospital": Profile(
        "HL",
        equipment={V: 6, M: 12, D: 6},
        rooms=(
            ("OR 1", [GEN], "Main block"),
            ("OR 2", [GEN, OBST], "Main block"),
            ("Emergency theatre", [GEN, TRAUMA], "Emergency"),
        ),
        ambulances=(("basic", 2), ("patientTransport", 1)),
        er_arrivals_per_day=150,
    ),
    "Orangi Hills Hospital": Profile(
        "OH",
        equipment={V: 2, M: 8, D: 4},
        rooms=(("OR 1", [GEN, OBST], "Main block"), ("OR 2", [GEN], "Main block")),
        ambulances=(("basic", 2),),
        er_arrivals_per_day=130,
    ),
    "Malir Valley Hospital": Profile(
        "MV",
        equipment={V: 8, M: 16, D: 6, DI: 8},
        rooms=(
            ("OR 1", [GEN], "Main block"),
            ("OR 2", [GEN, ORTHO], "Main block"),
            ("OR 3", [GEN, PAED], "Main block"),
        ),
        ambulances=(("advanced", 1), ("basic", 2)),
        blood_units=90,
        donors=20,
        er_arrivals_per_day=120,
    ),
    "Bahadurabad Medical Centre": Profile(
        "BM",
        equipment={V: 10, M: 24, D: 6, DI: 6},
        rooms=(
            ("OR 1", [GEN], "Floor 4"),
            ("OR 2", [GEN, ORTHO], "Floor 4"),
            ("Cardiac theatre", [CARD], "Floor 5"),
        ),
        ambulances=(("advanced", 1), ("patientTransport", 1)),
        blood_units=120,
        donors=25,
        er_arrivals_per_day=55,
    ),
    "Metro Blood Centre": Profile("MB", blood_units=600, donors=150),
}
