#!/usr/bin/env python3
import json
import os
import subprocess
import sys

ORG = "marinade-finance"
REMOTE = "marinade"
ROOT = os.path.expanduser("~/marinade")
WORKTREES = os.path.join(ROOT, ".review-worktrees")
SKIP_REPOS = {r.strip() for r in os.environ.get("MARINADE_ALL_SKIP_REPOS", "").split(",") if r.strip()}
DOC_EXTS = (".md", ".mdx", ".txt", ".rst", ".adoc", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
DOC_DIRS = ("docs/", "doc/")

os.environ["GIT_TERMINAL_PROMPT"] = "0"


class Fail(Exception):
    pass


def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        last = (p.stderr.strip() or p.stdout.strip()).splitlines()[-1:] or ["exit %d" % p.returncode]
        raise Fail("%s: %s" % (" ".join(cmd[:3]), last[0]))
    return p


def git(repo, *args, check=True):
    return run(["git", "-C", repo, *args], check=check)


def is_doc(path):
    return path.lower().endswith(DOC_EXTS) or path.startswith(DOC_DIRS) or "/docs/" in path


def tmux_sessions():
    p = run(["tmux", "list-sessions", "-F", "#{session_name}"], check=False)
    return set(p.stdout.split()) if p.returncode == 0 else set()


def find_remote(repo, name):
    for line in git(repo, "remote", "-v").stdout.splitlines():
        remote, url = line.split()[:2]
        if url.rstrip("/").removesuffix(".git").endswith("%s/%s" % (ORG, name)):
            return remote
    raise Fail("no remote points to %s/%s" % (ORG, name))


def worktrees_holding(main_dir, branch):
    paths, path = set(), None
    for line in git(main_dir, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == "branch refs/heads/" + branch:
            paths.add(path)
    return paths


def update_default(main_dir, remote):
    head = git(main_dir, "symbolic-ref", "--short", "-q", "refs/remotes/%s/HEAD" % remote, check=False).stdout.strip()
    if not head:
        git(main_dir, "remote", "set-head", remote, "--auto")
        head = git(main_dir, "symbolic-ref", "--short", "refs/remotes/%s/HEAD" % remote).stdout.strip()
    branch = head.removeprefix(remote + "/")
    git(main_dir, "fetch", "-q", remote, branch)
    if git(main_dir, "rev-parse", "-q", "--verify", "refs/heads/" + branch, check=False).returncode != 0:
        git(main_dir, "branch", branch, "%s/%s" % (remote, branch))
        return branch, None
    current = git(main_dir, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    if current == branch:
        p = git(main_dir, "merge", "-q", "--ff-only", "%s/%s" % (remote, branch), check=False)
    else:
        p = git(main_dir, "fetch", "-q", remote, "%s:%s" % (branch, branch), check=False)
    return branch, None if p.returncode == 0 else "local %s not fast-forwarded" % branch


def prepare(pr, main_dir, workdir):
    name = pr["repo"]
    if not os.path.isdir(main_dir):
        run(["git", "clone", "-q", "-o", REMOTE, "git@github.com:%s/%s.git" % (ORG, name), main_dir])
    remote = find_remote(main_dir, name)
    if os.path.isdir(workdir) and git(workdir, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise Fail("uncommitted changes in " + workdir)
    default, warn = update_default(main_dir, remote)
    if pr["fork"]:
        local, ref = "pr-%d" % pr["number"], "refs/remotes/%s/pr/%d" % (remote, pr["number"])
        git(main_dir, "fetch", "-q", remote, "+pull/%d/head:%s" % (pr["number"], ref))
    else:
        local, ref = pr["branch"], "refs/remotes/%s/%s" % (remote, pr["branch"])
        git(main_dir, "fetch", "-q", remote, "+refs/heads/%s:%s" % (pr["branch"], ref))
    if local == default:
        raise Fail("PR branch is the default branch " + default)
    git(main_dir, "worktree", "prune")
    for path in worktrees_holding(main_dir, local) | ({workdir} if workdir != main_dir and os.path.isdir(workdir) else set()):
        if path != main_dir:
            git(main_dir, "worktree", "remove", path)
    if workdir == main_dir:
        git(workdir, "checkout", "-q", "--no-track", "-B", local, ref)
    else:
        os.makedirs(WORKTREES, exist_ok=True)
        git(main_dir, "worktree", "add", "-q", "--no-track", "-B", local, workdir, ref)
    if not pr["fork"]:
        git(workdir, "branch", "-q", "--set-upstream-to", "%s/%s" % (remote, pr["branch"]))
    return local, warn


def launch(session, workdir, prompt, title):
    run(["tmux", "new-session", "-d", "-s", session, "-n", "claude", "-c", workdir])
    run(["tmux", "new-window", "-d", "-t", session, "-n", "bash", "-c", workdir])
    run(["tmux", "send-keys", "-t", session + ":claude", "claude-work '%s'" % prompt, "Enter"])
    sid = run(["qdbus6", "org.kde.yakuake", "/yakuake/sessions", "addSession"]).stdout.strip()
    tid = run(["qdbus6", "org.kde.yakuake", "/yakuake/sessions", "terminalIdsForSessionId", sid]).stdout.strip().split(",")[0]
    run(["qdbus6", "org.kde.yakuake", "/yakuake/tabs", "setTabTitle", sid, title])
    run(["qdbus6", "org.kde.yakuake", "/yakuake/sessions", "runCommandInTerminal", tid, "tmux attach -t " + session])


def main():
    dry = "--dry-run" in sys.argv[1:]
    me = run(["gh", "api", "user", "--jq", ".login"]).stdout.strip()
    found = json.loads(run(["gh", "search", "prs", "--review-requested=@me", "--owner=" + ORG, "--state=open",
                            "--sort=updated", "--json", "repository,number,title,isDraft,url", "--limit", "100"]).stdout)
    sessions = tmux_sessions()
    used = set()
    rows = []
    for item in found:
        name, number = item["repository"]["name"], item["number"]
        session = "rev-%s-%d" % (name, number)
        row = {"status": "", "pr": "%s#%d" % (name, number), "title": item["title"], "detail": "", "dir": "", "url": item["url"]}
        rows.append(row)
        if name in SKIP_REPOS:
            row.update(status="NOT-REVIEWED", detail="skip-list repo")
            continue
        if item["isDraft"]:
            row.update(status="NOT-REVIEWED", detail="draft")
            continue
        if session in sessions:
            row.update(status="OPEN", detail="tmux session %s already exists" % session)
            continue
        try:
            eyes = run(["gh", "api", "-X", "GET", "--paginate", "repos/%s/%s/issues/%d/reactions" % (ORG, name, number),
                        "-f", "content=eyes", "--jq", ".[].user.login"]).stdout.split()
            if me in eyes:
                row.update(status="NOT-REVIEWED", detail="parked")
                continue
            view = json.loads(run(["gh", "pr", "view", str(number), "--repo", "%s/%s" % (ORG, name), "--json",
                                   "files,headRefName,headRepositoryOwner,reviews,reviewRequests"]).stdout)
            if view["files"] and all(is_doc(f["path"]) for f in view["files"]):
                row.update(status="NOT-REVIEWED", detail="docs only")
                continue
            reviewed = any(r["author"]["login"] == me and r["state"] != "PENDING" for r in view["reviews"])
            # Submitting a review drops my personal request; only a re-request adds it back.
            if reviewed and not any(r.get("login") == me for r in view["reviewRequests"]):
                row.update(status="NOT-REVIEWED", detail="reviewed, waiting for author to re-request")
                continue
            pr = {"repo": name, "number": number, "branch": view["headRefName"],
                  "fork": view["headRepositoryOwner"]["login"] != ORG}
            main_dir = os.path.join(ROOT, name)
            busy = name in used or any(s.startswith("rev-%s-" % name) for s in sessions)
            workdir = os.path.join(WORKTREES, "%s-%d" % (name, number)) if busy else main_dir
            used.add(name)
            row["dir"] = workdir
            if dry:
                row.update(status="READY", detail="followup" if reviewed else "review --deep")
                continue
            local, warn = prepare(pr, main_dir, workdir)
            prompt = "/code-review-marinade-all --followup " + item["url"] if reviewed else "/code-review --deep"
            launch(session, workdir, prompt, row["pr"])
            row.update(status="LAUNCHED", detail="%s on %s, tmux %s%s" % (
                "followup" if reviewed else "review --deep", local, session, "; WARN " + warn if warn else ""))
        except Fail as e:
            row.update(status="FAILED", detail=str(e))
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
