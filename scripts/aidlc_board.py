"""Build the AIDLC bolt board (docs/aidlc/bolts/README.md) from the bolt files' front matter.

Each bolt is one file, docs/aidlc/bolts/BNN-<slug>.md, starting with a front-matter block:

    ---
    id: B01
    title: Inter-hospital transfer request
    issues: 47
    points: 5
    priority: highest
    sprint: 7
    depends_on: B00
    owner: unassigned
    status: Ready
    ---

The board is generated, never edited by hand: change the bolt file, then run

    python3 scripts/aidlc_board.py          # rewrite the board
    python3 scripts/aidlc_board.py --check  # CI: fail if the board is out of date or a bolt is malformed
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOLTS = ROOT / "docs" / "aidlc" / "bolts"
BOARD = BOLTS / "README.md"
REPO = "https://github.com/harishassan-code/hospital-care"

REQUIRED = ["id", "title", "issues", "points", "priority", "sprint", "depends_on", "owner", "status"]
STATUSES = ["Backlog", "Ready", "In Progress", "In Review", "Done"]
PRIORITIES = ["highest", "high", "medium", "low"]
STATUS_ICON = {"Backlog": "⚪", "Ready": "🟢", "In Progress": "🟡", "In Review": "🔵", "Done": "✅"}

HEADER = """# Bolt board

> **Generated** by `scripts/aidlc_board.py` from each bolt's front matter. Don't edit this table: change the
> bolt file and run `python3 scripts/aidlc_board.py`. CI fails if the two disagree.

A **bolt** is one short, time-boxed AIDLC cycle (1–3 days) owned by one person: Inception spec → approval →
Construction → PR → Operations notes. How to run one: [docs/aidlc/README.md](../README.md#4-bolts).

**To take a bolt:** set `owner:` to your GitHub handle and `status: In Progress` in its file, run the script,
and assign yourself the linked issue(s) on the board. Max 2 bolts in progress per person (working agreement).
A bolt can start once everything in **Depends on** is Done (or the bolt says which part can go ahead).
"""


def parse(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ValueError(f"{path.name}: missing front matter (--- block at the top)")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.strip():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    missing = [key for key in REQUIRED if key not in meta]
    if missing:
        raise ValueError(f"{path.name}: missing {', '.join(missing)}")
    if not path.name.startswith(meta["id"] + "-"):
        raise ValueError(f"{path.name}: file name must start with its id ({meta['id']}-)")
    if meta["status"] not in STATUSES:
        raise ValueError(f"{path.name}: status must be one of {', '.join(STATUSES)}")
    if meta["priority"] not in PRIORITIES:
        raise ValueError(f"{path.name}: priority must be one of {', '.join(PRIORITIES)}")
    meta["file"] = path.name
    return meta


def split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip() and part.strip() != "-"]


def issue_links(value: str) -> str:
    return ", ".join(f"[#{n}]({REPO}/issues/{n})" for n in split(value)) or "–"


def render(bolts: list[dict[str, str]]) -> str:
    ids = {bolt["id"] for bolt in bolts}
    for bolt in bolts:
        unknown = [dep for dep in split(bolt["depends_on"]) if dep not in ids]
        if unknown:
            raise ValueError(f"{bolt['file']}: depends on unknown bolt(s) {', '.join(unknown)}")

    lines = [HEADER]
    groups: dict[str, list[dict[str, str]]] = {}
    for bolt in bolts:
        groups.setdefault(bolt["sprint"], []).append(bolt)

    def sprint_key(sprint: str) -> tuple[int, str]:
        return (int(sprint), "") if sprint.isdigit() else (99, sprint)

    for sprint in sorted(groups, key=sprint_key):
        group = groups[sprint]
        points = sum(int(b["points"]) for b in group if b["points"].isdigit())
        title = f"Sprint {sprint}" if sprint.isdigit() else sprint.capitalize()
        lines.append(f"## {title} ({points} pts)\n")
        lines.append("| Bolt | Title | Issues | Pts | Priority | Depends on | Owner | Status |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for b in group:
            deps = ", ".join(split(b["depends_on"])) or "–"
            owner = "_unassigned_" if b["owner"] in ("", "unassigned") else b["owner"]
            lines.append(
                f"| [{b['id']}]({b['file']}) | {b['title']} | {issue_links(b['issues'])} | {b['points']} "
                f"| {b['priority']} | {deps} | {owner} | {STATUS_ICON[b['status']]} {b['status']} |"
            )
        lines.append("")

    counts = {status: sum(b["status"] == status for b in bolts) for status in STATUSES}
    lines.append("## Progress\n")
    lines.append(" · ".join(f"{STATUS_ICON[s]} {s}: {counts[s]}" for s in STATUSES))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    files = sorted(p for p in BOLTS.glob("B[0-9]*-*.md"))
    try:
        board = render([parse(p) for p in files])
    except ValueError as error:
        print(f"aidlc_board: {error}", file=sys.stderr)
        return 1
    if "--check" in sys.argv:
        current = BOARD.read_text(encoding="utf-8") if BOARD.exists() else ""
        if current != board:
            print("aidlc_board: the bolt board is out of date. Run python3 scripts/aidlc_board.py")
            return 1
        print(f"aidlc_board: {len(files)} bolts, board up to date.")
        return 0
    BOARD.write_text(board, encoding="utf-8")
    print(f"aidlc_board: wrote {BOARD.relative_to(ROOT)} ({len(files)} bolts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
