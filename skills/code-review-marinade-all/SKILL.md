---
name: code-review-marinade-all
description: Find every open marinade-finance PR awaiting my review, prepare each repo under ~/marinade (clone, update the default branch, force-reset the PR branch), and open one yakuake tab per PR with a tmux session running the Claude command (--claude, default the current session's subscription) — this skill's --first mode for a first review, its --followup mode for a re-requested one. Skip-list repos, drafts, PRs I reacted to with 👀, docs-only PRs and PRs waiting for the author are listed, not reviewed. Ends with two tables, launched and not reviewed. The first mode reviews, gates each finding through a fresh agent and parks the survivors in a pending review only I can see; the followup mode replies to and resolves my own threads the author addressed or declined for a reason that holds. Nothing is ever submitted.
when_to_use: the user wants all pending marinade-finance review requests set up for review in one go; the user still reads each result, edits the pending review and submits it
model: sonnet
argument-hint: "[--dry-run] [--claude <cmd>] [--max <n>] | --first <pr-url> [--retro <pr-url>] | --followup <pr-url>"
---

# Code review — all marinade PRs

Arguments: $ARGUMENTS

With `--first <pr-url>` go to **First mode**, with `--followup <pr-url>` to
**Followup mode**. Otherwise run the launcher.

## Launcher

Run as one bash call, passing `--dry-run`, `--claude <cmd>` and `--max <n>` through when given:

```
python3 ~/.claude/skills/code-review-marinade-all/review_all.py [--dry-run] [--claude <cmd>] [--max <n>]
```

`--max` caps the `rev-*` tmux sessions alive at once, default 7; each runs a Claude
process and more of them run the machine out of memory. Sessions already open count.

`--claude` is the shell command typed into each tab's `claude` window, e.g. `claude-work`
or `CLAUDE_CONFIG_DIR=~/.claude-x claude`. Quote it as one argument. Default: the current
session's subscription, i.e. `claude` with this session's `CLAUDE_CONFIG_DIR` when set.

It prints a JSON list, one row per PR found by
`review-requested:@me org:marinade-finance`. `status` is one of:

- `LAUNCHED` — repo prepared, tmux session `rev-<repo>-<n>` started with windows
  `claude` and `bash`, yakuake tab `<repo>#<n>` attached to it.
- `READY` — `--dry-run` only: would be launched.
- `OPEN` — the tmux session already exists; nothing touched.
- `QUEUED` — would be launched, but `--max` sessions are already alive; repo not
  touched, no tab. `detail` is the mode it would get.
- `MANUAL` — `ansible` repo: passes every filter below but I review it by hand;
  repo not touched, no tab. `detail` is the mode it would get.
- `NOT-REVIEWED` — skip-list repo, draft, parked (my 👀 reaction on the PR
  description), docs only, or I reviewed and the author has not re-requested me yet.
- `FAILED` — clone, fetch, checkout or launch failed; `detail` says why.

Never fix a `FAILED` row. Uncommitted changes and diverged branches are the
user's call — never stash, reset or check out to get past one. The skip list
comes from `MARINADE_ALL_SKIP_REPOS` (comma-separated repo names, empty when unset).
The docs rule and directory layout live in `review_all.py`; edit them there.

### Output

One bold line: `<l> launched, <q> queued, <m> manual, <n> not reviewed, <f> failed`. Then two tables.
Summary is one short line written from the PR title — what the PR does, no
ticket id. PR is a markdown link `[<repo>#<n>](<url>)`.

Launched (`LAUNCHED`, `READY`, `OPEN`, `MANUAL`):

| PR | Summary | Mode | Tab / directory |
|----|---------|------|-----------------|

Not reviewed (`QUEUED`, `NOT-REVIEWED`, `FAILED`), `QUEUED` rows first with Reason
`queued (<mode>)`:

| PR | Summary | Reason |
|----|---------|--------|

A `WARN` in a launched row's detail (default branch not fast-forwarded) goes
into its Mode cell. A `MANUAL` row's Mode cell is `TODO (manual, <detail>)`, its
Tab / directory cell `—`.

No `QUEUED` row → nothing after the tables. Otherwise ask with AskUserQuestion:
"<q> reviews queued. Close finished `rev-*` sessions (`tmux kill-session -t <name>`),
then continue?" — options `Continue` and `Stop`. On `Continue` run the launcher again
with the same arguments and print its output the same way; on `Stop`, stop.

## First mode

Runs inside a launched tab for a PR I have not reviewed yet.

0. **Checkout check.** Run `gh pr view <pr-url> --json headRefOid` and `git rev-parse HEAD`
   as two calls. Not a git repo, or the two differ → stop with one line:
   `Checkout is not the PR head (<HEAD> vs <headRefOid>) — run the launcher, or gh pr checkout <n> in the repo.`
   Never fetch, reset or check out to get past it. The same check opens Followup mode.
1. Invoke the `code-review` skill with `--deep --summary`. Run it through its final
   table, then continue to step 2 in the same turn.
2. **Gate.** The review decided which findings are real; this re-checks which are
   worth a comment, from a cold context that never saw the review's reasoning. Write
   the findings to `<scratch>/gate-input.md` with the Write tool, one block each: ID,
   `file:line`, the claim, the failure scenario, the recommendation. Add the `skip:`
   lines from the lessons files code-review loaded. Then:
   ```
   Agent({ subagent_type: "general-purpose", model: "sonnet",
           description: "Gate review findings",
           prompt: "Read-only: no edits, no git state changes, no GitHub writes. Every bash
                    call is one plain command. Read <scratch>/gate-input.md. The repo is
                    <cwd>, the PR diff is `git diff <BASE_REF>`. For each finding read the
                    code at HEAD and rule: POST — the defect is real, a caller can reach
                    it, and a reviewer would want the comment; DROP — refuted, pure style,
                    outside what this PR touches or reaches, or matching a skip line; ASK
                    — real, but a design or product call the human must make. At most
                    three P3 findings get POST. Return only one line per finding:
                    `<ID> | POST|DROP|ASK | <file:line> | <one-sentence reason>`." })
   ```
   Gate unavailable or errored → post nothing, say so first, go to step 4.
3. Invoke `post-review-comments` with the POST IDs, comma-joined, and the PR URL.
   No POST rows → skip it in one line.
4. Invoke `review-lesson` with the PR URL, plus `--retro <url>` when this mode was
   given one.
5. Print the gate's lines as a table — `ID | Gate | Reason` — then the pending review
   line from step 3, then the **PR digest**, then `PR: <PR URL>` as the last line, and
   stop. ASK rows stay off GitHub; posting one is the user's `post-review-comments` run.

## Followup mode

Runs inside a launched tab for a PR I already reviewed and was re-requested on.

1. Run the checkout check from First mode, step 0. Then invoke the `pr-review-followup`
   skill with the PR URL. Run it through its
   final table. Its closing STOP is about code changes; continue to step 2 in the
   same turn.
2. From its Section A, take items that are all of: `[MY_THREAD]`, `[INLINE-THREAD]`,
   unresolved. Of those, select:
   - `FIXED` — resolve.
   - `ADDRESSED_IN_DISCUSSION`, and `PRESENT` where the author replied declining —
     send to the gate below; resolve only what it ACCEPTs.

   Nothing else is touched — not others' threads, not review-body or issue items, not
   `UNCERTAIN` or `OUTDATED`, not a `PRESENT` thread with no author reply.

   **Decline gate.** Write each declined thread to `<scratch>/decline-input.md` with
   the Write tool: my original comment, the author's reply verbatim, `file:line`. Then:
   ```
   Agent({ subagent_type: "general-purpose", model: "sonnet",
           description: "Gate declined threads",
           prompt: "Read-only: no edits, no git state changes, no GitHub writes. Every bash
                    call is one plain command. Read <scratch>/decline-input.md. The repo
                    is <cwd> at the PR head. For each thread read the code and rule:
                    ACCEPT — the author's reason holds against the code; REJECT — it does
                    not, or it defers a real defect with no follow-up. Return only one line
                    per thread: `<ID> | ACCEPT|REJECT | <one-sentence reason>`." })
   ```
   Gate unavailable or errored → resolve only the `FIXED` ones and say so first.
3. Fetch the thread ids with the GraphQL query from the `answer-existing-review`
   skill, step 2. Write the batch JSON with the Write tool, in that skill's
   step 6 format, `resolve: true` on every entry. One reply per thread,
   1 sentence, prefixed `🤖 claude:`, naming the decisive fact:
   `🤖 claude: Resolved — the query now filters on the requested epochs in fetch_flat_validators.`
   For an ACCEPTed decline: `🤖 claude: Resolved — agreed with the explanation above, <the gate's reason>.`
4. Post and resolve:
   ```
   python3 -c 'import os;exec(open(os.path.expanduser("~/.claude/scripts/gh_reply_threads.py")).read())' <scratch>/replies.json
   ```
5. Invoke `review-lesson` with the PR URL. `pre-existing` findings are its
   earlier-round misses.
6. Under the followup table print one line per thread, `<ID> | resolved | <reply URL>`,
   then one per REJECTed decline, `<ID> | left open | <the gate's reason>`, then one
   per WEAK or WRONG row of the followup's **Prior comments**, `<ID> | <handling> |
   <strategy sentence>` — already resolved by the author, so reopening it is my call,
   then the **PR digest**, then `PR: <PR URL>` as the last line, and stop. New findings stay in
   the report — posting them is the user's `post-review-comments` run.

## PR digest

Both modes print it right above the `PR:` line, so I learn what the PR is about
without scrolling up. Reuse what this conversation printed under **Changes under
review** — from `code-review`, or from `pr-review-followup`, which produces it even with
no new commits: the PR block (Problem, Core change, Goal, bullets), then the
`Approach fit:` line. Copy them verbatim; do not rewrite or regenerate them. It is
never skipped; if neither skill printed it, that is a blocker.
