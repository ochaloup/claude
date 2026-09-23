---
name: pr-review-followup
description: Second (or later) round on a GitHub PR you already reviewed — computes the diff since your last review, gets conversation status from the pr-review skill, runs the code-review skill scoped to the new commits, adds a backwards-check against earlier PR commits, and unifies everything into one report saved via save-plan.
when_to_use: a PR you previously reviewed has new commits or new replies and needs another round; for a first-time pass use pr-review
argument-hint: "[<pr-url>|<pr-number>]"
---

# PR Review Follow-up

Follow up on a PR you previously reviewed: find what changed since your last review,
check conversation status via `pr-review`, review new code via `code-review`, and
produce a unified report.

This skill reuses two existing skills:
- `pr-review` — for fetching and classifying review threads
- `code-review` — for reviewing code changes

Arguments: $ARGUMENTS

## 1. Resolve PR and your last review

### 1a. Resolve PR info

Run the same setup as `pr-review`:
```bash
~/.claude/scripts/git-pr-info.sh
```
```bash
git fetch <REMOTE>
```

If the arguments contain a full URL or number, use it. Otherwise find the open PR
for the current branch:
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
   - exit code 0 → set REVIEW_BASE = LAST_REVIEW_COMMIT, skip item 2 below.
   - exit code 1 (force-push or rebase happened) → continue to item 2 below.

2. Resolve the merge-base:
   ```bash
   git merge-base <LAST_REVIEW_COMMIT> HEAD
   ```
   Set REVIEW_BASE = stdout of that command.

Store REVIEW_BASE. This is the starting point for "new changes since your review."

## 2. Run the `pr-review` skill for conversation status

Invoke the `pr-review` skill with the resolved PR number as its argument.

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

## 3. Run the `code-review` skill scoped to new changes

Invoke the `code-review` skill with the diff base set to the review anchor:
`--base <REVIEW_BASE>`

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

This step happens **once** for the whole followup, after the sub-skills
in steps 2 and 3 have produced their raw findings.

### 4a. Round detection

Use the `$SAVE_PLAN_PATH` lookup conventions from the `save-plan` skill (resolve
via `python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'`). Scan
for prior saved followup/review files matching this PR/branch — typical names
`*--<HEAD_BRANCH>--pr-<PR_NUMBER>*REVIEW*.md`.

