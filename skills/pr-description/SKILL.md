---
name: pr-description
description: Compose a brief, human-readable PR description for the active branch from the conversation context, the saved work documents under $K, and the actual branch diff. One lead sentence plus one bullet per change, each stating intention over implementation. Prints raw markdown for copy&paste into the GitHub PR; writes it to the PR only when invoked with `apply`.
when_to_use: a branch is finished (code reviewed, review comments addressed) and its PR body needs to be written or refreshed
argument-hint: "[<pr-url>|<pr-number>|<branch>] [apply]"
---

# PR Description

Arguments: $ARGUMENTS

Produce the PR body the author pastes into GitHub. The audience is a reviewer or
a future colleague reading the merged PR in the history — they want to know
**what changed and why**, in under a minute.

## 1. Parse arguments

Tokens, any order, all optional:

- `apply` → APPLY=true (write the result to the PR at step 7)
- Matches `https?://github\.com/.+/pull/\d+` → PR_URL (extract OWNER_REPO, PR_NUMBER)
- Pure digits → PR_NUMBER
- Anything else → BRANCH_NAME

At most one of PR_URL / PR_NUMBER / BRANCH_NAME. With none, the target is the
current branch.

## 2. Resolve branch, repo, base

```bash
~/.claude/scripts/git-pr-info.sh
```
Yields BRANCH, REMOTE, OWNER_REPO. PR_URL overrides OWNER_REPO and PR_NUMBER.

Resolve the PR if one exists — by number:
```bash
gh pr view PR_NUMBER --repo OWNER_REPO --json number,title,url,headRefName,baseRefName,body,state
```
or by branch (TARGET = BRANCH_NAME if set, else BRANCH):
```bash
gh pr list --repo OWNER_REPO --head TARGET --state open --json number,title,url,headRefName,baseRefName,body -L 1
```

BASE_BRANCH comes from the PR. **No PR yet is fine** — the skill still works
(that is the point of pre-filling an empty description). In that case get the
base from:
```bash
gh repo view OWNER_REPO --json defaultBranchRef -q .defaultBranchRef.name
```
With APPLY=true and no PR, stop and say so: there is nothing to write to.

Make the base available locally:
```bash
git fetch REMOTE BASE_BRANCH
```

## 3. Gather the three input channels

All three. Skipping one produces a description that misses either the *why*
(channels a, b) or an actual change (channel c).

**a. This conversation** — the primary source of *intention*. What the user
asked for, the problem being solved, decisions and their rationale, constraints
accepted. This is the material that cannot be recovered from the diff.

**b. Saved work documents under `$K`** — resolve the literal path once:
```bash
python3 -c 'import os; print(os.environ.get("K",""))'
```
Never use `$K` in a bash command — Claude Code's shell-expansion guard prompts
for any `$VAR` use regardless of allow-list rules. Use the resolved literal
string in every subsequent operation, and prefer `Glob` / `Read` over shell.

Files there follow `<DIR>--<BRANCH>--[<CONTEXT>--]<TYPE>.md`, where DIR is the
basename of the repo directory and `/` in the branch became `-`. Glob for, in
order of usefulness:

```
<DIR>--<BRANCH>--*.md          # PLAN, IMPLEMENTATION_DETAIL, INVESTIGATION, REVIEW
*--<BRANCH>--*.md              # fallback when DIR differs from the repo folder name
```

Read what matches. Use each type for what it is good for:

- `PLAN` / `DESIGN` — the goal and the approach. Best source for the lead sentence.
- `INVESTIGATION` — the root cause. Best source for the *why* behind a fix.
- `IMPLEMENTATION_DETAIL` — decisions and edge cases; mine for reasons, not for prose to reuse.
- `REVIEW` (including `*--pr-<N>--REVIEW.md`) — why a given fix exists. **Not** a
  change list: see the net-effect rule in step 4.

If nothing matches, proceed on channels a and c and say so in the sources line
at step 6. Do not ask the user to point at a file.

**c. The actual branch diff** — the completeness check, so nothing shipped goes
undescribed and nothing described was never shipped.

