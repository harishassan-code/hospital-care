"""The scenario profiles (B21): for every rate the simulation uses, the range it may take. The engine draws a
fresh value inside each range on every tick, so no two days are alike, but nothing ever leaves its bounds; the
hospitals' capacity (beds, rooms, staff, stock) then limits what can happen. docs/product/simulation.md lists
the same values with their reasons.

Rates are multipliers on each hospital's own size (its emergency arrivals per day, B20 profiles), or shares.
"""

import random
from dataclasses import dataclass, field

R = tuple[float, float]


@dataclass(frozen=True)
class Profile:
    label: str
    arrivals: R  # × the hospital's usual emergency arrivals
    triage: dict  # level → share range (normalised after drawing)
    complaints: dict  # complaint → share range
    admit: dict  # triage level → share admitted
    transfer: R  # share of treated patients sent to another hospital
    leave_unseen: R  # chance per hour that someone of triage 4-5 who has waited over an hour leaves
    treatment_minutes: dict  # triage level → (shortest, longest)
    stay: R  # × the usual length of a ward stay
    occupancy: R  # ward occupancy the hospitals run at
    blood_use: R  # × the usual red-cell use
    donations: R  # × the usual donations
    cancel: R  # share of next day's theatre cases cancelled
    emergency_theatre: R  # unplanned theatre cases per room per day
    absent: R  # share of shifts nobody turns up for
    late: R  # share of shifts started 15-45 minutes late
    cases: R  # new emergency cases (resource requests) per day, whole network
    trip_delay: R  # chance per 5 minutes that a trip under way is held up


# Minutes in the department once seen, by triage level: assessment, tests, treatment and the decision.
TREATMENT = {1: (150, 300), 2: (120, 240), 3: (90, 180), 4: (45, 120), 5: (20, 60)}
ADMIT = {1: 0.7, 2: 0.45, 3: 0.15, 4: 0.04, 5: 0.01}

REGULAR = Profile(
    label="Regular day",
    arrivals=(0.9, 1.1),
    triage={1: (0.005, 0.015), 2: (0.08, 0.12), 3: (0.35, 0.45), 4: (0.25, 0.33), 5: (0.1, 0.18)},
    complaints={
        "respiratory": (0.1, 0.14),
        "cardiac": (0.08, 0.11),
        "trauma": (0.18, 0.24),
        "abdominal": (0.12, 0.16),
        "neurological": (0.05, 0.08),
        "infection": (0.1, 0.14),
        "minor": (0.15, 0.22),
    },
    admit=ADMIT,
    transfer=(0.01, 0.025),
    leave_unseen=(0.03, 0.06),
    treatment_minutes=TREATMENT,
    stay=(0.9, 1.1),
    occupancy=(0.82, 0.9),
    blood_use=(0.85, 1.15),
    donations=(0.9, 1.15),
    cancel=(0.06, 0.12),
    emergency_theatre=(0.15, 0.35),
    absent=(0.015, 0.035),
    late=(0.04, 0.08),
    cases=(3, 6),
    trip_delay=(0.02, 0.05),
)

FLU = Profile(
    label="Flu season",
    arrivals=(1.12, 1.25),
    triage={1: (0.008, 0.02), 2: (0.1, 0.15), 3: (0.4, 0.5), 4: (0.22, 0.3), 5: (0.06, 0.12)},
    complaints={
        "respiratory": (0.3, 0.4),
        "cardiac": (0.07, 0.1),
        "trauma": (0.12, 0.16),
        "abdominal": (0.08, 0.12),
        "neurological": (0.04, 0.07),
        "infection": (0.16, 0.22),
        "minor": (0.08, 0.12),
    },
    admit={1: 0.75, 2: 0.5, 3: 0.19, 4: 0.05, 5: 0.01},
    transfer=(0.02, 0.04),
    leave_unseen=(0.05, 0.09),
    treatment_minutes={k: (lo * 1.05, hi * 1.1) for k, (lo, hi) in TREATMENT.items()},
    stay=(1.2, 1.4),
    occupancy=(0.86, 0.92),  # planned admissions are held back for the emergency ones
    blood_use=(0.9, 1.1),
    donations=(0.65, 0.85),  # donors are ill too
    cancel=(0.12, 0.2),  # beds are short, so planned cases go
    emergency_theatre=(0.15, 0.3),
    absent=(0.04, 0.08),
    late=(0.05, 0.1),
    cases=(4, 8),
    trip_delay=(0.03, 0.06),
)

SLOW = Profile(
    label="Slow day",
    arrivals=(0.6, 0.8),
    triage={1: (0.004, 0.012), 2: (0.07, 0.1), 3: (0.3, 0.4), 4: (0.3, 0.38), 5: (0.15, 0.22)},
    complaints=REGULAR.complaints,
    admit=ADMIT,
    transfer=(0.01, 0.02),
    leave_unseen=(0.02, 0.04),
    treatment_minutes=TREATMENT,
    stay=(0.85, 1.0),
    occupancy=(0.72, 0.8),
    blood_use=(0.6, 0.8),
    donations=(0.7, 0.9),
    cancel=(0.04, 0.08),
    emergency_theatre=(0.08, 0.2),
    absent=(0.01, 0.025),
    late=(0.03, 0.06),
    cases=(1, 3),
    trip_delay=(0.01, 0.03),
)

PROFILES = {"regular": REGULAR, "flu": FLU, "slow": SLOW}


@dataclass(frozen=True)
class MassCasualty:
    """An incident (a building collapse, a bus crash): for 1 to 3 hours, waves of trauma patients at the
    hospitals nearest the site, then the city settles back to its season."""

    hours: R = (1.0, 3.0)
    hospitals: int = 3  # nearest emergency departments that receive patients
    per_hospital_per_hour: R = (12, 30)
    triage: dict = field(
        default_factory=lambda: {1: (0.2, 0.3), 2: (0.35, 0.45), 3: (0.2, 0.3), 4: (0.05, 0.1)}
    )
    blood_use: R = (3.0, 5.0)  # × O- and O+ red-cell use at those hospitals
    emergency_theatre_per_hour: R = (0.3, 0.6)  # per receiving hospital
    cases: R = (2, 4)  # extra emergency cases per hour across the receivers


MASS_CASUALTY = MassCasualty()
# Where an incident can happen: the city's busy districts (centre of each, rounded).
INCIDENT_SITES = [
    (24.8607, 67.0011),  # Saddar
    (24.8138, 67.0300),  # Clifton
    (24.9056, 67.0822),  # Gulshan
    (24.8465, 67.1290),  # Korangi
    (24.9456, 67.0400),  # North Nazimabad
    (24.9200, 66.9900),  # SITE area
]


def draw(rand: random.Random, bounds: R) -> float:
    lo, hi = bounds
    return rand.uniform(lo, hi)


def shares(rand: random.Random, ranges: dict) -> dict:
    """One draw per share, normalised to sum to 1."""
    drawn = {key: rand.uniform(*bounds) for key, bounds in ranges.items()}
    total = sum(drawn.values())
    return {key: value / total for key, value in drawn.items()}


def pick(rand: random.Random, weights: dict):
    return rand.choices(list(weights), weights=list(weights.values()))[0]
