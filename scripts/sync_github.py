"""Create labels, sprint milestones and backlog issues on GitHub from scripts/backlog.py.

Idempotent: existing labels are updated, existing milestones/issues (matched by title) are skipped.
Requires the GitHub CLI (`gh`) logged in with repo access.

    python scripts/sync_github.py                 # labels, milestones, issues
    python scripts/sync_github.py --project       # also create/fill the GitHub Project board
                                                   # (needs: gh auth refresh -s project)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, time, timedelta, timezone

from backlog import BACKLOG, EPICS, SPRINT_GOALS, sprint_dates

PKT = timezone(timedelta(hours=5))
PROJECT_TITLE = "Hospital Care Scrum Board"

LABELS = {
    "type: story": ("0e8a16", "User-facing backlog item"),
    "type: task": ("c5def5", "Technical or process work"),
    "type: bug": ("d73a4a", "Something is broken"),
    "needs refinement": ("fbca04", "Not yet meeting the Definition of Ready"),
    "blocked": ("b60205", "Waiting on something outside the assignee's control"),
    "stretch": ("ededed", "Secondary scope; only pulled in if velocity allows"),
    "priority: highest": ("b60205", ""),
    "priority: high": ("d93f0b", ""),
    "priority: medium": ("fbca04", ""),
    "priority: low": ("c2e0c6", ""),
    "area: frontend": ("5319e7", ""),
    "area: backend": ("1d76db", ""),
    "area: devops": ("006b75", ""),
    "area: docs": ("bfdadc", ""),
    "area: qa": ("f9d0c4", ""),
}
for code, (name, color) in EPICS.items():
    LABELS[f"epic: {code} {name}"] = (color, f"WBS epic {code}")


def gh(*args, input=None, check=True):
    res = subprocess.run(["gh", *args], input=input, capture_output=True, text=True, encoding="utf-8")
    if check and res.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed:\n{res.stderr}")
    return res.stdout


def gh_json(*args):
    out = gh(*args)
    return json.loads(out) if out.strip() else None


def repo_name():
    return gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]


def milestone_title(n):
    start, end = sprint_dates(n)
    return f"Sprint {n} ({start:%b %d} – {end:%b %d})"


def sync_labels():
    for name, (color, desc) in LABELS.items():
        gh("label", "create", name, "--color", color, "--description", desc, "--force")
    print(f"labels: {len(LABELS)} ensured")


def sync_milestones(repo):
    existing = {m["title"]: m["number"] for m in gh_json("api", f"repos/{repo}/milestones?state=all&per_page=100")}
    numbers = {}
    for n, goal in enumerate(SPRINT_GOALS, start=1):
        title = milestone_title(n)
        if title in existing:
            numbers[n] = existing[title]
            continue
        _, end = sprint_dates(n)
        # Due at the Friday ceremony (22:00 PKT)
        due = datetime.combine(end, time(22, 0), PKT).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        m = gh_json("api", f"repos/{repo}/milestones", "-f", f"title={title}", "-f", f"description=Sprint goal: {goal}",
                    "-f", f"due_on={due}")
        numbers[n] = m["number"]
    print(f"milestones: {len(numbers)} ensured")
    return numbers


def issue_title(item):
    return item["title"]


def issue_body(item):
    lines = [
        "## Story" if item["type"] == "story" else "## Task",
        item["story"],
        "",
        "## Acceptance criteria",
        *[f"- [ ] {c}" for c in item["ac"]],
        "",
        "## Details",
        f"- **WBS:** {item['wbs']}",
        f"- **Epic:** {item['epic']} {EPICS[item['epic']][0]}",
        f"- **Initial estimate:** {item['points']} story points",
        f"- **Planned sprint:** {item['sprint'] or 'Unscheduled (secondary/stretch)'}",
        "",
        "_Imported from the initial product backlog. Re-estimate and refine during sprint planning._",
    ]
    return "\n".join(lines)


def issue_labels(item):
    labels = [f"type: {item['type']}", f"priority: {item['priority']}", f"epic: {item['epic']} {EPICS[item['epic']][0]}"]
    labels += [f"area: {a}" for a in item["area"]]
    if item["sprint"] is None:
        labels.append("stretch")
    return labels


def sync_issues(repo, milestones):
    existing = {i["title"]: i["number"] for i in gh_json("issue", "list", "--state", "all", "--limit", "500",
                                                          "--json", "title,number")}
    created = 0
    numbers = {}
    for item in BACKLOG:
        title = issue_title(item)
        if title in existing:
            numbers[title] = existing[title]
            continue
        args = ["issue", "create", "--title", title, "--body-file", "-"]
        for label in issue_labels(item):
            args += ["--label", label]
        if item["sprint"]:
            args += ["--milestone", milestone_title(item["sprint"])]
        url = gh(*args, input=issue_body(item)).strip()
        numbers[title] = int(url.rsplit("/", 1)[1])
        created += 1
    print(f"issues: {created} created, {len(BACKLOG) - created} already existed")
    return numbers


# ── GitHub Project (v2) ─────────────────────────────────────────────────────

def graphql(query, **variables):
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        args += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
    return gh_json(*args)["data"]


def sync_project(repo, issue_numbers):
    owner = repo.split("/")[0]
    projects = gh_json("project", "list", "--owner", owner, "--format", "json")["projects"]
    project = next((p for p in projects if p["title"] == PROJECT_TITLE), None)
    if project is None:
        project = gh_json("project", "create", "--owner", owner, "--title", PROJECT_TITLE, "--format", "json")
        gh("project", "link", str(project["number"]), "--owner", owner, "--repo", repo)
    num, pid = str(project["number"]), project["id"]

    fields = {f["name"]: f for f in gh_json("project", "field-list", num, "--owner", owner, "--format", "json")["fields"]}

    # Status column options for the board
    status = fields["Status"]
    wanted = ["Backlog", "Ready", "In Progress", "In Review", "Done"]
    if [o["name"] for o in status.get("options", [])] != wanted:
        colors = ["GRAY", "BLUE", "YELLOW", "PURPLE", "GREEN"]
        opts = ", ".join(f'{{name: "{n}", color: {c}, description: ""}}' for n, c in zip(wanted, colors, strict=True))
        graphql(f'mutation($id: ID!) {{ updateProjectV2Field(input: {{fieldId: $id, singleSelectOptions: [{opts}]}})'
                " { clientMutationId } }", id=status["id"])

    if "Points" not in fields:
        gh("project", "field-create", num, "--owner", owner, "--name", "Points", "--data-type", "NUMBER")
    if "Priority" not in fields:
        gh("project", "field-create", num, "--owner", owner, "--name", "Priority", "--data-type", "SINGLE_SELECT",
           "--single-select-options", "Highest,High,Medium,Low")
    if "Sprint" not in fields:
        start, _ = sprint_dates(1)
        iterations = ", ".join(
            f'{{title: "Sprint {n}", startDate: "{sprint_dates(n)[0]:%Y-%m-%d}", duration: 7}}'
            for n in range(1, len(SPRINT_GOALS) + 1))
        graphql(
            "mutation($pid: ID!) { createProjectV2Field(input: {projectId: $pid, dataType: ITERATION, name: \"Sprint\","
            f' iterationConfiguration: {{startDate: "{start:%Y-%m-%d}", duration: 7, iterations: [{iterations}]}}}})'
            " { clientMutationId } }", pid=pid)
    fields = {f["name"]: f for f in gh_json("project", "field-list", num, "--owner", owner, "--format", "json")["fields"]}

    sprint_ids = {}
    sprint_field = graphql(
        "query($id: ID!) { node(id: $id) { ... on ProjectV2IterationField { configuration { iterations { id title } } } } }",
        id=fields["Sprint"]["id"])["node"]["configuration"]["iterations"]
    for it in sprint_field:
        sprint_ids[int(it["title"].split()[-1])] = it["id"]
    priority_ids = {o["name"].lower(): o["id"] for o in fields["Priority"]["options"]}
    status_ids = {o["name"]: o["id"] for o in fields["Status"]["options"]}

    existing_items = {i["content"].get("number"): i["id"] for i in
                      gh_json("project", "item-list", num, "--owner", owner, "--limit", "500", "--format", "json")["items"]}

    def set_field(item_id, field, **value):
        args = ["project", "item-edit", "--id", item_id, "--project-id", pid, "--field-id", fields[field]["id"]]
        for k, v in value.items():
            args += [f"--{k}", str(v)]
        gh(*args)

    added = 0
    for item in BACKLOG:
        number = issue_numbers[issue_title(item)]
        if number in existing_items:
            continue
        url = f"https://github.com/{repo}/issues/{number}"
        item_id = gh_json("project", "item-add", num, "--owner", owner, "--url", url, "--format", "json")["id"]
        set_field(item_id, "Points", number=item["points"])
        set_field(item_id, "Priority", **{"single-select-option-id": priority_ids[item["priority"]]})
        set_field(item_id, "Status", **{"single-select-option-id": status_ids["Ready" if item["sprint"] == 1 else "Backlog"]})
        if item["sprint"]:
            set_field(item_id, "Sprint", **{"iteration-id": sprint_ids[item["sprint"]]})
        added += 1
    print(f"project #{num}: {added} items added → https://github.com/users/{owner}/projects/{num}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", action="store_true", help="also create and fill the GitHub Project board")
    args = parser.parse_args()

    repo = repo_name()
    sync_labels()
    milestones = sync_milestones(repo)
    numbers = sync_issues(repo, milestones)
    if args.project:
        sync_project(repo, numbers)


if __name__ == "__main__":
    main()
