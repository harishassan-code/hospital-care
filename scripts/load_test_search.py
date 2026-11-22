#!/usr/bin/env python3
"""Story #58: time the candidate search (story #38) and print p50 / p95 / max.

Signs in as the demo doctor, opens one synthetic case that needs O- red cells, an ICU bed and a ventilator, then
asks for its candidate hospitals N times. Standard library only, so it runs anywhere Python does.

    python scripts/load_test_search.py --base http://localhost:8000/api --requests 200
    python scripts/load_test_search.py --base https://<staging-api>/api --requests 200

Seed the city first: `python manage.py seed_demo --hospitals 50` (synthetic data only).
"""

import argparse
import http.cookiejar
import json
import statistics
import sys
import time
import urllib.request


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self) -> str:
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def call(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.base}{path}", data=data, method=method)
        request.add_header("Content-Type", "application/json")
        request.add_header("Referer", self.base)
        if method != "GET":
            request.add_header("X-CSRFToken", self._csrf())
        with self.opener.open(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://localhost:8000/api")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--email", default="doctor@demo.citycare.pk")
    parser.add_argument("--password", default="CityCare-demo-1")
    args = parser.parse_args()

    client = Client(args.base)
    client.call("GET", "/auth/csrf/")
    client.call("POST", "/auth/login/", {"email": args.email, "password": args.password})
    case = client.call(
        "POST",
        "/emergencies/",
        {
            "severity": "high",
            "patientRef": "LOAD-TEST",
            "items": [
                {"type": "blood", "group": "O-", "component": "redCells", "quantity": 4},
                {"type": "bed", "bedType": "icu", "quantity": 1},
                {"type": "equipment", "equipmentType": "ventilator", "quantity": 1},
            ],
        },
    )
    path = f"/emergencies/{case['id']}/candidates/"
    client.call("GET", path)  # warm up

    timings = []
    for _ in range(args.requests):
        start = time.perf_counter()
        client.call("GET", path)
        timings.append((time.perf_counter() - start) * 1000)
    client.call("POST", f"/emergencies/{case['id']}/actions/", {"action": "cancel", "note": "Load test"})

    timings.sort()
    p95 = timings[max(0, int(len(timings) * 0.95) - 1)]
    print(f"{len(timings)} requests to {path}")
    print(f"p50 {statistics.median(timings):.1f} ms · p95 {p95:.1f} ms · max {timings[-1]:.1f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
