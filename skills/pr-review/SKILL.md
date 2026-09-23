---
name: pr-review
description: Act on reviewer feedback for an open GitHub PR. Fetches all three feedback channels (inline threads, review bodies, PR-level comments) via GraphQL, checks out the PR branch, classifies each item against current code, assigns round-scoped IDs, persists the report through the save-plan skill, and stops for the user to pick fixes. Use when the user runs /pr-review, or when the pr-review-followup skill needs conversation status.
when_to_use: an open PR has reviewer comments to triage; for reviewing your own branch diff use code-review instead
argument-hint: "[<pr-url>|<pr-number>|<branch>] [clean|new]"
---

# Review PR Comments

GitHub MCP token setup lives in `SETUP.md` next to this file — read it only if
GitHub access fails.

Arguments: $ARGUMENTS

The arguments may contain (in any order, all optional):
- A PR reference — one of: full PR URL (e.g. `https://github.com/owner/repo/pull/3`), PR number (digits only), or a branch name. If absent, the current branch is used.
- The keyword `clean` or `new` (synonyms) — triggers a fresh re-checkout of the PR branch from remote.

## 1. Parse arguments

Split the arguments by whitespace into tokens. Classify each:
- `clean` or `new` → CLEAN_MODE=true (synonyms; case-sensitive lowercase)
- Matches `https?://github\.com/.+/pull/\d+` → PR_URL (extract OWNER, REPO, PR_NUMBER from it)
- Pure digits → PR_NUMBER
- Anything else → BRANCH_NAME

At most one of PR_URL / PR_NUMBER / BRANCH_NAME may be set. If neither is set, the target is the current branch.

## 2. Detect repo metadata

Run this script to get the current branch, remote, and owner/repo:
```bash
~/.claude/scripts/git-pr-info.sh
```
This yields BRANCH (current), REMOTE (e.g. `marinade`, `origin`), OWNER_REPO (e.g. `marinade-finance/stake-liquidator`).

If PR_URL was provided, override OWNER_REPO and PR_NUMBER with values parsed from the URL.

Get the repo's default branch:
```bash
gh repo view OWNER_REPO --json defaultBranchRef -q .defaultBranchRef.name
```
Call the result DEFAULT_BRANCH.

## 3. Resolve PR

If PR_NUMBER is set:
```bash
gh pr view PR_NUMBER --repo OWNER_REPO --json number,title,url,headRefName,baseRefName,state
```

Else (BRANCH_NAME or empty → current branch). Let TARGET = BRANCH_NAME if set, else current BRANCH:
```bash
gh pr list --repo OWNER_REPO --head TARGET --state open --json number,title,url,headRefName,baseRefName -L 1
```

If no open PR is found, abort with:
`No open PR found for branch '<TARGET>' in <OWNER_REPO>.`

Resulting fields: PR_NUMBER, PR_TITLE, PR_URL, HEAD_BRANCH, BASE_BRANCH.

## 4. Check out the PR branch

If CLEAN_MODE is true:
1. If the current branch equals HEAD_BRANCH, switch off it first:
   ```bash
   git checkout DEFAULT_BRANCH
   ```
