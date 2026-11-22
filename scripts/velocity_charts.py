"""
Velocity and burndown charts for the final report (bolt B15, #60).

    pip install matplotlib==3.11.2
    python3 scripts/velocity_charts.py

Reads two sources and writes four files to docs/deliverables/final/charts/:

- **Velocity** from the table in docs/scrum/timeline.md (#velocity-check): planned, completed in sprint (the
  Definition of Done) and merged in the sprint's window, per sprint. Writes velocity.csv and velocity.png.
- **Burndown** from docs/deliverables/final/charts/issues.csv, a snapshot of every issue's milestone, story
  points (the "Initial estimate" in its body) and close date, fetched once from the GitHub API so the chart
  can be rebuilt without network access. It counts the issues on the Sprint 1-9 milestones (the release
  plan) and draws the points still open at the end of each day, against a straight line to zero at the end
  of Sprint 9, up to the day of the snapshot (SNAPSHOT_DATE). Writes burndown.csv and burndown.png.

matplotlib is needed only here, so it is not in backend/requirements*.txt. Colours follow the dataviz
reference palette (categorical slots 1-3, validated for colour-vision deficiency), with value labels so no
reading depends on colour alone.
"""

import csv
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TIMELINE = ROOT / "docs/scrum/timeline.md"
OUT = ROOT / "docs/deliverables/final/charts"
ISSUES = OUT / "issues.csv"

SPRINT_1_START = date(2026, 10, 3)  # as in scripts/backlog.py: sprints run Saturday to Friday
SPRINTS = 9
KARACHI = timezone(timedelta(hours=5))
# The day issues.csv was fetched. The burndown ends here: it knows nothing about later closes. Change it when
# you refresh the snapshot.
SNAPSHOT_DATE = date(2026, 11, 22)

SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3, in order


def sprint_start(n: int) -> date:
    return SPRINT_1_START + timedelta(weeks=n - 1)


def velocity_rows() -> list[dict]:
    """The velocity table's filled-in rows: sprint, planned, committed, completed, merged in window."""
    section = TIMELINE.read_text(encoding="utf-8").split("## Velocity check", 1)[1]
    rows = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0].isdigit() and all(c.isdigit() for c in cells[1:5]):
            sprint, planned, committed, completed, merged = map(int, cells[:5])
            rows.append(
                {
                    "sprint": sprint,
                    "planned": planned,
                    "committed": committed,
                    "completed": completed,
                    "merged": merged,
                }
            )
    return rows


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def velocity_chart(rows: list[dict]) -> None:
    with open(OUT / "velocity.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sprint", "planned", "committed", "completed", "merged"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    width = 0.26
    series = [
        ("planned", "Planned (release plan)"),
        ("completed", "Completed in the sprint (Definition of Done)"),
        ("merged", "Merged to main in the sprint's window"),
    ]
    for i, (key, label) in enumerate(series):
        xs = [r["sprint"] + (i - 1) * (width + 0.03) for r in rows]
        ys = [r[key] for r in rows]
        bars = ax.bar(xs, ys, width=width, color=SERIES[i], label=label, zorder=2)
        for bar, value in zip(bars, ys, strict=True):
            ax.annotate(
                str(value),
                (bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=7.5,
                color=INK_2,
            )
    ax.set_xticks([r["sprint"] for r in rows], [f"Sprint {r['sprint']}" for r in rows])
    ax.set_ylabel("Story points", color=INK_2)
    ax.set_title(
        "Velocity: points planned, completed and merged per sprint", loc="left", color=INK, fontsize=12
    )
    ax.legend(frameon=False, loc="upper left", fontsize=8.5, labelcolor=INK_2)
    ax.set_ylim(0, max(max(r["merged"], r["planned"]) for r in rows) * 1.18)
    fig.tight_layout()
    fig.savefig(OUT / "velocity.png", facecolor=SURFACE)
    plt.close(fig)


def burndown_chart(today: date) -> dict:
    issues = list(csv.DictReader(open(ISSUES, encoding="utf-8")))
    planned = [
        i for i in issues if re.match(r"Sprint [1-9] ", i["milestone"]) and i["points"].strip().isdigit()
    ]
    total = sum(int(i["points"]) for i in planned)

    def closed_on(issue) -> date | None:
        if issue["state"] != "closed" or not issue["closed_at"]:
            return None
        return datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00")).astimezone(KARACHI).date()

    start, end = sprint_start(1), sprint_start(SPRINTS) + timedelta(days=6)
    days = [start + timedelta(days=n) for n in range((today - start).days + 1)]
    remaining = []
    for day in days:
        done = sum(int(i["points"]) for i in planned if (c := closed_on(i)) is not None and c <= day)
        remaining.append(total - done)
    ideal_days = (end - start).days
    ideal = [round(total * max(0.0, 1 - (day - start).days / ideal_days), 1) for day in days]

    with open(OUT / "burndown.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["date", "points_remaining", "ideal"])
        writer.writerows([[d.isoformat(), r, i] for d, r, i in zip(days, remaining, ideal, strict=True)])

    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    for n in range(1, SPRINTS + 1):
        s = sprint_start(n)
        ax.axvline(s, color=GRID, linewidth=0.8, zorder=1)
        ax.text(s + timedelta(days=3.5), total * 1.02, f"S{n}", ha="center", fontsize=8, color=MUTED)
    ax.plot(
        [start, end],
        [total, 0],
        color=MUTED,
        linewidth=1.5,
        linestyle=(0, (4, 3)),
        label="Plan: even burn to 4 Dec",
    )
    ax.step(days, remaining, where="post", color=SERIES[0], linewidth=2, label="Points still open", zorder=3)
    for day, label in (
        (date(2026, 10, 19), "19–20 Oct integration"),
        (date(2026, 11, 17), "17 Nov integration"),
    ):
        value = remaining[(day - start).days]
        ax.annotate(
            label,
            (day, value),
            xytext=(-8, -16),
            ha="right",
            textcoords="offset points",
            fontsize=8,
            color=INK_2,
            arrowprops={"arrowstyle": "-", "color": AXIS, "linewidth": 0.8},
        )
    ax.annotate(
        f"{remaining[-1]} open on {today:%d %b}",
        (days[-1], remaining[-1]),
        xytext=(-10, -8),
        textcoords="offset points",
        ha="right",
        fontsize=8,
        color=INK_2,
    )
    ax.set_xlim(start - timedelta(days=1), end + timedelta(days=1))
    ax.set_ylim(0, total * 1.1)
    ax.set_ylabel("Story points still open", color=INK_2)
    ax.set_title(
        f"Release burndown: the {total}-point plan for Sprints 1–9, by issue close date",
        loc="left",
        color=INK,
        fontsize=12,
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(frameon=False, loc="lower left", fontsize=8.5, labelcolor=INK_2)
    fig.tight_layout()
    fig.savefig(OUT / "burndown.png", facecolor=SURFACE)
    plt.close(fig)
    return {"total": total, "remaining": remaining[-1], "issues": len(planned)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = velocity_rows()
    velocity_chart(rows)
    burn = burndown_chart(min(SNAPSHOT_DATE, sprint_start(SPRINTS) + timedelta(days=6)))
    print(f"velocity: sprints {rows[0]['sprint']}–{rows[-1]['sprint']} -> {OUT / 'velocity.png'}")
    print(
        f"burndown: {burn['issues']} issues, {burn['total']} points, {burn['remaining']} open"
        f" -> {OUT / 'burndown.png'}"
    )


if __name__ == "__main__":
    main()
