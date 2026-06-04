# PR Review Follow-up

Follow up on a PR you previously reviewed: find what changed since your last review,
check conversation status via `pr-review`, review new code via `code-review`, and
produce a unified report.

This command reuses two existing commands:
- `/pr-review` — for fetching and classifying review threads
- `/code-review` — for reviewing code changes

## 1. Resolve PR and your last review

### 1a. Resolve PR info

Run the same setup as `pr-review`:
```bash
~/.claude/scripts/git-pr-info.sh
```
```bash
git fetch <REMOTE>
```

If $ARGUMENTS is a full URL or number, use it. Otherwise find the open PR for
the current branch:
```bash
gh pr view --json number,url,title,headRefName,baseRefName,headRefOid
```

Store: OWNER, REPO, PR_NUMBER, PR_URL, HEAD_BRANCH, BASE_BRANCH, HEAD_SHA.

### 1b. Identify yourself

```bash
gh api user --jq '.login'
```
Store as MY_LOGIN.

### 1c. Find your latest review

```bash
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviews(first: 100) {
        nodes {
          author { login }
          state
          submittedAt
          commit { oid }
        }
      }
    }
  }
}
' -F owner=OWNER -F repo=REPO -F pr=PR_NUMBER
```

Filter to `author.login == MY_LOGIN`, take the most recent by `submittedAt`.
Store:
- LAST_REVIEW_DATE
- LAST_REVIEW_COMMIT (the `commit.oid`)
- LAST_REVIEW_STATE (APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED)

If no review found: warn the user, fall back to merge-base as diff anchor,
and skip the "since your review" scoping — treat everything as new.

### 1d. Compute the diff anchor

Run each command separately (no pipes, no `;`, no redirects — one command per bash call):

1. Check whether LAST_REVIEW_COMMIT is still an ancestor of HEAD:
   ```bash
   git merge-base --is-ancestor <LAST_REVIEW_COMMIT> HEAD
   ```
   - exit code 0 → set REVIEW_BASE = LAST_REVIEW_COMMIT, skip step 2.
   - exit code 1 (force-push or rebase happened) → continue to step 2.

2. Resolve the merge-base:
   ```bash
   git merge-base <LAST_REVIEW_COMMIT> HEAD
   ```
   Set REVIEW_BASE = stdout of that command.

Store REVIEW_BASE. This is the starting point for "new changes since your review."

## 2. Run `/pr-review` for conversation status

Execute the `pr-review` command with the resolved PR number: `/pr-review <PR_NUMBER>`