```bash
git log --oneline BASE_BRANCH..HEAD
```
```bash
git diff --stat BASE_BRANCH...HEAD
```
Read the diff itself for any area the conversation and documents do not explain.
Three dots (merge base) — not two.

## 4. Build the change list

**Describe the net effect of the branch against its base.** Not the history of
how it got there. A bug introduced mid-branch and fixed after review is not two
bullets and not one bullet about the fix — it is invisible, because against the
base it never existed. Review rounds, follow-up commits, and reverted attempts
never appear.

One bullet per change a reviewer would care about, ordered most significant
first, mechanical last. Merge everything that serves a single purpose into one
bullet, however many files it touched. Split one commit into two bullets when it
did two unrelated things.

Leave out, unless it is the point of the PR: formatting, lint fixes, dependency
bumps, generated files, import shuffles, renames with no behavioural effect.

Target 3–7 bullets. Above 10, the grouping is too fine — merge. Whole body under
~120 words.

Every bullet must trace to a real change in the diff, and every substantive
change in the diff must land in a bullet or be a conscious drop per the list
above.

## 5. Write it

```markdown
<one sentence: what this branch accomplishes, and for whom or why>

- <verb-first sentence: the change, and the intention behind it>
- <...>
```

**Lead sentence.** Present tense, states the outcome. No `This PR…`, no
`In this change…`. If the branch has one purpose, name it; if it genuinely has
two, one sentence still covers both.

**Bullets.** Each is exactly one sentence, verb-first, no trailing period
needed but be consistent. State the intention or the reason, not the mechanism.
Where the reason is not self-evident from the change, carry it in a short
`so …` / `since …` / `to …` clause — that clause is the value of the bullet.

Write the reason, not the recipe:

| Instead of | Write |
|---|---|
| Added a `checked_sub` call in `fund_settlement` at the lamports subtraction | Guard bond funding against underflow so one withdrawn stake account no longer aborts the whole batch |
| Changed `is_funded` to return true when balance is 0 | Treat a zero-balance bond as fundable, since dev clusters legitimately have them |
| Refactored `Watcher` into `WatcherCore` + `WatcherHandle` and moved 200 lines | Split the revoke watcher so a stalled RPC subscription can be restarted without dropping in-flight work |
| Bumped the timeout from 30s to 120s | Raise the collector timeout to survive the slow epoch-boundary RPC responses that were failing the pipeline nightly |

Style:

- No emoji, no icons, no `🤖 claude:` prefix. This is the author's own PR body,
  not a Claude review response — the transparency prefix belongs on PR comments.
- No file lists, no line numbers, no function-by-function walkthrough. An
  identifier in backticks is fine when it is the clearest name for the thing.
- No `## Summary` / `## Changes` / `## Testing` headings. The lead sentence and
  the bullets are the whole document.
- No hedging (`should probably`), no filler (`As part of this work`), no
  restating the branch name or ticket ID as a bullet.
- Tests get a bullet only when they are worth a reviewer's attention — a
  regression test pinning the reported bug, or new coverage of a risky path.
  Routine test updates that accompany a change belong inside that change's bullet.

## 6. Output

Print, in this order and nothing else:

1. One line naming the sources actually used, e.g.
   `Sources: conversation, validator-bonds--fix-fund-one-sol--INVESTIGATION.md, 7 commits vs main`
   or `Sources: conversation, 4 commits vs main (no saved document for this branch)`.
2. The description in a fenced ` ```markdown ` block — flush left, no trailing
   whitespace, ready to paste.

No summary of what you did, no restatement of the bullets, no offer of
alternatives.

## 7. Apply (only when APPLY=true)

Write the block's content — without the fence — to a temp file with `Write`,
then:
```bash
gh pr edit PR_NUMBER --repo OWNER_REPO --body-file <path>
```
This overwrites the existing body. If the current body has content that is not
reproduced in the new description, show that content and ask before overwriting.
Print the PR URL afterwards.

Without `apply`, never touch the PR — printing is the whole job.
