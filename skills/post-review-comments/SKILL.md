---
name: post-review-comments
description: Turn findings from this conversation into pending review comments on a GitHub PR — inline threads anchored to a line, a line range or a whole file, plus a draft review body. Everything lands in an unsubmitted (pending) review that nobody but the author can see, so the user edits the text, drops what they disagree with, and submits it themselves. Never posts a PR-level comment, never submits the review, never creates anything immediately visible.
when_to_use: findings are ready to go onto a PR as your own review comments and must stay invisible until the user submits the review themselves; for replying to threads that already exist use answer-existing-review instead
argument-hint: "[all | <finding-ids…> | <free-text target>] [<pr-url>|<pr-number>|<branch>]"
---

# Post Pending Review Comments

Arguments: $ARGUMENTS

GitHub token setup lives in `../pr-review/SETUP.md` — read it only if GitHub
access fails.

This skill **posts**. It does not review, re-triage or re-verify. The findings
already exist in the conversation; the job is to anchor each one to the right
code and park it in a pending review.

"post", "comment", "add" all mean **now, this turn**. Never show a draft and wait
for approval — the pending review *is* the draft, and it lives on GitHub where
the user can edit it.

`<scratch>` below means the session scratchpad directory, or `/tmp` if none is
set.

## 0. The one guarantee

Nothing this skill creates is visible to anyone but the user, and nothing it
creates sends a notification. That holds only as long as the review stays
**pending** — unsubmitted. A pending review carries no `event`, and the user
submits it themselves from the PR's *Files changed* tab.

These are banned outright. Not "prefer to avoid" — banned.

| Banned call | What it would do |
|---|---|
| `gh pr comment` | PR-level comment, visible and notifying immediately |
| `gh pr review --approve` / `--comment` / `--request-changes` | submits the review |
| `POST /pulls/N/reviews` with `event:` set | submits the review |
| `POST /pulls/N/comments` | standalone review comment, visible immediately |
| `submitPullRequestReview` mutation | submits the review |
| `addComment` mutation on the PR | issue comment, visible immediately |
| `deletePullRequestReview` mutation | destroys the user's own pending drafts |
| `resolveReviewThread` mutation | pending threads have nothing to resolve |

If a finding cannot be anchored to a pending thread, it goes in the review body
draft or in the chat report. It never becomes a visible comment to get it onto
the PR.

## 1. Preconditions

Refuse to run and say why if either is missing:

- **An open PR** — from arguments, from the conversation, or from the current branch.
- **Something to say** — at least one finding selected in step 2.

Local git state is irrelevant to whether you post. Do not check whether work is
committed or pushed, and never mention it in a comment. It matters in exactly one
place — step 5, where a line can only be anchored if it exists in the PR's
commits — and even there it is a chat-only note.

## 2. Parse the selection

`$ARGUMENTS` is free-form. Extract two things, both optional:

**The PR target** — a full PR URL, a bare number, or a branch name. Absent → the
conversation's PR, else the current branch.

**The selection** — what to post:

| Form | Meaning |
|---|---|
| `all`, "all findings" | every finding in the current report that is still open |
| finding IDs (`R1#3-P1`, `a b c`, `a+b+c`) | exactly those, in the order given |
| free text naming code ("this line", "the retry loop in fees.ts") | one ad-hoc comment; the user's sentence is the finding |
| nothing | the findings under discussion right now; if that is ambiguous, ask |

Never widen the selection. `a+b+c` means three comments, not the whole report.

## 3. Collect the findings

Take them from context, in this order — stop at the first source that has them:

1. The user's own words in `$ARGUMENTS`, for the ad-hoc form.
2. A review report already in this conversation (`code-review`, `pr-review`,
   `topology-review` output).
3. The saved report for this branch/PR under `$SAVE_PLAN_PATH` — resolve with
   `python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'` and read
   the newest matching file.

Do not go looking for new problems. If the selection names an ID that no source
has, say so and post the rest.

Each finding needs: a file path, a line or range, one sentence of what is wrong,
and — where the report has one — a concrete fix.

## 4. Resolve the PR and the pending review

```bash
~/.claude/scripts/git-pr-info.sh
```

Yields BRANCH, REMOTE, OWNER_REPO. For a branch target:

```bash
gh pr list --repo OWNER_REPO --head TARGET --state open --json number,title,url,headRefName -L 1
```

If no open PR is found, abort with:
`No open PR found for branch '<TARGET>' in <OWNER_REPO>.`

Then read the PR node id, the head commit, and any pending review that already
exists. Pending reviews are visible only to their author, so this is also how you
find drafts the user left behind earlier:

```bash
gh api graphql -F owner=OWNER -F repo=REPO -F pr=PR_NUMBER -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      id
      url
      headRefOid
      reviews(first: 50, states: PENDING) {
        nodes {
          id
          body
          commit { oid }
          comments(first: 100) {
            totalCount
            nodes { id path line startLine subjectType state body }
          }
        }
      }
    }
  }
}
'
```

