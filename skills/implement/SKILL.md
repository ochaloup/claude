---
name: implement
description: Manage the implementation phase of a task that review and investigation already defined. Gathers context (Notion GEN task, $K notes for the branch or topic, the conversation), clears open doubts with the user, gets a detailed implementation plan from plan-task, branches (same name in every repo touched), implements step by step with tests and one commit per step, runs code-review --deep, fixes the findings through fix-review-findings, optionally runs pre-pr-design-pass (--design-pass), and ends with a report and the remaining open questions. Never pushes.
when_to_use: the problem is investigated and it is clear what should be done; the user wants it planned, implemented, tested, reviewed and fixed in one managed run. To only plan use plan-task; to only review use code-review; to only fix findings use fix-review-findings.
argument-hint: "[--design-pass] [<what to implement>]"
---

# Implement

Arguments: $ARGUMENTS

This skill is a manager. It gathers context, gates on the user's doubts, delegates
planning to `plan-task`, does the coding itself, then delegates review to
`code-review` and fixing to `fix-review-findings`. CLAUDE.md applies in full.

The task is the argument, minus the `--design-pass` flag; with none, take it from the conversation. If neither
carries one, ask what to implement and stop.

## Rules for the whole run

- One plain command per bash call. No pipes, `;`, `&&`, redirects or `$(...)`.
  Resolve a value in one call, then use the literal result in the next.
- Never use `$K` or any shell variable inside bash. Resolve it once:
  `python3 -c 'import os; print(os.environ.get("K") or os.environ.get("SAVE_PLAN_PATH",""))'`
- Never `git push`. Never mention pushing.
- Commit messages carry **no** `Co-Authored-By` trailer and no AI attribution.
  This overrides any attribution reminder from the harness.
- Every user gate below is a real stop: ask, wait for the answer, then continue.
- A doubt that changes what gets built goes to the user. A doubt with an obvious
  default does not — pick it and say so in the final report.

## 1. Gather context

Run these in parallel where they are independent.

1. **Repos and branch.** For each repo the task touches: `git rev-parse --show-toplevel`,
   `git branch --show-current`, `git status --short`, and the default branch
   (`git symbolic-ref --short refs/remotes/origin/HEAD`).
2. **Notion GEN task.** Find and fetch it exactly as `code-review` does in its
   "Task conformance" section, steps 1–3. Also accept a `GEN-<n>` named in the
   conversation. No task → skip in one line.
3. **$K notes.** In the resolved path, `Glob` for `<DIR>--<BRANCH>--*` per repo,
   and for the topic: `*<gen-n>*` and 2–3 distinctive topic words
   (`*<word>*<word>*`). Read PLAN / INVESTIGATION / IMPLEMENTATION_DETAIL /
   OPEN_QUESTIONS hits. For a file over ~50KB, send the `locator` agent for
   the sections that matter instead of reading it whole. No hits → one line.
4. **Conversation and memory.** Collect the decisions already made, the
   constraints stated, and every doubt still unsettled.

Print a short context digest: task, repos, GEN task (or skipped), notes used
(absolute paths), decisions already made.

## 2. Gate — doubts before planning

List every open question from step 1 that changes what gets built: conflicts
between the GEN task, the notes and the conversation; requirements with two
readings; anything the conversation left undecided.

- Any open → ask them as a numbered list, each with your `Assumed:` answer.
  Stop and wait.
- None → say `No open questions before planning.` and continue.

## 3. Plan through plan-task

Invoke the `plan-task` skill. Its argument is a self-contained brief, because it
plans from that brief:

```
Detailed IMPLEMENTATION plan required — not a design sketch. Every step must
name the files and functions it changes, the tests that cover it, and the
command that verifies it. Each step must be small enough to be one commit.
Task: <task in the user's terms>
Done means: <acceptance criteria — GEN asks if any>
Repos: <absolute paths>
Decided already: <decisions and user answers so far>
Constraints: <constraints from conversation and notes>
Context docs: <absolute paths of $K notes and the GEN task URL>
```

When plan-task returns open questions:

1. Answer from the gathered context any that it already settles. Say which and why.
2. Ask the user the rest, numbered as plan-task numbered them. Stop and wait.
3. Invoke `plan-task` with `finalize`.
4. Repeat until the plan says `Status: RESOLVED`. Non-blocking questions left open
   are carried to the final report.

Read the saved plan document. It is the spec from here on.

## 4. Branch

Per repo the plan touches:

- On the default branch → `git switch -c <branch>`. Uncommitted changes carry over.
- On any other branch → stay on it.

