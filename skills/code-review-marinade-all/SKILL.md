---
name: code-review-marinade-all
description: Find every open marinade-finance PR awaiting my review, prepare each repo under ~/marinade (clone, update the default branch, force-reset the PR branch), and open one yakuake tab per PR with a tmux session running claude-work — /code-review --deep for a first review, this skill's --followup mode for a re-requested one. Skip-list repos, drafts, PRs I reacted to with 👀, docs-only PRs and PRs waiting for the author are listed, not reviewed. Ends with two tables, launched and not reviewed. Never posts new review comments; the followup mode only replies to and resolves my own threads the author addressed.
when_to_use: the user wants all pending marinade-finance review requests set up for review in one go; the user still reads each result and posts with post-review-comments
model: sonnet
argument-hint: "[--dry-run] | --followup <pr-url>"
---

# Code review — all marinade PRs

Arguments: $ARGUMENTS

With `--followup <pr-url>` go to **Followup mode**. Otherwise run the launcher.

## Launcher

Run as one bash call, passing `--dry-run` through when given:

```
python3 ~/.claude/skills/code-review-marinade-all/review_all.py [--dry-run]
```

It prints a JSON list, one row per PR found by
`review-requested:@me org:marinade-finance`. `status` is one of:

- `LAUNCHED` — repo prepared, tmux session `rev-<repo>-<n>` started with windows
  `claude` and `bash`, yakuake tab `<repo>#<n>` attached to it.
- `READY` — `--dry-run` only: would be launched.
- `OPEN` — the tmux session already exists; nothing touched.
- `NOT-REVIEWED` — skip-list repo, draft, parked (my 👀 reaction on the PR
  description), docs only, or I reviewed and the author has not re-requested me yet.
- `FAILED` — clone, fetch, checkout or launch failed; `detail` says why.

Never fix a `FAILED` row. Uncommitted changes and diverged branches are the
user's call — never stash, reset or check out to get past one. The skip list
comes from `MARINADE_ALL_SKIP_REPOS` (comma-separated repo names, empty when unset).
The docs rule and directory layout live in `review_all.py`; edit them there.

### Output

One bold line: `<l> launched, <n> not reviewed, <f> failed`. Then two tables.
Summary is one short line written from the PR title — what the PR does, no
ticket id. PR is a markdown link `[<repo>#<n>](<url>)`.

Launched (`LAUNCHED`, `READY`, `OPEN`):

| PR | Summary | Mode | Tab / directory |
|----|---------|------|-----------------|

Not reviewed (`NOT-REVIEWED`, `FAILED`):

| PR | Summary | Reason |
|----|---------|--------|

A `WARN` in a launched row's detail (default branch not fast-forwarded) goes
into its Mode cell. Nothing after the tables.

## Followup mode

Runs inside a launched tab for a PR I already reviewed and was re-requested on.

1. Invoke the `pr-review-followup` skill with the PR URL. Run it through its
   final table. Its closing STOP is about code changes; continue to step 2 in the
   same turn.
2. From its Section A, select items that are all of: `[MY_THREAD]`,
   `[INLINE-THREAD]`, unresolved, status `FIXED` or `ADDRESSED_IN_DISCUSSION`.
   Nothing else is touched — not others' threads, not review-body or issue items,
   not `PRESENT`, `UNCERTAIN` or `OUTDATED`.
3. Fetch the thread ids with the GraphQL query from the `answer-existing-review`
   skill, step 2. Write the batch JSON with the Write tool, in that skill's
   step 6 format, `resolve: true` on every entry. One reply per thread,
   1 sentence, prefixed `🤖 claude:`, naming the decisive fact:
   `🤖 claude: Resolved — the query now filters on the requested epochs in fetch_flat_validators.`
   For `ADDRESSED_IN_DISCUSSION`: `🤖 claude: Resolved — agreed with the explanation above, <one reason>.`
4. Post and resolve:
   ```
   python3 -c 'import os;exec(open(os.path.expanduser("~/.claude/scripts/gh_reply_threads.py")).read())' <scratch>/replies.json
   ```
5. Under the followup table print one line per thread, `<ID> | resolved | <reply URL>`,
   then `PR: <PR URL>` as the last line, and stop. New findings stay in the
   report — posting them is the user's `post-review-comments` run.
