"""What the engine knows about each hospital for one tick (B21): its size, who its emergency department sees,
which wards take whom, and what it keeps. Built once per tick from the database, so a hospital added by an
admin joins the simulation at the next tick."""

import random
import zlib
from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType

from apps.blood.models import BloodUnit
from apps.core.seed.profiles import EXTRA_WARDS, PROFILES
from apps.hospitals.models import Bed, BedType, Hospital, Ward
from apps.matching.models import ACTIVE, Reservation
from apps.operating_rooms.models import OperatingRoom

# Ages each demo ward takes, from the seed's ward lists; a ward added later takes adults.
FEMALE_KINDS = ("obstetric", "postnatal", "labour", "gynaecology", "maternity")
DEFAULT_AGES = (14, 95)


def _ward_ages() -> dict:
    from apps.core.management.commands import seed_demo  # the seed's ward lists; imported late

    specs = [w for h in seed_demo.HOSPITALS for w in h[9]] + [w for ws in EXTRA_WARDS.values() for w in ws]
    return {code: ages for code, _, _, _, _, _, ages, _ in specs}


@dataclass
class WardRule:
    lo: int
    hi: int
    female_only: bool

    def fits(self, age: int, sex: str) -> bool:
        return self.lo <= age <= self.hi and (sex == "F" or not self.female_only)


@dataclass
class Site:
    hospital: Hospital
    arrivals_per_day: float  # usual emergency arrivals
    population: str  # "general", "children" or "women": who its emergency department sees
    er_department: str | None  # the department its emergency beds belong to
    er_beds: int
    blood_per_day: float  # usual red-cell units used a day (0: keeps no blood)
    donations_per_day: float  # donations it takes a day
    rooms: int
    wards: dict = field(default_factory=dict)  # ward id → WardRule (wards with beds other than emergency)


def stable(*key) -> random.Random:
    """A random stream fixed by `key` (e.g. a bed and when it started cleaning), so a draw made for one thing
    gives the same answer on every tick: a bed's cleaning time is decided once, not re-rolled."""
    return random.Random(zlib.crc32(":".join(str(k) for k in key).encode()))


def held_ids(model) -> set[int]:
    """Ids of `model` rows held or allocated for a case: the simulation never moves them."""
    return set(
        Reservation.objects.filter(
            content_type=ContentType.objects.get_for_model(model), status__in=ACTIVE
        ).values_list("object_id", flat=True)
    )


def build_sites() -> list[Site]:
    ages = _ward_ages()
    sites = []
    hospitals = Hospital.objects.filter(is_active=True).order_by("id")
    for hospital in hospitals:
        profile = PROFILES.get(hospital.name)
        wards = {}
        er_department, er_beds = None, 0
        for ward in Ward.objects.filter(hospital=hospital).select_related("department"):
            types = set(ward.beds.values_list("bed_type", flat=True))
            if not types:
                continue
            if BedType.EMERGENCY in types:
                er_department = ward.department.name if ward.department else er_department
                er_beds += ward.beds.filter(bed_type=BedType.EMERGENCY).count()
                continue
            lo, hi = ages.get(ward.code, DEFAULT_AGES)
            female = any(word in f"{ward.kind} {ward.name}".lower() for word in FEMALE_KINDS)
            wards[ward.pk] = WardRule(lo, hi, female)
        adult = [r for r in wards.values() if r.hi > 17]
        children = [r for r in wards.values() if r.hi <= 17]
        if wards and not adult:
            population = "children"
        elif adult and all(r.female_only for r in adult) and len(children) <= 1:
            population = "women"
        else:
            population = "general"
        per_day = profile.er_arrivals_per_day if profile else max(20, er_beds * 4)
        units = profile.blood_units if profile and profile.blood_units else 0
        if not units:
            units = BloodUnit.objects.filter(hospital=hospital).count() if hospital.type != "bloodBank" else 0
        blood_bank = hospital.type == "bloodBank"
        use = 0.0 if not units else units * 0.6 / (24 if blood_bank else 9)
        sites.append(
            Site(
                hospital=hospital,
                arrivals_per_day=per_day if er_beds else 0,
                population=population,
                er_department=er_department,
                er_beds=er_beds,
                blood_per_day=use,
                donations_per_day=use * 0.6,  # balances use on average (blood.components)
                rooms=OperatingRoom.objects.filter(hospital=hospital).count(),
                wards=wards,
            )
        )
    return sites


def emergency_beds_free(site: Site, held: set[int]):
    return (
        Bed.objects.filter(hospital=site.hospital, bed_type=BedType.EMERGENCY, status="free")
        .exclude(pk__in=held)
        .order_by("label")
    )
