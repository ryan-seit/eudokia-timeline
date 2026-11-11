"""Build the client timeline page from the GitHub project.

Reads the project through the GitHub GraphQL API and writes dist/index.html.
Needs a token in PROJECT_TOKEN (or GH_TOKEN) that can read the project and
the issues in the private repo it tracks.

Run locally:  PROJECT_TOKEN=$(gh auth token) python3 scripts/build.py
"""
import json
import os
import pathlib
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

OWNER = "ryan-seit"
PROJECT_NUMBER = 1
TIMEZONE = "America/New_York"

# Items the client never sees. Add the label "internal" to any issue to hide it,
# or list its issue number here.
HIDE_LABEL = "internal"
HIDE_ISSUES = {27, 40}

ROOT = pathlib.Path(__file__).resolve().parent.parent

QUERY = """
query($owner: String!, $number: Int!, $after: String) {
  user(login: $owner) {
    projectV2(number: $number) {
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isArchived
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
            }
          }
          content {
            ... on Issue {
              number title body
              parent { number }
              subIssuesSummary { total completed }
              labels(first: 20) { nodes { name } }
            }
          }
        }
      }
    }
  }
}
"""


def graphql(token, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if data.get("errors"):
        sys.exit("GitHub API error: " + json.dumps(data["errors"], indent=2))
    project = data["data"]["user"]["projectV2"]
    if project is None:
        sys.exit("Project not found. Check the token can read projects (read:project).")
    return project["items"]


def fetch_items(token):
    items, after = [], None
    while True:
        page = graphql(token, {"owner": OWNER, "number": PROJECT_NUMBER, "after": after})
        items += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return items
        after = page["pageInfo"]["endCursor"]


def clean_body(body):
    body = (body or "").split("Source:")[0].strip()
    for phrase in (
        " Dates are a proposed placement within the QA window.",
        " Dates are a proposed placement; the doc doesn't schedule this page individually.",
        " Dates are a proposed placement.",
    ):
        body = body.replace(phrase, "")
    return " ".join(body.split())


def to_task(item):
    issue = item["content"]
    labels = {l["name"] for l in issue["labels"]["nodes"]}
    fields = {}
    for fv in item["fieldValues"]["nodes"]:
        if fv and fv.get("field"):
            fields[fv["field"]["name"]] = fv.get("date") or fv.get("name")

    if "launch" in labels:
        kind = "launch"
    elif "client-deliverable" in labels:
        kind = "client"
    elif "review" in labels:
        kind = "review"
    elif "phase-2" in labels:
        kind = "phase2"
    else:
        kind = "build"

    title = issue["title"].removeprefix("Client deliverable: ").removeprefix("Phase 2: ")
    subs = issue["subIssuesSummary"]
    start, target = fields.get("Start date"), fields.get("Target date")
    if start and not target:
        target = start
    if target and not start:
        start = target
    return {
        "n": issue["number"],
        "t": title,
        "k": kind,
        "s": fields.get("Status") or "Backlog",
        "a": start,
        "b": target,
        "d": "" if kind == "client" else clean_body(issue["body"]),
        "p": [subs["completed"], subs["total"]] if subs["total"] else None,
    }


def visible(item):
    issue = item.get("content") or {}
    if item.get("isArchived") or "number" not in issue:
        return False  # archived items, draft notes and pull requests stay off the page
    labels = {l["name"] for l in issue["labels"]["nodes"]}
    if issue["number"] in HIDE_ISSUES or HIDE_LABEL in labels:
        return False
    if issue["parent"]:
        return False  # sub-issues show as progress on their parent
    if not labels:
        return False  # unlabeled items are treated as internal
    return True


def main():
    token = os.environ.get("PROJECT_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("Set PROJECT_TOKEN to a GitHub token that can read the project.")
    tasks = [to_task(i) for i in fetch_items(token) if visible(i)]
    tasks.sort(key=lambda t: (t["a"] or "9999", t["n"]))
    today = datetime.now(ZoneInfo(TIMEZONE)).date().isoformat()

    html = (ROOT / "template.html").read_text()
    # Escape "</" so issue text can never close the script tag.
    data = json.dumps(tasks, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("__DATA__", data).replace("__TODAY__", today)

    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html)
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    print(f"Built dist/index.html with {len(tasks)} tasks, today = {today}")


if __name__ == "__main__":
    main()