2. Delete the local branch (ignore "branch not found" — that's fine if it never existed locally):
   ```bash
   git branch -D HEAD_BRANCH
   ```
3. Fetch and check out fresh from the remote:
   ```bash
   git fetch REMOTE HEAD_BRANCH
   ```
   ```bash
   git checkout HEAD_BRANCH
   ```

Else (no clean mode):
```bash
git fetch REMOTE HEAD_BRANCH
```
Then check out HEAD_BRANCH if not already on it:
```bash
git checkout HEAD_BRANCH
```

## 5. Verify base branch

If BASE_BRANCH differs from DEFAULT_BRANCH, this PR targets a non-default base. Note it and also fetch the base so it is available locally for any manual diffing:
```bash
git fetch REMOTE BASE_BRANCH
```

## 6. Fetch all PR feedback via GraphQL

You MUST fetch ALL THREE feedback channels — missing any of them is a bug. Inline
threads ARE NOT the only place reviewers leave actionable feedback. The most
important comments (top-level review summaries with `CHANGES_REQUESTED` or
`COMMENTED` state) live in `reviews.body`, not in `reviewThreads`.

**Delegate the fetch to the `locator` agent** so the raw GraphQL dump never enters
this context. Pass it the query below with OWNER/REPO/PR_NUMBER substituted, and
this task:

> Run the command. Drop `reviewThreads.nodes` entries where `isResolved` is true —
> that field only, nothing else. Return every remaining record verbatim: channel,
> id, author login, path, line, isOutdated, url, and the full body text unchanged.
> Never truncate a body — the ask is often in its last sentence.
> Lead with the ledger line.

Check its ledger arithmetic before going on: threads seen minus resolved must equal
threads returned. If it does not, run the query yourself and do not use the agent's
output.

Fall back to running it inline when the agent is unavailable or the ledger fails.

```bash
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      url
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 20) {
            nodes {
              id
              body
              path
              line
              originalLine
              author { login }
              url
            }
          }
        }
      }
      reviews(first: 100) {
        nodes {
          id
          state
          body
          author { login }
          url
          submittedAt
        }
      }
      comments(first: 100) {
        nodes {
          id
          body
          author { login }
          url
          createdAt
        }
      }
    }
  }
}
' -F owner=OWNER -F repo=REPO -F pr=PR_NUMBER
```

Treat each channel as follows:

- `reviewThreads.nodes` — inline file comments. The `locator` agent has already
  dropped `isResolved` ones; discard any that slipped through. Threads where
  `isOutdated` is true are unresolved but note them as OUTDATED.
- `reviews.nodes` — top-level review submissions. Keep entries where `body` is
  non-empty. These do NOT have a resolved/unresolved state in the API; treat them
  as actionable unless their content is purely informational (e.g. "LGTM",
  Copilot's auto-generated "Pull request overview"). A review whose body asks a
  question or requests a change counts even when `state` is `COMMENTED` — do not
  use `state` to filter, use the body. Skip bot-generated review summaries that
  just describe what the PR does (no action requested).
- `comments.nodes` — PR-level (issue) comments outside of any review or file
  thread. Keep entries with non-empty `body` that ask a question or request a
  change. Skip pure status pings / chitchat.

Paginate if there are more than 100 of any node.

## 7. Check each item against current code

Use GitHub MCP (or `Read`) to fetch current file content at HEAD of the PR branch
for each item. Do not use git diff or git log.

For review-body and issue-comment items, there is no file/line. Resolve them by
checking the repository state the comment refers to — that may be a file
elsewhere in the repo (e.g. "is the namespace added in ecr-auth?" points at
`argocd/ecr-auth/`), a config, or something purely contextual. Search the repo
when needed.

Classify each item:

- FIXED — concern is gone from current code
- PRESENT — concern is still there
- UNCERTAIN — cannot determine; explain why

Classify every item regardless of tone or apparent importance — nitpicks and
style comments count too. Treat review-body comments and issue comments with the
same rigor as inline threads — they often contain the most important asks.

## 8. Detect review round and load prior unaddressed findings

Before assembling the report, look up any prior saved review for this PR/branch
so the current run can pick up where the last one left off.

### 8a. Round detection

Use the `$SAVE_PLAN_PATH` lookup conventions from the `save-plan` skill (resolve
the path via `python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'`).
Scan for files matching this PR/branch, e.g. `*--<HEAD_BRANCH>--pr-<PR_NUMBER>--REVIEW*.md`
or `*--<HEAD_BRANCH>--*REVIEW*.md` if the context arg differs.

**Delegate the scan and the extraction to the `locator` agent** — saved REVIEW
files reach 200KB+ and only the finding index is needed here. Give it this task:

> List the files in <resolved path> matching <glob>, newest by mtime first. From
> the newest one only, return verbatim, for every heading of any level that starts
> with `R<round>#<seq>-P<pri>`: the heading line, the section heading above it, the `file:line`
> reference, and the `Fix plan:` line. Never truncate a fix plan. Omit every other
> line. Also list the distinct `R<n>` values you saw. Lead with the ledger line.

Check the ledger before going on: headings found must equal headings returned.
Take `ROUND` from the highest `R<n>` it reports, plus one. Read the file inline
instead if the agent is unavailable or the ledger fails.

- If no matching file: this is **round 1** → `ROUND = 1`.
- If a matching file exists: parse its findings for the highest `R<n>` in the
  IDs (format `R<n>#<seq>-P<pri>`). Set `ROUND = highest + 1`.

### 8b. Load prior findings and re-verify

For each finding the `locator` returned from the most recent matching prior file:
1. Take its file/line + Fix plan from what the agent returned.
2. Re-check against current code at HEAD of the PR branch.
3. Classify as:
   - **ADDRESSED** — concern is gone. Drop from the new run's outputs (but record the ID as addressed for the summary tally).
   - **STILL_PRESENT** — concern remains. Carry it forward into the new run **keeping its original ID** (do not renumber across rounds — prior `R1#3-P1` stays `R1#3-P1`).
   - **UNCERTAIN** — cannot determine; carry forward with its original ID.

## 9. Assign IDs to current-run findings

Assign a unique ID to every finding generated in this run (step 7).

**Format:** `R<ROUND>#<seq>-P<priority>`

- `<ROUND>` — the round number from 8a.
- `<seq>` — 1-indexed sequence, **unique within this round across all priorities**
  (so `R1#1-P1`, `R1#2-P3`, `R1#3-P1` — seq does not restart per priority).
- `<priority>` — `1` (high), `2` (medium), `3` (low). Pick based on impact/blocker risk.

Examples: `R1#1-P1`, `R1#2-P2`, `R2#1-P1`.

Carried-forward prior findings keep their original IDs (e.g. `R1#3-P1` still
appears in a round-2 run if unaddressed).

## 10. Detailed findings (for the MD file)

Plain text, no emoji, no icons.

Resolve the current date and time by running `date '+%Y-%m-%d %H:%M %Z'` as
its own bash call. It must be the first header line.

Header:
  Reviewed: <YYYY-MM-DD HH:MM TZ>
  PR: <title> / <url> / <branch>
  Base: <BASE_BRANCH>[ (NOT default — default is <DEFAULT_BRANCH>)]
  Round: R<ROUND>
  Inline threads: <total> fetched, <N> resolved (skipped), <N> unresolved
  Review-body comments: <total kept> (out of <total fetched>)
  Issue comments: <total kept> (out of <total fetched>)
  Prior findings re-checked: <N total — A addressed, S still present, U uncertain>  (omit when ROUND == 1)

(Include the default-branch parenthetical only when BASE_BRANCH != DEFAULT_BRANCH.)

For each PRESENT, UNCERTAIN, or OUTDATED item from the current run **and** each
carried-forward STILL_PRESENT / UNCERTAIN prior finding:

  ### <ID> — <one-line title>                      # <ID> is e.g. R1#3-P1
  Status: <STATUS> / Kind: <KIND>
  File: <path>, line <N> — Author: <username>      (omit File/line for review-body and issue-comment items)
  Source: <thread-url | review-url | comment-url>
  Comment: <2-4 sentence summary with a short direct quote>
  Current code: <relevant lines>                   (or repo state checked, if no specific file)
  Reasoning: <why classified this way>
  Fix plan: <exact change needed — file, location, what and why>
  Carried from: R<prev>                            (only for carried-forward findings)

KIND is one of: INLINE-THREAD, REVIEW-BODY, ISSUE-COMMENT.
The `### <ID>` heading is what step 8a's lookup finds in the next round.

Every finding must include **all detail useful for fixing** — file paths,
line numbers, code snippets, the original comment, and the concrete fix.
The MD file is the source of truth; the console table at step 12 is only a
summary.

## 11. Persist the full report via the `save-plan` skill

Invoke the `save-plan` skill with context `pr-<PR_NUMBER>` and the step-10
content as input. `save-plan` resolves the canonical filename (TYPE will be
`REVIEW`) and writes the file under `$SAVE_PLAN_PATH`. Do not write any file
directly.

**This must complete before step 12.** The table is the final user-facing
output and must reflect what is now on disk.

## 12. Final summary table (last step)

After `save-plan` reports the saved file path, print a single summary table
to the chat as the **last** output. No prose after it except
the question in step 13.

Include, in this order:
1. Every carried-forward prior finding still unaddressed (STILL_PRESENT or
   UNCERTAIN from step 8b), in original-ID order across all prior rounds.
2. Every current-run finding (PRESENT / UNCERTAIN / OUTDATED), in ID order.

Table columns:

| ID | Description | Recommendation |
|----|-------------|----------------|

- **ID** — e.g. `R1#3-P1`.
- **Description** — one-line summary (≤ 150 chars) of what / where.
- **Recommendation** — concise concrete fix (≤ 80 chars). Append ` (UNCERTAIN)` or
  ` (OUTDATED)` for current-run findings with that status; PRESENT gets no suffix.
  For carried-forward items append ` (STILL_PRESENT from Rn)` or ` (UNCERTAIN from Rn)`.

Above the table, print in this order:
1. The PR URL, then one line per finding with its links:
   `<ID> comment: <url> code: <url>`. Print full bare URLs, never markdown link
   syntax — it hides the URL in terminals. `comment:` is the `url` from step 6.
   `code:` is `https://github.com/OWNER_REPO/blob/HEAD_BRANCH/<path>#L<line>`
   (`#L<start>-L<end>` for a range), only for findings tied to a file/line.
2. The absolute saved-file path from step 11, on its own line.

## 13. Ask for next action

Then STOP. Do not apply any changes.

If there is more than one finding in the table, ask which to proceed with and
which to decline. If there is exactly one, ask: "Proceed with fix <ID>, or decline?"

Retain thread IDs, file paths, IDs, and dispositions in context for the
follow-up close command.
