"""Blood compatibility (story #37): which donor groups may give each component to each recipient group.

The rules are data in blood_compatibility.json, which copies the "System rule" lines of
docs/domain/blood-compatibility.md. This module loads and validates that file and finds the usable units that
match it. Nothing else holds a copy of the rules. The frontend's drift test checks red cells and plasma.

These are a coordination aid's rules. The hospital laboratory still confirms every transfusion.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Case, IntegerField, Value, When

from apps.blood.models import BloodGroup, BloodUnit, Component
from apps.blood.services import usable_units

RULES_PATH = Path(__file__).with_name("blood_compatibility.json")


@dataclass(frozen=True)
class DonorOption:
    group: str
    rank: int  # 0 is the best option: the identical group
    # True: an RhD-positive platelet for an RhD-negative recipient. Allowed, but flagged for a clinician.
    rh_flag: bool


Rules = dict[str, dict[str, tuple[DonorOption, ...]]]


@lru_cache
def load_rules(path: Path | str | None = None) -> Rules:
    """The rules from the JSON file (default: blood_compatibility.json), validated and cached per path.
    Raises ImproperlyConfigured naming the file and the problem if anything is wrong."""
    path = Path(path) if path else RULES_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ImproperlyConfigured(f"Blood compatibility rules {path} can't be read: {exc}") from exc
    return _parse(data, path)


def _parse(data, path: Path) -> Rules:
    def bad(problem: str) -> ImproperlyConfigured:
        return ImproperlyConfigured(f"Blood compatibility rules {path}: {problem}")

    components = data.get("components") if isinstance(data, dict) else None
    if not isinstance(components, dict):
        raise bad("there is no 'components' object.")
    if set(components) != set(Component.values):
        raise bad(f"components must be exactly {', '.join(Component.values)}.")

    rules: Rules = {}
    for component, table in components.items():
        if not isinstance(table, dict) or set(table) != set(BloodGroup.values):
            missing = sorted(set(BloodGroup.values) - set(table or {}))
            raise bad(f"{component} must list every recipient group; missing {', '.join(missing) or 'none'}.")
        rules[component] = {}
        for recipient, entries in table.items():
            donors: list[DonorOption] = []
            seen: set[str] = set()
            for entry in entries:
                # An entry is a group code, or {"group": ..., "rhFlag": true} for a flagged platelet.
                if isinstance(entry, str):
                    group, rh_flag = entry, False
                elif isinstance(entry, dict):
                    group, rh_flag = entry.get("group"), entry.get("rhFlag", False)
                else:
                    group, rh_flag = None, False
                if group not in BloodGroup.values:
                    raise bad(f"{component}/{recipient} has an unknown donor group {group!r}.")
                if group in seen:
                    raise bad(f"{component}/{recipient} lists donor {group} more than once.")
                seen.add(group)
                donors.append(DonorOption(group, len(donors), bool(rh_flag)))
            if not donors or donors[0].group != recipient:
                raise bad(f"{component}/{recipient} must start with the identical group {recipient}.")
            rules[component][recipient] = tuple(donors)
    return rules


def compatible_donors(recipient: str, component: str) -> list[DonorOption]:
    """Donor groups that may give `component` to `recipient`, best first.
    ValueError for an unknown recipient group or component."""
    rules = load_rules()
    if component not in rules:
        raise ValueError(f"Unknown component {component!r}.")
    if recipient not in rules[component]:
        raise ValueError(f"Unknown recipient group {recipient!r}.")
    return list(rules[component][recipient])


def compatible_units(recipient: str, component: str, *, exclude_hospital_id=None, now=None):
    """Usable units across the whole network that may suit `recipient`, in one query.
    Each unit carries `donor_rank`. The order is donor rank, then earliest expiry, then id."""
    options = compatible_donors(recipient, component)
    rank = Case(
        *(When(group=option.group, then=Value(option.rank)) for option in options),
        output_field=IntegerField(),
    )
    units = BloodUnit.objects.filter(component=component, group__in=[option.group for option in options])
    if exclude_hospital_id is not None:
        units = units.exclude(hospital_id=exclude_hospital_id)
    return usable_units(units, now).annotate(donor_rank=rank).order_by("donor_rank", "expires_at", "id")