This will:
- Fetch all three feedback channels via GraphQL:
  1. `reviewThreads` (inline file threads)
  2. `reviews` (top-level review-body submissions — including bundled UX nits, design
     notes, and other actionable asks that don't anchor to a file/line)
  3. `comments` (PR-level issue comments outside any thread)
- Discard resolved threads
- Classify each unresolved item (FIXED, PRESENT, UNCERTAIN, OUTDATED)
- Produce a numbered report with permalinks

**Treat all three channels as equally actionable.** Review-body submissions in
particular often contain the most important asks (your own previous review, UX
nits, scope notes). Do **not** skip them just because they aren't anchored to a
file/line.

**Split bundled review-body / issue-comment asks.** A single review-body can
contain N distinct sub-asks (bullets, numbered list, "and... and... and"). Each
sub-ask becomes its own finding with its own ID — *do not* collapse them into
one entry. Quote the sub-ask verbatim. If you find yourself writing one Section A
entry whose `Original comment:` field contains multiple bullets, that's a sign
you need to split it.

**Additional follow-up classification on top of pr-review output:**

After `pr-review` finishes its classification, enrich each finding with:

1. **Thread ownership** — mark each as `[MY_THREAD]` or `[OTHERS_THREAD]` based on
   whether the first comment author (or for review-body items, the review author)
   `== MY_LOGIN`. Sort your items first in the report.

2. **Item kind** — tag each finding with `[INLINE-THREAD]`, `[REVIEW-BODY]`, or
   `[ISSUE-COMMENT]` so reviewers can see at a glance what channel it came from.

3. **Addressed-in-discussion detection** — for PRESENT inline threads, check if a
   later comment in the thread provides a satisfactory explanation or rebuttal.
   If so, reclassify as `ADDRESSED_IN_DISCUSSION`. (Not applicable to
   review-body / issue-comment items, which usually don't have replies.)

4. **Fix-in-new-commits correlation** — for FIXED items, check whether the fix
   appears in the new-changes diff (`REVIEW_BASE..HEAD`). If yes, note
   "fixed in post-review commits". If not, note "was already fixed at time of review
   (stale thread)".

## 3. Run `/code-review` scoped to new changes

Run the `code-review` command with the diff base set to the review anchor:
```
/code-review --base <REVIEW_BASE>
```

This reviews only the changes made **after** your last review, applying all
standard code-review objectives (logical flaws, regression risk, data correctness,
dead code, code quality, simplification, reusability, security, config consistency).

### 3a. Light backwards-check

After the scoped code-review completes, do one additional pass:

- Read the **full PR diff** (`git diff <REMOTE>/<BASE_BRANCH>..HEAD`)
- For each finding from the scoped review, check if the new code contradicts,
  duplicates, or regresses something from the older part of the PR
- For new files/functions introduced after your review, check if they duplicate
  logic that already existed in earlier PR commits

Report any backwards-check findings separately, tagged `[BACKWARDS-CHECK]`.

## 4. Detect round and load prior unaddressed findings

This step happens **once** for the whole followup, after the sub-commands
in steps 2 and 3 have produced their raw findings.

### 4a. Round detection

Use the `$SAVE_PLAN_PATH` lookup conventions from `/save-plan` (resolve via
`python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'`). Scan
for prior saved followup/review files matching this PR/branch — typical names
`*--<HEAD_BRANCH>--pr-<PR_NUMBER>*REVIEW*.md`.

- If no matching file: this is the first followup → `ROUND = 2`
  (round 1 is the original `/pr-review` even if it wasn't saved).
- If a matching file exists: parse its findings for the highest `R<n>` and set
  `ROUND = highest + 1`.

### 4b. Load prior findings and re-verify

For each finding in the most recent matching prior file, re-check against the
current HEAD of the PR branch and classify:

- **ADDRESSED** — concern is gone. Record the ID in the addressed tally only.
- **STILL_PRESENT** — concern remains. Carry forward keeping its original ID.
- **UNCERTAIN** — cannot determine; carry forward with its original ID.

Do not renumber prior IDs.

## 5. Assign IDs to current-run findings

Assign IDs to findings produced in steps 2 (conversation enrichment) and 3
(scoped code-review + backwards-check).

**Format:** `P<priority>-R<ROUND>#<seq>`

- `<priority>` — `1` (high), `2` (medium), `3` (low). For conversation-status
  items, derive from author intent / severity of the change request. For
  code-review items, derive from existing severity.
- `<ROUND>` — from step 4a.
- `<seq>` — 1-indexed across **all** sections of this run (A → B → C), unique
  within the round.

Carried-forward prior findings keep their original IDs.

## 6. Unified detailed report (for the MD file)

Combine everything into a single document. Plain text, no emoji, no icons.

Before rendering the header, run as its own bash call:
```bash
git rev-list <REVIEW_BASE>..HEAD --count
```
Use the stdout as NEW_COMMIT_COUNT.

Resolve the current date and time by running `date '+%Y-%m-%d %H:%M %Z'` as
its own bash call. It must be the first header line.

### Header
```
Reviewed: <YYYY-MM-DD HH:MM TZ>
PR: <title>
URL: <PR_URL>
Branch: <HEAD_BRANCH> -> <BASE_BRANCH>
Your last review: <LAST_REVIEW_STATE> at <LAST_REVIEW_DATE> (commit <short LAST_REVIEW_COMMIT>)
New commits since review: <NEW_COMMIT_COUNT>
Round: R<ROUND>
Prior findings re-checked: <N total — A addressed, S still present, U uncertain>   (omit when no prior file)
```

### Section A: Conversation Status (from pr-review + enrichment)

Use the pr-review output, enriched with ownership, kind, and fix-correlation.
Cover **all three channels**: inline threads, review-body submissions, and
PR-level issue comments. List YOUR items first.

Bundled review-body items must already have been split into per-sub-ask findings
during the enrichment in step 2 — Section A should never contain a single
finding whose `Original comment:` is a multi-bullet list.

Header:
```
Open items: <total> (<N inline threads>, <N review-body sub-asks>, <N issue comments>) — <N> yours, <N> others
```

For each item:
```
<ID> [STATUS] [MY_THREAD|OTHERS_THREAD] [INLINE-THREAD|REVIEW-BODY|ISSUE-COMMENT]
File: <path>, line <N> — Author: <username>     (omit File/line for REVIEW-BODY and ISSUE-COMMENT)
Permalink / Source: <full clickable URL — no markdown shortening>
Original comment: <verbatim quote of the single sub-ask, plus 1-2 sentences of context>
Latest reply: <summary of last comment, if any>           (INLINE-THREAD only)
Current code / state: <relevant lines, or repo state checked>
Assessment: <why classified this way>
Fix plan: <concrete change, or "None — resolve thread" / "Decline">
```

### Section B: New Changes Review (from code-review)

Use the code-review output. IDs continue the same round (e.g. `P1-R2#5`).

```
<ID> [SEVERITY: high|medium|low]
Category: <objective name>
File: <path>, lines <start>-<end>
Permalink: <full clickable URL>
Issue: <description>
Suggested fix: <concrete fix>
```

### Section C: Backwards-check Findings (if any)

Same format as B, prefixed `[BACKWARDS-CHECK]`.

### Section D: Carried-forward prior findings (if any)

Reproduce STILL_PRESENT / UNCERTAIN entries from step 4b in their original IDs,
with current code re-check notes.

```
<ID> [STILL_PRESENT | UNCERTAIN] (carried from R<prev>)
File: <path>, line <N>
Original finding: <one-paragraph recap from prior MD>
Current code: <relevant lines>
Assessment: <why still present / why uncertain>
Fix plan: <unchanged or updated fix plan>
```

### Section E: Summary

- How many of your review comments were addressed vs still pending
- Top concerns from new changes
- Whether the PR looks closer to mergeable or needs another round

The MD must contain **all detail useful for fixing** — file paths, line
numbers, permalinks, code snippets, and concrete fixes. The console table in
step 8 is only a summary.

## 7. Persist the full report via /save-plan

Execute `/save-plan pr-<PR_NUMBER>-followup` with the step-6 content as input.
`/save-plan` resolves the canonical filename (TYPE will be `REVIEW`) and writes
the file under `$SAVE_PLAN_PATH`. Do not write any file directly. Every finding
must include the full clickable GitHub permalink.

**This must complete before step 8.**

## 8. Final summary table (last step)

After `/save-plan` reports the saved file path, print a single table to the
chat as the **last** output of the command. No prose after it except the
question in step 9.

Include, in this order:
1. Every carried-forward prior finding still unaddressed (Section D), in
   original-ID order across all prior rounds.
2. Every current-run finding (Sections A, B, C) in ID order.

Table columns:

| ID | Description | Status / Recommendation |
|----|-------------|--------------------------|

- **ID** — e.g. `P1-R2#1`.
- **Description** — one-line summary (≤ 150 chars).
- **Status / Recommendation** —
  - Section A items: `PRESENT`, `ADDRESSED_IN_DISCUSSION`, `OUTDATED`, `UNCERTAIN`, or `STILL_PRESENT (Rn)`.
  - Section B/C items: short recommendation (≤ 80 chars).
  - Section D items: `STILL_PRESENT (Rn)` or `UNCERTAIN (Rn)`.

Above the table print the absolute saved-file path from step 7 on its own line.

## 9. Ask for next action

STOP. Do not apply any changes. Ask the user which IDs to act on and which to
decline.