Do not check out, fetch, or switch branches. This skill only talks to GitHub.

**One pending review per person per PR.** GitHub enforces it — a second
`addPullRequestReview` fails with 422. So:

- **No pending review** → create one (step 7a).
- **A pending review exists** → reuse its `id`. Its `comments.totalCount` is
  drafts the user already wrote; they will be submitted together with yours, so
  say the count in the report.
- **Its `commit.oid` differs from `headRefOid`** → every new thread anchors to
  that older commit, and line numbers must be read from it, not from head. Do not
  fix this by deleting the review — that destroys the user's drafts. Anchor
  against `commit.oid`, and name the mismatch in the loose ends.

Call the anchor commit ANCHOR_COMMIT: the pending review's `commit.oid` when one
exists, otherwise `headRefOid`.

## 5. Anchor each finding

A pending thread can only attach to a line GitHub considers part of the diff — an
added, removed or context line inside a hunk. Everything else is a 422.

Get the hunks for one file:

```bash
gh api repos/OWNER_REPO/pulls/PR_NUMBER/files --paginate --jq '.[] | select(.filename=="<path>") | .patch'
```

(`--jq` is gh's own flag, not a shell pipe.) For a small PR, `gh pr diff
PR_NUMBER --repo OWNER_REPO` in one call is cheaper than one call per file.

Pick the target:

- **RIGHT** side and the post-image line number for anything in the new code —
  the normal case.
- **LEFT** side and the pre-image line number only when the point is about a
  removed line.
- **A range** — `startLine` + `line`, same side — when the defect is the block,
  not the line. Prefer the smallest range that makes the comment legible.
- **The whole file** — `subjectType: FILE`, no line — for a point about the file
  as a whole (a missing export, a file that should not exist). The file still has
  to be part of the diff.

**Verify the anchor before posting.** Read the code at that line in ANCHOR_COMMIT
and confirm it is the code the finding describes. Reports go stale: a finding
carrying line 214 from three commits ago now points at a blank line. When the
line has drifted, re-anchor by searching for the symbol the finding names.

If the code the finding describes is not in the PR's commits at all, it cannot
become a comment. That goes in the chat report as a loose end — never on GitHub,
and never phrased as "not pushed yet".

**Fallback ladder** when a mutation returns `line must be part of the diff`:

1. Retry on the nearest commentable line in the same file that still carries the
   point.
2. Retry as `subjectType: FILE` on the same path, with the line number named in
   the comment text.
3. Give up on the thread, fold the finding into the review body (step 8), and say
   so in the report.

## 6. Compose each comment

You are raising the issue, not answering one. Say what is wrong and what it
costs.

- Starts with the literal prefix `🤖 claude:` — the reader must know a machine
  wrote it.
- **1–2 sentences of prose.** The defect plus the consequence that matters.
  Longer reasoning belongs in the chat, never on GitHub.
- Carries the decisive fact — the value, the call site, the failing input — not a
  vague "this looks wrong".
- Names no local repository state. No "not yet pushed", "uncommitted", no branch
  mechanics. Write it as if the code is already what the PR shows, because from
  the reader's side it is.
- No finding IDs in the body. `R1#3-P1` means nothing to a PR reader; the chat
  report carries the mapping.
- A low-priority point may open `🤖 claude: nit — …`. Nothing else gets a tag.

```
🤖 claude: `parseInt` on the raw amount silently truncates anything past 2^53, so a whale's stake lands short by the remainder.
```

**Suggestions.** A fenced `suggestion` block is one click for the author, so use
one whenever the fix is exactly the anchored lines. It does not count against the
sentence budget.

````
🤖 claude: The rate is a token amount, so `number` arithmetic rounds it before it reaches the ledger.

```suggestion
  const rate = new Decimal(raw).div(LAMPORTS_PER_SOL);
```
````

Rules that make a suggestion apply cleanly: the block replaces the anchored range
exactly — no more lines, no fewer; indentation matches the file character for
character; one block per comment; never on a FILE-level thread.

## 7. Post

**No comment text ever passes through the shell.** It carries apostrophes,
backticks, em-dashes and newlines; a `-f body='…'` argument mangles all of them,
and so does a `python3 -c '…'` one-liner with the text inlined. Always write the
text with the **Write tool** first — the review body to `<scratch>/body-0.md`
(7a), every finding into one `<scratch>/threads.json` payload (7b) — so each
command itself holds nothing but ASCII ids and paths.

### 7a. Create the pending review — only if none exists

`body-0.md` is the review's own text; step 8 says what goes in it.

```bash
python3 -c 'import json;b=open("<scratch>/body-0.md").read();open("<scratch>/review-create.json","w").write(json.dumps({"query":"mutation($pr:ID!,$oid:GitObjectID!,$body:String!){addPullRequestReview(input:{pullRequestId:$pr,commitOID:$oid,body:$body}){pullRequestReview{id state}}}","variables":{"pr":"PR_kwXXX","oid":"ANCHOR_COMMIT","body":b}}))'
```

```bash
gh api graphql --input <scratch>/review-create.json
```

**No `event` field.** That omission is the whole guarantee — with it the review
submits and every comment goes public at once. Confirm `state` comes back
`PENDING` before adding a single thread.

### 7b. Add the threads — one request each, one call

Write every finding into a single payload with the **Write tool**, bodies inline:

```json
{"review_id": "PRR_kwXXX", "threads": [
  {"path": "src/fees.ts", "line": 214, "body": "🤖 claude: …"},
  {"path": "src/fees.ts", "line": 260, "start_line": 254, "body": "🤖 claude: …"},
  {"path": "src/legacy.ts", "subject_type": "FILE", "body": "🤖 claude: …"}
]}
```

`start_line` makes it a range. `"side": "LEFT"` anchors a removed line. A
`subject_type` of `FILE` drops the line anchor for a whole-file thread.

```bash
python3 -c 'import os;exec(open(os.path.expanduser("~/.claude/scripts/gh_pending_threads.py")).read())' <scratch>/threads.json
```

Each finding is still its own mutation, so a rejected anchor — the failure you
will actually hit — stays isolated: the driver prints
`n path:line <thread id | FAILED …>` per finding, continues past a failure, and
exits non-zero if any failed. Never merge the findings into one mutation
document; that is what hides which one GitHub rejected.

**Skip duplicates.** Before adding, compare against the pending review's existing
comments from step 4 — same path, same line, same point. Re-running the skill
must not double-post. Report skipped ones as `skipped (already pending)`.

## 8. The review body

The body is the review's own text — the summary the user rewrites before
submitting. Keep it a starting point, not a report.

One line of framing, then one bullet per finding that could not get a thread:

```
🤖 claude: <N> findings from <what produced them>.

- `src/fees.ts` — <finding> (no diff line to anchor to)
```

Set it at creation (step 7a), or update an existing pending review:

```bash
python3 -c 'import json;b=open("<scratch>/body-0.md").read();open("<scratch>/review-body.json","w").write(json.dumps({"query":"mutation($rev:ID!,$body:String!){updatePullRequestReview(input:{pullRequestReviewId:$rev,body:$body}){pullRequestReview{id body}}}","variables":{"rev":"PRR_kwXXX","body":b}}))'
```

```bash
gh api graphql --input <scratch>/review-body.json
```

**Never overwrite a body the user wrote.** If the existing pending review has a
non-empty body that does not start with `🤖 claude:`, leave it exactly as it is
and put your framing in the chat report instead.

## 9. Verify

Re-run the step 4 query. Every comment you added must come back with `state:
"PENDING"`. A `SUBMITTED` state means the review went public — say that first,
above everything else in the report.

## 10. Report

One line per comment, nothing else. No re-summary of the findings — the comment
already says it and the chat already knows.

```
Pending review: <PR_URL>/files — <N> comments waiting, not submitted
<finding ID> | <path>:<line|start-end|FILE> | <suggestion|—>
```

Pending comments have no working permalink; the per-comment URL only resolves
once the review is submitted. Report `path:line` and link the PR's files tab.

Then these blocks, each only when it applies:

```
In the review body (no thread):
- <finding> — <why it could not be anchored>

Not posted:
- <finding> — <why> — <recommendation>

Loose ends:
- <item>
```

Close with one line: the review is pending and the user submits it from *Files
changed → Finish your review*. Never offer to submit it, and never submit it
because the user said "post" — "post" got the comments onto the PR as drafts,
which is exactly what this skill is for.

Loose ends never delay the posting. Post first, list after.

## Failure modes worth knowing

- **A second pending review.** 422 `user can only have one pending review per
  pull request`. Reuse the existing one; never delete it to get a clean slate.
- **`line must be part of the diff`.** The commonest error. The line is outside
  every hunk, or it is a RIGHT-side number for a line that only exists on the
  LEFT. Walk the fallback ladder in step 5.
- **A stale line number.** A saved report's line drifts as commits land. The
  mutation succeeds and the comment lands on unrelated code — worse than a 422,
  because nothing errors. Verify the anchor against ANCHOR_COMMIT first.
- **Shell quoting.** An apostrophe inside `-f body='…'` breaks the argument, and
  a backtick workaround renders as a literal backtick in the posted comment.
  Inlining the same text in a `python3 -c '…'` one-liner breaks identically — the
  quote character is the problem, not the tool. Text goes to a file via Write;
  the shell only ever sees the file's path.
- **A suggestion that will not apply.** The block has to replace the anchored
  range exactly. One extra line, or indentation off by a space, and the author
  gets a diff they must fix by hand.
- **`event: COMMENT` slipping in.** Some `gh` examples include it by default.
  Copying one submits the review and publishes every draft comment at once,
  irreversibly.
