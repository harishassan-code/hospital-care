"""Story #37: blood compatibility rules and the network-wide search for compatible units."""

import itertools
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.utils import timezone

from apps.blood.models import BloodUnit, UnitStatus
from apps.matching import compatibility
from apps.matching.compatibility import RULES_PATH, compatible_donors, compatible_units, load_rules

pytestmark = pytest.mark.django_db

GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
COMPONENTS = ["redCells", "plasma", "platelets", "cryo"]

# ── The expected matrix, written from docs/domain/blood-compatibility.md, not read from the JSON ──────

# Red cells: no ABO antigen the donor has that the recipient lacks; RhD-negative recipients get RhD-negative.
# Plasma (and cryo, which uses the plasma rule): the donor's ABO antigens must cover the recipient's.
# Platelets: the doc's table, best option then "Acceptable" groups. RhD is not a match rule; it is flagged.
ANTIGENS = {"O": set(), "A": {"A"}, "B": {"B"}, "AB": {"A", "B"}}
PLATELET_TABLE = {
    "O": ("O", {"A", "B"}),
    "A": ("A", {"B", "O"}),
    "B": ("B", {"A", "O"}),
    "AB": ("AB", {"A", "B", "O"}),
}


def rh_positive(group: str) -> bool:
    return group.endswith("+")


def abo(group: str) -> str:
    return group[:-1]


def expected_compatible(component: str, recipient: str, donor: str) -> bool:
    if component == "redCells":
        antigens_ok = ANTIGENS[abo(donor)] <= ANTIGENS[abo(recipient)]
        rh_ok = rh_positive(recipient) or not rh_positive(donor)
        return antigens_ok and rh_ok
    if component in ("plasma", "cryo"):
        return ANTIGENS[abo(recipient)] <= ANTIGENS[abo(donor)]
    best, acceptable = PLATELET_TABLE[abo(recipient)]
    return abo(donor) == best or abo(donor) in acceptable


def expected_flag(component: str, recipient: str, donor: str) -> bool:
    return component == "platelets" and rh_positive(donor) and not rh_positive(recipient)


# ── Rules: every component x recipient x donor (4 x 8 x 8 = 256) ─────────────────────────────────


@pytest.mark.parametrize(
    ("component", "recipient", "donor"),
    list(itertools.product(COMPONENTS, GROUPS, GROUPS)),
)
def test_donor_is_compatible_exactly_as_the_doc_says(component, recipient, donor):
    donors = {option.group for option in compatible_donors(recipient, component)}
    assert (donor in donors) == expected_compatible(component, recipient, donor)


@pytest.mark.parametrize(("component", "recipient"), list(itertools.product(COMPONENTS, GROUPS)))
def test_identical_group_ranks_first_and_ranks_are_in_order(component, recipient):
    donors = compatible_donors(recipient, component)
    assert donors[0].group == recipient
    assert donors[0].rank == 0
    assert [option.rank for option in donors] == list(range(len(donors)))


def test_platelet_rh_flag_is_set_exactly_for_rh_positive_donor_to_rh_negative_recipient():
    for component in COMPONENTS:
        for recipient, donor in itertools.product(GROUPS, GROUPS):
            if not expected_compatible(component, recipient, donor):
                continue
            option = next(o for o in compatible_donors(recipient, component) if o.group == donor)
            assert option.rh_flag == expected_flag(component, recipient, donor), (component, recipient, donor)


def test_red_cell_order_puts_the_universal_reserve_last():
    # O- is last for every recipient that can take it, as the universal reserve.
    for recipient in GROUPS:
        donors = [option.group for option in compatible_donors(recipient, "redCells")]
        if "O-" in donors:
            assert donors[-1] == "O-", recipient


def test_unknown_recipient_or_component_is_a_value_error():
    with pytest.raises(ValueError, match="recipient group"):
        compatible_donors("Z+", "redCells")
    with pytest.raises(ValueError, match="component"):
        compatible_donors("A+", "bone")
    with pytest.raises(ValueError):
        compatible_units("Z+", "redCells")
    with pytest.raises(ValueError):
        compatible_units("A+", "bone")


# ── Loader validation ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_rules():
    """load_rules is cached per path. A test that changes the default path must start with an empty cache."""
    load_rules.cache_clear()
    yield
    load_rules.cache_clear()


def write_rules(tmp_path: Path, mutate) -> Path:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    mutate(data["components"])
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_shipped_file_loads():
    assert set(load_rules()) == set(COMPONENTS)


def test_a_missing_recipient_group_is_rejected(tmp_path):
    path = write_rules(tmp_path, lambda c: c["redCells"].pop("AB+"))
    with pytest.raises(ImproperlyConfigured, match="missing AB\\+"):
        load_rules(path)


def test_a_bad_donor_group_is_rejected(tmp_path):
    path = write_rules(tmp_path, lambda c: c["plasma"]["O-"].append("Z+"))
    with pytest.raises(ImproperlyConfigured, match="unknown donor group 'Z\\+'"):
        load_rules(path)


