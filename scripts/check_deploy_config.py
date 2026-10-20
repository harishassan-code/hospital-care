"""
Keeps render.yaml and frontend/vercel.json pointing at the same Render service.

The browser only talks to the Vercel domain; vercel.json forwards /api/* to the Render API by its
full onrender.com URL. If render.yaml's service name and that hardcoded URL ever drift (someone
renames the service, or copies this config to a new project), login still works but every signed-in
action starts failing with 403 CSRF, and nothing else makes that obvious. This catches it in CI.

If there's no /api rewrite yet, there's nothing to check: exits clean.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def render_service_name() -> str | None:
    render_yaml = (ROOT / "render.yaml").read_text()
    match = re.search(r"type:\s*web\b.*?name:\s*(\S+)", render_yaml, re.DOTALL)
    return match.group(1) if match else None


def vercel_api_destination() -> str | None:
    config = json.loads((ROOT / "frontend" / "vercel.json").read_text())
    for rule in config.get("rewrites", []):
        if rule.get("source", "").startswith("/api"):
            return rule.get("destination", "")
    return None


def main() -> int:
    destination = vercel_api_destination()
    if destination is None:
        print("No /api rewrite in frontend/vercel.json yet; nothing to check.")
        return 0

    name = render_service_name()
    if name is None:
        print("render.yaml has no web service with a name; can't check frontend/vercel.json against it.")
        return 1

    expected_host = f"https://{name}.onrender.com"
    if expected_host not in destination:
        print(
            f"frontend/vercel.json's /api rewrite points at {destination!r}, "
            f"but render.yaml's web service is named {name!r} (expected {expected_host!r} in the destination)."
        )
        return 1

    print(f"frontend/vercel.json's /api rewrite matches render.yaml's service ({expected_host}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
