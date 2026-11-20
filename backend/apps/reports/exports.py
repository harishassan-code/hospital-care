"""
The report dict from `services.build` laid out as files to share (B18, #67): CSV for spreadsheets, PDF for
reading. Both show the same sections and figures as the page; nothing is computed here.
"""

import csv
import io

from fpdf import FPDF
from fpdf.fonts import FontFace

# What a spreadsheet would run as a formula (OWASP's list), plus tab and carriage return, as in B10.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _minutes(value) -> str:
    return "" if value is None else f"{value:g}"


def sections(report: dict) -> list[tuple[str, list[str], list[list]]]:
    """(title, header, rows) for every table, in the order both files show them."""
    requests, fulfilment, wastage = report["requests"], report["fulfilment"], report["wastage"]
    stats_header = ["Cases", "Median (min)", "Average (min)", "90th percentile (min)"]

    def stats_row(stats: dict) -> list:
        return [
            stats["count"],
            _minutes(stats["medianMinutes"]),
            _minutes(stats["averageMinutes"]),
            _minutes(stats["p90Minutes"]),
        ]

    return [
        (
            f"Requests: {requests['total']} case(s) opened, {requests['allocations']} resource(s) allocated",
            ["Severity", "Cases"],
            [[row["label"], row["count"]] for row in requests["bySeverity"]],
        ),
        (
            "Requests by current status",
            ["Status", "Cases"],
            [[row["label"], row["count"]] for row in requests["byStatus"]],
        ),
        (
            "Requests by resource type",
            ["Resource type", "Needs", "Units asked", "Units allocated"],
            [
                [row["label"], row["needs"], row["unitsAsked"], row["unitsAllocated"]]
                for row in requests["byResourceType"]
            ],
        ),
        (
            "Fulfilment time (opened to fulfilled)",
            ["Severity", *stats_header],
            [["All", *stats_row(fulfilment["overall"])]]
            + [[row["label"], *stats_row(row)] for row in fulfilment["bySeverity"]],
        ),
        (
            "Opened in the range and not fulfilled",
            ["Current status", "Cases"],
            [[row["label"], row["count"]] for row in fulfilment["notFulfilled"]],
        ),
        (
            f"Blood wastage: {wastage['expired']} expired unused, {wastage['discarded']} discarded",
            ["Hospital", "Group", "Component", "Expired", "Discarded"],
            [
                [row["hospital"], row["group"], row["component"], row["expired"], row["discarded"]]
                for row in wastage["rows"]
            ],
        ),
    ]


def _heading(report: dict) -> tuple[str, str]:
    period = f"{report['range']['from']} to {report['range']['to']} ({report['range']['days']} days)"
    where = report["hospital"]["name"] if report["hospital"] else "All hospitals"
    return period, where


def filename(report: dict, extension: str) -> str:
    return f"reports-{report['range']['from']}-to-{report['range']['to']}.{extension}"


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_STARTS) else text


def to_csv(report: dict) -> str:
    """One section per table: its title, its header, its rows, then a blank line."""
    period, where = _heading(report)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["CityCare operational reports"])
    writer.writerow(["Period", period])
    writer.writerow(["Hospital", _cell(where)])
    writer.writerow([])
    for title, header, rows in sections(report):
        writer.writerow([title])
        writer.writerow(header)
        writer.writerows([_cell(value) for value in row] for row in rows)
        if not rows:
            writer.writerow(["(none)"])
        writer.writerow([])
    return buffer.getvalue()


def _latin1(value) -> str:
    """The PDF core fonts draw Latin-1 only; anything else becomes '?' rather than failing the export."""
    return str(value).encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: dict) -> bytes:
    """A4 portrait: a title, the period and hospital, then one table per section."""
    period, where = _heading(report)
    pdf = FPDF(orientation="portrait", unit="mm", format="A4")
    pdf.set_title("CityCare operational reports")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "CityCare operational reports", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, _latin1(f"Period: {period}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _latin1(f"Hospital: {where}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        _latin1(f"Generated: {report['generatedAt'][:16].replace('T', ' ')}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    for title, header, rows in sections(report):
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, _latin1(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        if not rows:
            pdf.cell(0, 6, "None in this period.", new_x="LMARGIN", new_y="NEXT")
            continue
        with pdf.table(
            headings_style=FontFace(emphasis="BOLD", fill_color=(230, 230, 230)), text_align="LEFT"
        ) as table:
            for line in [header, *rows]:
                table_row = table.row()
                for value in line:
                    table_row.cell(_latin1(value))
    return bytes(pdf.output())