def test_a_duplicate_donor_is_rejected(tmp_path):
    path = write_rules(tmp_path, lambda c: c["redCells"]["A+"].append("A-"))
    with pytest.raises(ImproperlyConfigured, match="more than once"):
        load_rules(path)


def test_identical_group_not_first_is_rejected(tmp_path):
    def swap(c):
        c["redCells"]["A+"][0], c["redCells"]["A+"][1] = c["redCells"]["A+"][1], c["redCells"]["A+"][0]

    path = write_rules(tmp_path, swap)
    with pytest.raises(ImproperlyConfigured, match="must start with the identical group A\\+"):
        load_rules(path)


def test_an_unreadable_file_is_rejected(tmp_path):
    with pytest.raises(ImproperlyConfigured, match="can't be read"):
        load_rules(tmp_path / "missing.json")


def test_the_system_check_passes_on_the_shipped_file(fresh_rules):
    call_command("check")


def test_the_system_check_fails_on_a_broken_file(tmp_path, monkeypatch, fresh_rules):
    broken = write_rules(tmp_path, lambda c: c["redCells"].pop("AB+"))
    monkeypatch.setattr(compatibility, "RULES_PATH", broken)
    with pytest.raises(SystemCheckError, match="matching.E001"):
        call_command("check")


# ── compatible_units: network-wide, usable only, ranked ───────────────────────────────────────────

_numbers = itertools.count(1)


def make_unit(
    hospital, group, component="redCells", *, status=UnitStatus.AVAILABLE, expires_in=30, expires_at=None
):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=f"M{next(_numbers)}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=now - timedelta(days=10),
        expires_at=expires_at or now + timedelta(days=expires_in),
        status=status,
        location="Blood fridge 1",
    )


def test_finds_usable_compatible_units_at_every_hospital(make_hospital):
    here, there, third = make_hospital(name="Here"), make_hospital(name="There"), make_hospital(name="Third")
    a = make_unit(here, "O+")
    b = make_unit(there, "A+")
    c = make_unit(third, "O-")
    found = {u.id for u in compatible_units("A+", "redCells")}
    assert found == {a.id, b.id, c.id}


def test_excludes_units_that_are_not_usable(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    keep = make_unit(there, "O-")
    for status in (
        UnitStatus.QUARANTINED,
        UnitStatus.RESERVED,
        UnitStatus.ISSUED,
        UnitStatus.DISCARDED,
        UnitStatus.EXPIRED,
    ):
        make_unit(there, "O-", status=status)
    make_unit(there, "O-", expires_in=-1)  # still marked available, but past its expiry date
    make_unit(there, "A+", "plasma")  # right group, other component
    make_unit(there, "B+")  # wrong group for an A+ patient
    make_unit(there, "AB-")  # wrong group for an A+ patient
    make_unit(here, "A+", "platelets")  # other component
    assert [u.id for u in compatible_units("A+", "redCells")] == [keep.id]


def test_exclude_hospital_id_drops_the_requesting_hospital(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    make_unit(here, "O+")
    kept = make_unit(there, "O+")
    assert [u.id for u in compatible_units("A+", "redCells", exclude_hospital_id=here.id)] == [kept.id]


def test_orders_by_donor_rank_then_earliest_expiry_then_id(make_hospital):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    a_plus_3d = make_unit(there, "A+", expires_in=3)  # rank 0
    a_plus_tie_1 = make_unit(here, "A+", expires_in=4)  # rank 0
    a_plus_tie_2 = make_unit(there, "A+", expires_at=a_plus_tie_1.expires_at)  # rank 0, same expiry
    a_plus_5d = make_unit(here, "A+", expires_in=5)  # rank 0
    a_minus_1d = make_unit(there, "A-", expires_in=1)  # rank 1: expires soonest, but ranks after the A+ units
    o_plus_2d = make_unit(here, "O+", expires_in=2)  # rank 2
    o_minus_1d = make_unit(there, "O-", expires_in=1)  # rank 3
    ordered = [u.id for u in compatible_units("A+", "redCells")]
    assert ordered == [
        a_plus_3d.id,
        a_plus_tie_1.id,
        a_plus_tie_2.id,
        a_plus_5d.id,
        a_minus_1d.id,
        o_plus_2d.id,
        o_minus_1d.id,
    ]


def test_each_unit_carries_its_donor_rank(make_hospital):
    here = make_hospital()
    make_unit(here, "O-")
    (unit,) = compatible_units("A+", "redCells")
    assert unit.donor_rank == 3


def test_the_search_is_one_query(make_hospital, django_assert_num_queries):
    here, there = make_hospital(name="Here"), make_hospital(name="There")
    make_unit(here, "A+")
    make_unit(there, "O-")
    with django_assert_num_queries(1):
        list(compatible_units("A+", "redCells", exclude_hospital_id=here.id))
