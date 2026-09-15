import json, subprocess, sys

FIELDS = ("$rev:ID!,$path:String!,$body:String!,$line:Int,$start:Int,"
          "$side:DiffSide,$startSide:DiffSide,$subject:PullRequestReviewThreadSubjectType")
MUT = ("mutation(" + FIELDS + "){addPullRequestReviewThread(input:{"
       "pullRequestReviewId:$rev,path:$path,body:$body,line:$line,startLine:$start,"
       "side:$side,startSide:$startSide,subjectType:$subject}){thread{id}}}")

payload = json.load(open(sys.argv[1], encoding="utf-8"))
rev = payload["review_id"]

failed = 0
for n, t in enumerate(payload["threads"], 1):
    where = t["path"] + (":%s" % t["line"] if t.get("line") else " (file)")
    body = {"query": MUT, "variables": {
        "rev": rev, "path": t["path"], "body": t["body"],
        "line": t.get("line"), "start": t.get("start_line"),
        "side": t.get("side") or (None if t.get("subject_type") else "RIGHT"),
        "startSide": t.get("start_side") or (t.get("side") if t.get("start_line") else None),
        "subject": t.get("subject_type"),
    }}
    p = subprocess.run(["gh", "api", "graphql", "--input", "-"],
                       input=json.dumps(body), capture_output=True, text=True)
    out, err = (p.stdout or "").strip(), (p.stderr or "").strip()
    if p.returncode or '"errors"' in out:
        failed += 1
        print("%d  %s  FAILED  %s" % (n, where, (err or out)[:300]))
    else:
        tid = json.loads(out)["data"]["addPullRequestReviewThread"]["thread"]["id"]
        print("%d  %s  %s" % (n, where, tid))

print("---\n%d threads, %d failed" % (len(payload["threads"]), failed))
sys.exit(1 if failed else 0)
