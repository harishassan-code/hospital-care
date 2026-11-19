"""B13 search load test (spec Q1, Q2): scripts/load_test_search.py times the candidate search over HTTP. These
tests check its arithmetic, its failure messages, and one real run against a gunicorn server."""

import importlib.util
import socket
import subprocess
import sys
import time
import urllib.request
from io import StringIO
from pathlib import Path

import pytest

from apps.core.tests.django_subprocess import BACKEND, child_env, manage

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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_up(url: str, seconds: float = 30) -> None:
    deadline = time.monotonic() + seconds
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


@pytest.fixture
def served_network(tmp_path):
    """Gunicorn with its default single synchronous worker, as render.yaml runs it, on a file database seeded
    with the demo data. Django's in-process live server is not used here: it gives every thread the same
    in-memory SQLite connection, which is not safe for concurrent requests."""
    env = {"DJANGO_DEBUG": "true", "DATABASE_URL": f"sqlite:///{tmp_path / 'loadtest.sqlite3'}"}
    for command in (("migrate", "--noinput"), ("seed_demo",)):
        done = manage(*command, env=env)
        assert done.returncode == 0, done.stderr
    address = f"127.0.0.1:{free_port()}"
    with open(tmp_path / "gunicorn.log", "w") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "config.wsgi:application", "--bind", address],
            cwd=BACKEND,
            env=child_env(env),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_until_up(f"http://{address}/api/health/")
            yield f"http://{address}"
        finally:
            server.terminate()
            server.wait(timeout=10)


def test_a_run_against_a_gunicorn_server_reports_every_level(served_network):
    out = StringIO()
    code = script.main(
        ["--base-url", served_network, "--requests", "6", "--warmup", "2", "--concurrency", "1", "3"],
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
