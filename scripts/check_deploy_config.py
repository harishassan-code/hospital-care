"""
Checks the staging deploy config that nothing else checks before a deploy (bolt B14, #59/#69).

Staging is one Vercel project (vercel.json, framework preset "Services"): the React site and the Django API
share one domain, and /api/* goes to the API. If that drifts, the site loads but every API call fails, and the
first sign of it is a broken demo. This script runs in CI (the deploy-config job) and checks:

  1. vercel.json has a `web` service in frontend/ and a Django `api` service in backend/;
  2. /api/* is routed to `api` before the catch-all route to `web`;
  3. the frontend is built with VITE_API_URL=/api, so the browser calls the API on the same domain;
  4. backend/pyproject.toml (read by Vercel) lists the same dependencies as backend/requirements.txt (Docker,
     CI);
  5. the build script named in pyproject.toml exists.

Exit code 0 when everything matches, 1 otherwise. Standard library only.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


def requirement_lines(path: Path) -> list[str]:
    lines = (line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
    return [line for line in lines if line]


def normalised(requirement: str) -> str:
    """Compare package names the way pip does (case, - and _ alike), and ignore spaces."""
    match = re.match(r"([A-Za-z0-9._-]+)(.*)", requirement.replace(" ", ""))
    name, rest = match.groups() if match else (requirement, "")
    return re.sub(r"[-_.]+", "-", name).lower() + rest


def check_services(config: dict) -> list[str]:
    problems = []
    services = config.get("services") or {}
    web, api = services.get("web"), services.get("api")
    if not web or web.get("root") != "frontend":
        problems.append('vercel.json needs a "web" service with "root": "frontend".')
    if not api or api.get("root") != "backend" or api.get("framework") != "django":
        problems.append('vercel.json needs an "api" service with "root": "backend", "framework": "django".')
    if web and "VITE_API_URL=/api" not in (web.get("buildCommand") or ""):
        problems.append(
            'The "web" service must build with VITE_API_URL=/api (its "buildCommand"), or the site calls '
            "http://localhost:8000 instead of its own /api."
        )

    order = [
        (rule.get("source"), (rule.get("destination") or {}).get("service"))
        for rule in config.get("rewrites", [])
        if isinstance(rule.get("destination"), dict)
    ]
    api_at = next((i for i, rule in enumerate(order) if rule == ("/api/(.*)", "api")), None)
    web_at = next((i for i, rule in enumerate(order) if rule == ("/(.*)", "web")), None)
    if api_at is None:
        problems.append('vercel.json must rewrite "/api/(.*)" to the "api" service.')
    if web_at is None:
        problems.append('vercel.json must rewrite "/(.*)" to the "web" service.')
    if api_at is not None and web_at is not None and api_at > web_at:
        problems.append('The "/api/(.*)" rewrite must come before the catch-all "/(.*)".')
    return problems


def check_backend() -> list[str]:
    problems = []
    pyproject = tomllib.loads((BACKEND / "pyproject.toml").read_text())
    declared = sorted(normalised(d) for d in pyproject.get("project", {}).get("dependencies", []))
    required = sorted(normalised(r) for r in requirement_lines(BACKEND / "requirements.txt"))
    if declared != required:
        only_pyproject = sorted(set(declared) - set(required))
        only_requirements = sorted(set(required) - set(declared))
        problems.append(
            "backend/pyproject.toml and backend/requirements.txt list different dependencies "
            f"(only in pyproject.toml: {only_pyproject or 'none'}; only in requirements.txt: "
            f"{only_requirements or 'none'}). Vercel installs from pyproject.toml, Docker and CI from "
            "requirements.txt, so change both."
        )

    build = pyproject.get("tool", {}).get("vercel", {}).get("scripts", {}).get("build", "")
    script = re.search(r"([\w./-]+\.sh)\b", build)
    if not script or not (BACKEND / script.group(1)).is_file():
        problems.append(
            f"backend/pyproject.toml's [tool.vercel.scripts] build ({build!r}) must run a script in backend/."
        )
    return problems


def main() -> int:
    config_path = ROOT / "vercel.json"
    if not config_path.is_file():
        print("vercel.json is missing: staging can't deploy.")
        return 1
    problems = check_services(json.loads(config_path.read_text())) + check_backend()
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("vercel.json routes /api to the Django service; backend dependencies match. Staging config OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
