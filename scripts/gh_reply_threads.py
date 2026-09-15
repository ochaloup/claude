import json, subprocess, sys

RESOLVE = "mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{id isResolved}}}"

payload = json.load(open(sys.argv[1], encoding="utf-8"))
repo, pr = payload["repo"], payload["pr"]

def run(args, stdin=None):
    p = subprocess.run(args, input=stdin, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


failed = 0
for t in payload["threads"]:
    tid = t["thread_id"]
    rc, out, err = run(
        ["gh", "api", "repos/%s/pulls/%s/comments/%s/replies" % (repo, pr, t["comment_id"]),
         "--input", "-"],
        json.dumps({"body": t["body"]}),
    )
    if rc:
        failed += 1
        print("%s  reply=FAILED  %s" % (tid, (err or out)[:200]))
        continue
    url = (json.loads(out).get("html_url") or "") if out.startswith("{") else ""
    if not t.get("resolve"):
        print("%s  reply=ok  resolve=skipped(human)  %s" % (tid, url))
        continue
    rc, out, err = run(["gh", "api", "graphql", "-F", "t=" + tid, "-f", "query=" + RESOLVE])
    if rc or '"isResolved":true' not in out.replace(" ", ""):
        failed += 1
        print("%s  reply=ok  resolve=FAILED  %s  %s" % (tid, (err or out)[:200], url))
    else:
        print("%s  reply=ok  resolve=ok  %s" % (tid, url))

print("---\n%d threads, %d failed" % (len(payload["threads"]), failed))
sys.exit(1 if failed else 0)
