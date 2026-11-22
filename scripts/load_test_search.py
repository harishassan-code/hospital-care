"""
Times the candidate search over HTTP (B13, spec Q1 and Q2). Standard library only, so it adds no dependency.

    python3 scripts/load_test_search.py --base-url http://127.0.0.1:8000 --requests 200 --concurrency 1 5

It signs in as a demo staff login, creates one emergency case at that login's hospital, warms up, then times
GET /api/emergencies/<reference>/candidates/ at each concurrency level. Every timed request is a plain GET, so
the search's own release sweep runs each time, as it does in production. Latencies are in milliseconds, and the
percentiles use the nearest-rank method. The exit code is 1 if any request failed.

The default login is the public demo nurse from docs/setup/deployment.md. Point it at a local or demo database
only: the case it creates is real data in that database. Override the login with --email and --password, or the
LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD environment variables.
"""

import argparse
import http.cookiejar
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DEMO_EMAIL = "nurse@demo.citycare.pk"
DEMO_PASSWORD = "CityCare-demo-1"

# One need of each type, at the most the API allows on one line (blood 20, bed 5, equipment 5, operating room 3;
# see apps/emergencies/serializers.py). The origin hospital's own stock leaves some of them short, so the search
# has work to do. The summary line after the case is created says how much.
CASE_NEEDS = [
    {"type": "blood", "group": "A+", "component": "redCells", "quantity": 20},
    {"type": "bed", "bedType": "general", "quantity": 5},
    {"type": "equipment", "equipmentType": "ventilator", "quantity": 5},
    {"type": "operatingRoom", "capability": "general", "quantity": 3},
]


def percentile(sorted_values, pct):
    """Nearest-rank percentile of an ascending list; None for an empty list."""
    if not sorted_values:
        return None
    rank = math.ceil(pct / 100 * len(sorted_values))
    return sorted_values[max(rank, 1) - 1]


def summarize(latencies_ms, errors, concurrency):
    values = sorted(latencies_ms)
    return {
        "concurrency": concurrency,
        "requests": len(values) + errors,
        "errors": errors,
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": values[-1] if values else None,
    }


def format_row(row):
    def ms(value):
        return "-" if value is None else f"{value:.1f}"

    return (
        f"{row['concurrency']:>11}  {row['requests']:>8}  {row['errors']:>6}  "
        f"{ms(row['p50']):>8}  {ms(row['p95']):>8}  {ms(row['p99']):>8}  {ms(row['max']):>8}"
    )


class Session:
    """One signed-in browser-like session: a cookie jar, and the Origin and Referer headers Django's CSRF
    check expects on writes."""

    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        parts = urllib.parse.urlsplit(self.base_url)
        self.origin = f"{parts.scheme}://{parts.netloc}"

    def request(self, path, body=None, method=None, headers=None):
        data = None
        head = {"Accept": "application/json", "Origin": self.origin, "Referer": self.origin + "/"}
        if body is not None:
            data = json.dumps(body).encode()
            head["Content-Type"] = "application/json"
            head["X-CSRFToken"] = self.csrf_token()
        head.update(headers or {})
        req = urllib.request.Request(self.base_url + path, data=data, headers=head, method=method)
        with self.opener.open(req, timeout=self.timeout) as response:
            return response.status, response.read()

    def csrf_token(self):
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        return ""

    def sign_in(self, email, password):
        self.request("/api/auth/csrf/")
        try:
            self.request("/api/auth/login/", {"email": email, "password": password})
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Sign-in failed with HTTP {exc.code}. Check --email and --password.") from None

    def create_case(self):
        try:
            _, raw = self.request(
                "/api/emergencies/", {"severity": "critical", "patientRef": "LOADTEST", "items": CASE_NEEDS}
            )
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Creating the test case failed with HTTP {exc.code}.") from None
        return json.loads(raw)["id"]


def timed_gets(session, path, count):
    """`count` GETs one after another on this thread. Returns (latencies in ms of the successes, errors)."""
    latencies, errors = [], 0
    for _ in range(count):
        started = time.perf_counter()
        try:
            status, _ = session.request(path, method="GET")
        except urllib.error.HTTPError as exc:
            status = exc.code
        except (urllib.error.URLError, OSError):
            status = None
        elapsed_ms = (time.perf_counter() - started) * 1000
        if status == 200:
            latencies.append(elapsed_ms)
        else:
            errors += 1
    return latencies, errors


def run_level(session, path, total, concurrency):
    """`total` requests split across `concurrency` threads. Each thread waits for its reply before the next."""
    shares = [total // concurrency + (1 if i < total % concurrency else 0) for i in range(concurrency)]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda count: timed_gets(session, path, count), shares))
    latencies = [value for part, _ in results for value in part]
    errors = sum(part_errors for _, part_errors in results)
    return summarize(latencies, errors, concurrency)


def describe_search(payload):
    """One phrase on what the search returned: how many needs are short, and the candidate entries for them."""
    items = payload.get("items", [])
    offers = sum(len(item.get("candidates", [])) for item in items)
    return f"{len(items)} short need(s), {offers} candidate hospital entries"


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000", help="Server to test (no trailing /api)."
    )
    parser.add_argument("--email", default=os.environ.get("LOAD_TEST_EMAIL", DEMO_EMAIL))
    parser.add_argument("--password", default=os.environ.get("LOAD_TEST_PASSWORD", DEMO_PASSWORD))
    parser.add_argument("--requests", type=int, default=200, help="Timed requests per concurrency level.")
    parser.add_argument("--warmup", type=int, default=5, help="Untimed requests before the first level.")
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 5], help="Client counts to try.")
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="Seconds before a request counts as failed."
    )
    args = parser.parse_args(argv)
    if args.requests < 1 or args.warmup < 0 or any(level < 1 for level in args.concurrency):
        parser.error("--requests and each --concurrency must be 1 or more; --warmup 0 or more.")
    return args


def main(argv=None, out=sys.stdout):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    session = Session(args.base_url, args.timeout)
    session.sign_in(args.email, args.password)
    reference = session.create_case()
    path = f"/api/emergencies/{reference}/candidates/"
    _, raw = session.request(path, method="GET")  # the first GET may build caches or wake a sleeping host
    summary = describe_search(json.loads(raw))
    if args.warmup:
        timed_gets(session, path, args.warmup)

    print(f"Candidate search, {args.base_url}{path}", file=out)
    print(f"Case {reference}: {summary}", file=out)
    header = f"{'concurrency':>11}  {'requests':>8}  {'errors':>6}  {'p50 ms':>8}  {'p95 ms':>8}  {'p99 ms':>8}  {'max ms':>8}"
    print(header, file=out)
    rows = [run_level(session, path, args.requests, level) for level in args.concurrency]
    for row in rows:
        print(format_row(row), file=out)
    return 1 if any(row["errors"] for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
