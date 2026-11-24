"""How long a new emergency patient can expect to wait (B21), from what is happening in the department now,
and which factors made it longer. The simulation sets each hospital's EmergencyStatus from this; staff see the
factors on their emergency page.

The model, in short: a department is staffed to see about 1.55 times its usual hourly arrivals. It goes at
that pace with the doctors and nurses its rota plans, slower with fewer (an absent doctor, a late nurse), and
never faster than its free emergency beds allow. A new patient of middling priority (triage 3) waits behind
everyone of the same or higher priority, plus the arrivals of the next half hour that it can't absorb.
Thresholds for "very busy" and "not accepting ambulances" are the ones the history uses (B20). Values are in
docs/product/simulation.md.
"""

from dataclasses import dataclass, field, replace

from .models import ErStatus

SIZED_FOR = 1.55  # a department is staffed for 1.55 times its usual arrivals per hour
MAX_STAFF_SHARE = 1.25  # extra staff on a shift help, up to a quarter faster
MEAN_TREATMENT_HOURS = 1.75  # the average of the treatment times by triage level (apps/simulation/profiles)
TRIAGE_MINUTES = 10  # registration and triage, even when nobody is waiting
CHAIRS = 6  # places a minor complaint is seen without a bed
COVER = 0.5  # with no emergency doctor clocked in, a doctor from a ward covers, at half pace
FAST_TRACK_PER_DAY = 40  # a fast-track place (minor complaints, in a chair) per 40 usual arrivals a day
MAX_WAIT_MINUTES = 24 * 60


def er_wait_minutes(arrivals_per_hour: float, capacity_per_hour: float) -> float:
    """The average wait for how busy a department is (load = arrivals over what it can see in an hour): about
    a quarter of an hour when quiet, rising steeply as the load passes 1, at most four hours. Used by the
    history (B20) and by a fast-forward, which runs hour by hour without individual patients."""
    load = arrivals_per_hour / capacity_per_hour if capacity_per_hour else 1.0
    return min(240.0, 15 + 30 * load**3)


def er_status_for(waiting: int, wait: int, er_beds: int) -> str:
    """Not accepting ambulances at a wait of 2½ hours or 1½ patients waiting per bed; very busy from an hour
    or one per bed."""
    if wait >= 150 or waiting >= er_beds * 1.5:
        return ErStatus.DIVERTING
    if wait >= 60 or waiting >= er_beds:
        return ErStatus.BUSY
    return ErStatus.ACCEPTING


@dataclass(frozen=True)
class Inputs:
    """What the department looks like now."""

    waiting: dict = field(default_factory=dict)  # triage level → patients waiting
    doctors: int = 0  # emergency doctors clocked in
    doctors_rostered: int = 0  # planned for this shift
    nurses: int = 0
    nurses_rostered: int = 0
    beds: int = 0  # emergency beds in service
    beds_free: int = 0
    boarding: int = 0  # admitted patients still in an emergency bed
    arrivals_last_hour: int = 0
    usual_per_day: float = 0  # the department's usual arrivals a day, which its staffing is sized for


def capacity_per_hour(inputs: Inputs) -> float:
    """Patients the department can finish in an hour with the staff and beds it has."""
    base = SIZED_FOR * (inputs.usual_per_day or 24 * 4) / 24
    doctors = max(inputs.doctors, COVER) / max(1, inputs.doctors_rostered)
    nurses = min(1.0, inputs.nurses / max(1, inputs.nurses_rostered))
    rate = base * min(MAX_STAFF_SHARE, doctors) * (0.6 + 0.4 * nurses)
    beds = max(1, inputs.beds - inputs.boarding + CHAIRS) / MEAN_TREATMENT_HOURS
    return max(0.5, min(rate, beds))


def minutes(inputs: Inputs) -> int:
    rate = capacity_per_hour(inputs)
    ahead = sum(n for level, n in inputs.waiting.items() if int(level) <= 3)
    ahead += 0.25 * sum(n for level, n in inputs.waiting.items() if int(level) > 3)
    surge = max(0.0, inputs.arrivals_last_hour - rate) * 0.5
    return min(MAX_WAIT_MINUTES, round(TRIAGE_MINUTES + (ahead + surge) / rate * 60))


@dataclass(frozen=True)
class Estimate:
    minutes: int
    waiting: int
    status: str
    factors: list  # [{"key", "label", "value", "minutes"}], biggest effect first


def estimate(inputs: Inputs) -> Estimate:
    """The wait, and how many minutes each factor added compared with a normal department: full staff, no
    one boarding, arrivals the department can absorb, nobody waiting."""
    wait = minutes(inputs)
    waiting = sum(inputs.waiting.values())
    normal = {
        "queue": replace(inputs, waiting={}),
        "doctors": replace(inputs, doctors=max(inputs.doctors, inputs.doctors_rostered)),
        "nurses": replace(inputs, nurses=max(inputs.nurses, inputs.nurses_rostered)),
        "boarding": replace(inputs, boarding=0),
        "arrivals": replace(inputs, arrivals_last_hour=0),
    }
    labels = {
        "queue": ("Patients waiting", waiting),
        "doctors": ("Emergency doctors on duty", f"{inputs.doctors} of {inputs.doctors_rostered}"),
        "nurses": ("Emergency nurses on duty", f"{inputs.nurses} of {inputs.nurses_rostered}"),
        "boarding": ("Admitted patients waiting for a ward bed", inputs.boarding),
        "arrivals": ("Arrivals in the last hour", inputs.arrivals_last_hour),
    }
    factors = [
        {
            "key": key,
            "label": labels[key][0],
            "value": labels[key][1],
            "minutes": max(0, wait - minutes(other)),
        }
        for key, other in normal.items()
    ]
    factors.append(
        {
            "key": "beds",
            "label": "Free emergency beds",
            "value": f"{inputs.beds_free} of {inputs.beds}",
            "minutes": 0,
        }
    )
    factors.sort(key=lambda f: -f["minutes"])
    # Diversion is about room for serious patients: someone with a minor complaint counts a quarter.
    urgent = sum(n for level, n in inputs.waiting.items() if int(level) <= 3)
    weighted = round(urgent + 0.25 * (waiting - urgent))
    return Estimate(wait, waiting, er_status_for(weighted, wait, inputs.beds or 1), factors)