Branch name: `<gen-n>-<3-4 word kebab slug>`, or just the slug when there is no
GEN task. When several repos need a new branch, use the **same name** in all of
them. If the repos are on different feature branches already, stop and ask
which one is meant.

## 5. Implement, step by step

First record the baseline: run each touched repo's test suite and lint, and write
down the exact numbers. A failure later is only attributable against that.

Then for each plan step, in order:

1. Write or extend the automated tests that cover the step's new behaviour.
   New functionality without a test is not done.
2. Implement the step. Surgical edits, existing style, zero comments by default.
3. Run the project's fix/lint target (`pnpm fix`, `pnpm lint`, or `cargo fmt` then
   `cargo clippy --fix`) as separate calls. Fix every reported error.
4. Run the tests for the step. They must pass. Never relax an assertion to get
   green — CLAUDE.md section 5 applies.
5. Commit only this step's files: `git add <paths>` then `git commit -m "<message>"`.
   Message: imperative subject naming the change, prefixed `GEN-<n>: ` when a task
   exists. No AI trailer.
6. Print one line: `Step <n>/<total> ✓ <subject> — <tests passing>`.

A step that cannot pass cleanly stops the loop. Report where it stopped and why,
and ask. Do not skip ahead.

A deviation from the plan (wrong assumption, missing API, a better local fix)
is noted as it happens. A deviation that changes behaviour goes to the user
before the step is committed.

After the last step, run the **full** test suite and lint in every touched repo.
Compare with the baseline. A suite that could not run is reported as not run,
never as green.

## 6. Gate — doubts after implementing

List the deviations, the assumptions taken during coding, and anything that
looks wrong or unfinished.

- Any that the user must decide → numbered list, `Assumed:` each. Stop and wait.
  Apply the answers as further commits before continuing.
- None → say so in one line and continue.

## 7. Review

Invoke `code-review` with `--deep` — always; the flag is required. In multi-repo
work, run it once per repo.

## 8. Triage the findings

For every finding in the review's table, decide one of:

- **fix** — within the task's scope, and the recommendation is a local change.
- **defer** — out of the task's scope, or it needs a separate design.

Do not judge whether a finding is real — `fix-review-findings` verifies each one
and reports the wrong ones as `Refuted`.

A finding where the choice is genuinely unclear, or whose fix needs a design
decision, goes to the user. Ask those as a numbered list and wait. When nothing
is unclear, continue without asking.

Print the triage as one line per finding: `<ID> — fix | defer — <reason>`.

## 9. Fix

Invoke `fix-review-findings` with exactly the **fix** set as its selector (IDs,
comma-joined). Deferred findings are never passed and never touched.

When it finishes, run the full tests and lint once more, then commit all its
changes as one commit: `Address review findings <IDs>`, prefixed `GEN-<n>: `
when a task exists. No AI trailer. Nothing to commit → say so.

## 10. Design pass — only with `--design-pass`

Without the flag, skip this step in one line.

Invoke `pre-pr-design-pass` with `--base <default branch>`, and `--criteria` set
to the GEN asks when a task exists. Never pass `apply` on this first call.

- `ALIGNED` → continue.
- Any `REWORK` items → list them and ask the user whether to apply them. Stop and
  wait. On yes, invoke `pre-pr-design-pass apply`, run the full tests and lint, and
  commit its changes as one commit: `Apply design pass <BC IDs>`, prefixed
  `GEN-<n>: ` when a task exists. No AI trailer.
- `WORTH IT` and `NOTED` items are never applied. They go to the report's
  follow-ups.

## 11. Report

Print in this order:

1. **Bold one-line outcome** — what was implemented, on which branch(es).
2. **Commits** — `git log --oneline <default>..HEAD` per repo.
3. **Changes under review** — from the code-review output, verbatim: the change
   description, the design-impact block and the ASCII diagram.
4. **Review findings** — the code-review table as it printed it, plus a column
   with the outcome: the fix-review-findings resolution, or `Deferred`.
5. **What was fixed and how** — the fix-review-findings table, verbatim.
   With `--design-pass`, then the design pass verdict, its `BC<n>` table, and
   which items were applied.
6. **Tests** — baseline → final numbers, lint state, any suite not run and why.
7. **Saved docs** — absolute paths of the plan and the review.
8. **Open questions and follow-ups** — last. Non-blocking plan questions left open,
   assumptions taken without asking, deferred findings, loose ends. For each
   deferred finding, offer `/maintenance-task` to file it. Nothing open → one line
   saying so.
