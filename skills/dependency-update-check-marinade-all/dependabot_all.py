#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.expanduser("~/.claude/skills/code-review-marinade-all"))
from review_all import ORG, REMOTE, ROOT, SKIP_REPOS, Fail, find_remote, git, run, update_default  # noqa: E402

WORKTREES = os.path.join(ROOT, ".dependabot-worktrees")
INACTIVE_DAYS = 365
RED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED"}
RED_STATES = {"FAILURE", "ERROR"}
BUMP = re.compile(r"\bbump (\S+) from \S+ to (\S+)", re.IGNORECASE)
QUERY = """query($endCursor: String) {
  search(query: "is:pr is:open author:app/dependabot org:%s", type: ISSUE, first: 40, after: $endCursor) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest {
      number title url isDraft reactionGroups { content viewerHasReacted }
      repository { name isArchived defaultBranchRef { target { ... on Commit { committedDate } } } }
      commits(last: 1) { nodes { commit { statusCheckRollup { state contexts(first: 50) { nodes {
        ... on CheckRun { name conclusion checkSuite { workflowRun { workflow { name } } } }
        ... on StatusContext { context state }
      } } } } } }
    } }
  }
}""" % ORG


def failing_checks(rollup):
    names = []
    for c in rollup["contexts"]["nodes"]:
        if c.get("conclusion") in RED_CONCLUSIONS or c.get("state") in RED_STATES:
            workflow = ((c.get("checkSuite") or {}).get("workflowRun") or {}).get("workflow", {}).get("name")
            names.append("%s / %s" % (workflow, c["name"]) if workflow else c.get("name") or c["context"])
    return list(dict.fromkeys(names))


def workdir(repo, number):
    return os.path.join(WORKTREES, "%s-%d" % (repo, number))


def triage(only_repo):
    out = run(["gh", "api", "graphql", "--paginate", "-f", "query=" + QUERY, "--jq", ".data.search.nodes[]"]).stdout
    prs = [json.loads(line) for line in out.splitlines() if line.strip()]
    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS)
    newest = {}
    for pr in prs:
        m = BUMP.search(pr["title"])
        if m:
            key = (pr["repository"]["name"], m.group(1))
            newest[key] = max(newest.get(key, 0), pr["number"])
    rows = []
    for pr in sorted(prs, key=lambda p: (p["repository"]["name"], p["number"])):
        repo = pr["repository"]
        if only_repo and repo["name"] != only_repo:
            continue
        rollup = (pr["commits"]["nodes"] or [{}])[0].get("commit", {}).get("statusCheckRollup")
        row = {"status": "CHECK", "repo": repo["name"], "number": pr["number"], "title": pr["title"],
               "url": pr["url"], "ci": rollup["state"] if rollup else "NONE", "detail": ""}
        rows.append(row)
        last = (repo["defaultBranchRef"] or {}).get("target", {}).get("committedDate")
        m = BUMP.search(pr["title"])
        if repo["name"] in SKIP_REPOS:
            row.update(status="SKIPPED", detail="skip-list repo")
        elif repo["isArchived"]:
            row.update(status="SKIPPED", detail="archived repo")
        elif not last or datetime.fromisoformat(last.replace("Z", "+00:00")) < cutoff:
            row.update(status="SKIPPED", detail="inactive repo, last default-branch commit %s" % (last or "never")[:10])
        elif pr["isDraft"]:
            row.update(status="SKIPPED", detail="draft")
        elif any(g["content"] == "EYES" and g["viewerHasReacted"] for g in pr["reactionGroups"]):
            row.update(status="SKIPPED", detail="parked")
        elif m and newest[(repo["name"], m.group(1))] != pr["number"]:
            row.update(status="SUPERSEDED", detail="newer bump of %s in #%d" % (m.group(1), newest[(repo["name"], m.group(1))]))
        elif row["ci"] in RED_STATES:
            row.update(status="CI-RED", detail=", ".join(failing_checks(rollup)) or "no failing check reported")
    return rows


def prepare(repo, number):
    main_dir = os.path.join(ROOT, repo)
    if not os.path.isdir(main_dir):
        run(["git", "clone", "-q", "-o", REMOTE, "git@github.com:%s/%s.git" % (ORG, repo), main_dir])
    remote = find_remote(main_dir, repo)
    view = json.loads(run(["gh", "pr", "view", str(number), "--repo", "%s/%s" % (ORG, repo),
                           "--json", "headRefName,baseRefName"]).stdout)
    _, warn = update_default(main_dir, remote)
    base = view["baseRefName"]
    git(main_dir, "fetch", "-q", remote, "+refs/heads/%s:refs/remotes/%s/%s" % (base, remote, base))
    ref = "refs/remotes/%s/pr/%d" % (remote, number)
    git(main_dir, "fetch", "-q", remote, "+pull/%d/head:%s" % (number, ref))
    wd = workdir(repo, number)
    git(main_dir, "worktree", "prune")
    if os.path.isdir(wd):
        git(main_dir, "worktree", "remove", "--force", wd)
    os.makedirs(WORKTREES, exist_ok=True)
    git(main_dir, "worktree", "add", "-q", "--detach", wd, ref)
    return {"dir": wd, "base": "%s/%s" % (remote, base), "branch": view["headRefName"], "warn": warn or ""}


def park(url):
    m = re.fullmatch(r"https://github\.com/%s/([^/]+)/pull/(\d+)/?" % ORG, url)
    if not m:
        raise Fail("not a %s PR URL: %s" % (ORG, url))
    run(["gh", "api", "-X", "POST", "repos/%s/%s/issues/%s/reactions" % (ORG, m.group(1), m.group(2)),
         "-f", "content=eyes", "--silent"])
    return {"parked": url}


def cleanup(repo, number):
    git(os.path.join(ROOT, repo), "worktree", "remove", "--force", workdir(repo, number))
    return {"removed": workdir(repo, number)}


def main():
    args = sys.argv[1:]
    try:
        if args[:1] == ["triage"]:
            result = triage(args[2] if args[1:2] == ["--repo"] else None)
        elif args[:1] == ["prepare"]:
            result = prepare(args[1], int(args[2]))
        elif args[:1] == ["cleanup"]:
            result = cleanup(args[1], int(args[2]))
        elif args[:1] == ["park"]:
            result = [park(url) for url in args[1:]]
        else:
            sys.exit("usage: dependabot_all.py triage [--repo <name>] | prepare <repo> <n> | cleanup <repo> <n> | park <pr-url>...")
    except Fail as e:
        result = {"error": str(e)}
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