- If no matching file: this is the first followup → `ROUND = 2`
  (round 1 is the original `pr-review` even if it wasn't saved).
- If a matching file exists: parse its findings for the highest `R<n>` and set
  `ROUND = highest + 1`.

### 4b. Load prior findings and re-verify

For each finding in the most recent matching prior file, re-check against the
current HEAD of the PR branch and classify:

- **ADDRESSED** — concern is gone. Record the ID in the addressed tally only.
- **STILL_PRESENT** — concern remains. Carry forward keeping its original ID.
- **UNCERTAIN** — cannot determine; carry forward with its original ID.

Do not renumber prior IDs.

### 4c. Trace each new finding to its origin

A follow-up round reviews code that was largely written to satisfy the previous
round. So a new finding is often not a fresh regression — it is a gap in a fix the
last review asked for. That changes who owns it and how it reads on the PR, and it
is invisible unless you correlate the two sets deliberately.

For every finding this run produced (Sections A, B, C), decide where the code it
anchors to came from:

- **`fix for <prior ID>`** — the code was written to address a prior finding. Find
  it by locating the finding's hunk in `git diff <REVIEW_BASE>..HEAD` and matching
  it against that prior finding's Fix plan. Highest-signal outcome: the review
  caused this one.
- **`new`** — code added in `REVIEW_BASE..HEAD` that no prior finding asked for.
- **`pre-existing`** — the code predates `REVIEW_BASE`. Confirm with
  `git log --oneline <REVIEW_BASE>..HEAD -- <path>` returning nothing. The finding
  is new to the *review*, not to the code — the earlier round missed it. Say that,
  so it does not read as a regression.

A finding caused by another finding of this same round records that chain, e.g.
`fix for P2-R2#8`.

For each `fix for <prior ID>`, name which pattern it follows — they need different
responses:

- **Cheaper substitute** — the fix closed the finding by removing the thing (a test
  deleted, a feature dropped) instead of doing what was asked. State what was lost.
- **Incomplete attempt** — the fix is right in shape and misses an edge.

When the prior round's own suggested fix would not have avoided the new defect
either, say so in that finding's Assessment. The review owns that, not the author.

Tally for the header: how many new findings trace back to prior-round fixes.

## 5. Verify against description in notion task

If you have access to notion (Marinade the most probably) and the PR title
has got with format [GEN-<number>] then find the Notion task with that `GEN` id
and read the description and verify that the implemented code matches the description.

## 6. Assign IDs to current-run findings

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

## 7. Unified detailed report (for the MD file)

Combine everything into a single document. Plain text, no emoji, no icons.

Before rendering the header, resolve both header values in one bash call:
```bash
python3 -c 'import subprocess,datetime;print(subprocess.run(["git","rev-list","<REVIEW_BASE>..HEAD","--count"],capture_output=True,text=True).stdout.strip());print(datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"))'
```
First stdout line is NEW_COMMIT_COUNT, second is the `Reviewed:` timestamp, which
must be the header's first line.

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
Fix lineage: <N> of <M> new findings caused by prior-round fixes, <N> new code, <N> pre-existing   (omit when no prior file)
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
### <ID> — <one-line title>
[STATUS] [MY_THREAD|OTHERS_THREAD] [INLINE-THREAD|REVIEW-BODY|ISSUE-COMMENT]
File: <path>, line <N> — Author: <username>     (omit File/line for REVIEW-BODY and ISSUE-COMMENT)
Permalink / Source: <full clickable URL — no markdown shortening>
Original comment: <verbatim quote of the single sub-ask, plus 1-2 sentences of context>
Latest reply: <summary of last comment, if any>           (INLINE-THREAD only)
Current code / state: <relevant lines, or repo state checked>
Origin: <fix for <prior ID> — cheaper substitute|incomplete attempt | new | pre-existing>   (from step 4c)
Assessment: <why classified this way>
Fix plan: <concrete change, or "None — resolve thread" / "Decline">
```

### Section B: New Changes Review (from code-review)

Use the code-review output. IDs continue the same round (e.g. `P1-R2#5`).

```
### <ID> — <one-line title>
[SEVERITY: high|medium|low]
Category: <objective name>
File: <path>, lines <start>-<end>
Permalink: <full clickable URL>
Origin: <fix for <prior ID> — cheaper substitute|incomplete attempt | new | pre-existing>   (from step 4c)
Issue: <description>
Suggested fix: <concrete fix>
```

### Section C: Backwards-check Findings (if any)

Same format as B, with `[BACKWARDS-CHECK]` before the severity tag.

### Section D: Carried-forward prior findings (if any)

Reproduce STILL_PRESENT / UNCERTAIN entries from step 4b in their original IDs,
with current code re-check notes.

```
### <ID> — <one-line title>
[STILL_PRESENT | UNCERTAIN] (carried from R<prev>)
File: <path>, line <N>
Original finding: <one-paragraph recap from prior MD>
Current code: <relevant lines>
Assessment: <why still present / why uncertain>
Fix plan: <unchanged or updated fix plan>
```

### Section E: Summary

- How many of your review comments were addressed vs still pending
- Top concerns from new changes
- How many new findings the previous round's fixes caused, and whether the pattern
  is cheaper substitutes or incomplete attempts — a round that is mostly the former
  needs a conversation about fix quality, not another list of defects
- Whether the PR looks closer to mergeable or needs another round

The MD must contain **all detail useful for fixing** — file paths, line
numbers, permalinks, code snippets, and concrete fixes. The console table in
step 9 is only a summary.

## 8. Persist the full report via the `save-plan` skill

Invoke the `save-plan` skill with context `pr-<PR_NUMBER>-followup` and the
step-7 content as input. `save-plan` resolves the canonical filename (TYPE will
be `REVIEW`) and writes the file under `$SAVE_PLAN_PATH`. Do not write any file
directly. Every finding must include the full clickable GitHub permalink.

**This must complete before step 9.**

## 9. Final summary table (last output)

After `save-plan` reports the saved file path, print a single table to the
chat as the **last** output. No prose after it except the
question in step 10.

Include, in this order:
1. Every carried-forward prior finding still unaddressed (Section D), in
   original-ID order across all prior rounds.
2. Every current-run finding (Sections A, B, C) in ID order.

Table columns:

| ID | Description | Origin | Status / Recommendation |
|----|-------------|--------|--------------------------|

- **ID** — e.g. `P1-R2#1`.
- **Description** — one-line summary (≤ 150 chars).
- **Origin** — from step 4c: `fix for <prior ID>`, `new`, or `pre-existing`. Keep
  it to that; the pattern (cheaper substitute / incomplete attempt) lives in the MD.
  Leave blank for Section D rows — a carried-forward finding has no origin, it *is*
  the origin.
- **Status / Recommendation** —
  - Section A items: `PRESENT`, `ADDRESSED_IN_DISCUSSION`, `OUTDATED`, `UNCERTAIN`, or `STILL_PRESENT (Rn)`.
  - Section B/C items: short recommendation (≤ 80 chars).
  - Section D items: `STILL_PRESENT (Rn)` or `UNCERTAIN (Rn)`.

### Fix-lineage block

The Origin column answers "where did this one come from" per row. It cannot show a
single fix that spawned two defects, or a chain. Print this block directly above the
table, grouped by the **prior** finding, so both are visible at a glance:

```
Caused by prior-round fixes (<N> of <M> new findings):
  <prior ID>  <what was done>        -> <new ID>, <new ID>
  <prior ID>  <what was done>        -> <new ID> -> <new ID>
```

`<what was done>` is three or four words naming the change, not the defect — "anchor
added", "lookahead removed", "test deleted". An arrow chain shows a second-order
cause. Omit the whole block when nothing traces back; a clean round should print
nothing rather than an empty heading.

Above that, print the absolute saved-file path from step 8 on its own line.

## 10. Ask for next action

STOP. Do not apply any changes. Ask the user which IDs to act on and which to
decline.
