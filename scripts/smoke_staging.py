"""
Is staging up? Run it a couple of minutes before every demo (bolt B14, #59/#69):

    python3 scripts/smoke_staging.py https://hospital-care.vercel.app

It checks, in order:
  1. the API through the Vercel proxy:  <site>/api/health/  →  {"status": "ok"}
  2. the frontend:                      <site>/             →  200 with the app's HTML

The free Render API sleeps after 15 minutes idle and takes 30–60 s to wake, so the first check waits up to
90 s; running this also wakes it. Exit code 0 when everything passes, 1 otherwise. Standard library only.
"""

import json
import sys
import time
import urllib.error
import urllib.request

WAKE_SECONDS = 90
TIMEOUT_SECONDS = 30


def fetch(url: str, timeout: float = TIMEOUT_SECONDS) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "citycare-smoke-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def check_health(site: str) -> str | None:
    """None when the API answers ok, otherwise what went wrong. Retries while the API wakes up."""
    url = f"{site}/api/health/"
    deadline = time.monotonic() + WAKE_SECONDS
    problem = "no answer"
    while time.monotonic() < deadline:
        try:
            status, body = fetch(url)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            problem = f"could not connect ({error})"
        else:
            if status == 200:
                try:
                    if json.loads(body).get("status") == "ok":
                        return None
                except ValueError:
                    pass
                return f'{url} answered 200 but not {{"status": "ok"}}: {body[:120]!r}'
            problem = f"{url} answered {status}"
            if status not in (502, 503, 504):  # anything but "still waking up" won't fix itself
                return problem
        time.sleep(5)
    return f"{problem} after {WAKE_SECONDS} s"


def check_home(site: str) -> str | None:
    try:
        status, body = fetch(f"{site}/")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        return f"could not open the home page ({error})"
    if status != 200:
        return f"the home page answered {status}"
    if '<div id="root">' not in body:
        return 'the home page is not the React app (no <div id="root">)'
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].startswith(("http://", "https://")):
        print("Usage: python3 scripts/smoke_staging.py <site URL, e.g. https://hospital-care.vercel.app>")
        return 1
    site = argv[1].rstrip("/")
    failed = False
    checks = (("API health (through the site's /api proxy)", check_health), ("Home page", check_home))
    for name, check in checks:
        problem = check(site)
        print(f"{'FAIL' if problem else 'ok  '}  {name}{': ' + problem if problem else ''}")
        failed = failed or problem is not None
    print("Staging is NOT ready." if failed else "Staging is up.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
