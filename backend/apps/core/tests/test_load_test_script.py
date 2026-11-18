"""B13 search load test (spec Q1, Q2): scripts/load_test_search.py times the candidate search over HTTP. These
tests check its arithmetic, its failure messages, and one real run against Django's live server."""

import importlib.util
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db(transaction=True)

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "load_test_search.py"


def load_script():
    spec = importlib.util.spec_from_file_location("load_test_search", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = load_script()


def test_percentiles_use_the_nearest_rank():
    values = list(range(1, 101))
    assert script.percentile(values, 50) == 50
    assert script.percentile(values, 95) == 95
    assert script.percentile(values, 99) == 99
    assert script.percentile([7.0], 99) == 7.0
    assert script.percentile([], 95) is None


def test_a_summary_counts_failures_and_leaves_them_out_of_the_latencies():
    row = script.summarize([10.0, 20.0, 30.0], errors=2, concurrency=5)
    expected = {
        "concurrency": 5,
        "requests": 5,
        "errors": 2,
        "p50": 20.0,
        "p95": 30.0,
        "p99": 30.0,
        "max": 30.0,
    }
    assert row == expected


def test_a_wrong_password_stops_with_a_message_that_names_the_fix(live_server):
    with pytest.raises(SystemExit, match="HTTP 401"):
        script.main(["--base-url", live_server.url, "--password", "not-the-password"], out=StringIO())


def test_a_run_against_the_live_server_reports_every_level(live_server):
    call_command("seed_demo", stdout=StringIO())
    out = StringIO()
    code = script.main(
        ["--base-url", live_server.url, "--requests", "6", "--warmup", "2", "--concurrency", "1", "3"],
        out=out,
    )
    lines = out.getvalue().splitlines()
    assert code == 0, out.getvalue()
    assert lines[0].startswith("Candidate search, ") and lines[0].endswith("/candidates/")
    assert lines[1].startswith("Case EC-") and "short need(s)" in lines[1]
    assert "p95 ms" in lines[2]
    rows = {int(line.split()[0]): line.split() for line in lines[3:]}
    assert set(rows) == {1, 3}
    for level, fields in rows.items():
        requests, errors = int(fields[1]), int(fields[2])
        assert requests == 6 and errors == 0, (level, fields)
