---
name: fix-review-findings
description: Fix findings that a review already produced in this conversation. Reads the selector the user gives (all, P1#3, "the last one"), re-verifies each selected finding against current code before touching anything, plans the fixes, applies them one at a time with the project's own checks, and ends with a three-column table — finding, resolution, notes. Refuted and already-fixed findings are reported, never edited around. Never posts to GitHub, never commits.
when_to_use: a review round exists in the conversation (code-review, pr-review, pr-review-followup, topology-review, security-review, a saved REVIEW doc) and the user picked which findings to fix. This skill fixes; it does not review. To produce findings use code-review or pr-review; to reply on PR threads afterwards use answer-existing-review.
argument-hint: "[all | <ID selectors> | ordinals | descriptions]"
---

# Fix Review Findings

Arguments: $ARGUMENTS

The findings already exist. This skill does three things to them: verify, fix,
report. It does not review, does not hunt for new findings, and does not widen
the set the user selected.

The verification step is the point of the skill. A review report is a snapshot.
By the time a fix is asked for, the code may have moved, the finding may be
wrong, or it may already be fixed. Editing on the strength of the report alone
is how a review round produces dead defensive code.

## Shell discipline

One plain command per bash call. No `$(...)` or backticks, no `&&` / `;` chains,
no redirects, no heredocs. Those shapes stall on a permission prompt. Resolve a
computed value (branch name, merge-base, an env path) in its own call, then
substitute the literal result into the next one.

Never use `$SAVE_PLAN_PATH` or any shell variable inside a bash command. Resolve
it once:

```
python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'
```

Then use the literal path with `Glob` / `Read`.

## 0. Preconditions

Refuse to run and name what is missing if either fails:

- **A findings set** — in this conversation, or in a saved REVIEW doc for this
  branch. If there is none, say so. Do not review the code to manufacture one.
- **A selector** — see step 2. With no argument, print the working list and ask
  which findings to fix. Never default to `all`.

Local git state is irrelevant. Do not check whether work is committed or pushed.
Do not commit unless asked. Never push.

## 1. Locate the findings

In order of authority:

1. **The latest review round in this conversation** — `code-review`, `pr-review`,
   `pr-review-followup`, `topology-review`, `security-review`, `ReportFindings`
   output, raw codex output, or `pre-pr-design-pass` proposals.
2. **Findings the user typed or pasted** in chat.
3. **The saved REVIEW doc for this branch** — glob `<DIR>--<BRANCH>--*REVIEW*.md`
   under the resolved `$SAVE_PLAN_PATH`. Use this when the conversation has no
   findings, or when it has only the summary table and the fixing detail is in
   the file.

If several rounds are in context, the latest round is the default namespace.
Carried-forward findings keep their original IDs.

Build a working list before reading any code — one row per finding:

```
<ID> | P<n> | <one-line> | <file>:<line> | <engine> | <review verdict>
```

## 2. Resolve the selector

| Selector | Means |
|---|---|
| `all`, `all findings` | every finding in the latest report's table, carried-forward included |
| `all P1`, `P1` | every priority-1 finding in that table |
| `P1#3`, `P1-R1#3`, `#3`, `3` | one finding — loose forms match the canonical `P<pri>-R<n>#<seq>`, latest round assumed |
| `P1#1-3` | that range within that priority |
| `the last one`, `the first two` | positions in the last printed table, in its row order |
| `the missing await one` | matched by content against the one-line descriptions |
| `all except P3#2`, `all but the last` | the set minus the exclusion |
| `P1#3 and the last one` | union of `,` / `and`-joined selectors, deduplicated |

Rules:

- **Echo the resolved set before any work**: `Selected: P1-R1#1, P1-R1#3, P2-R1#5 (3 of 8)`.
- A selector matching **nothing** stops the skill. Ask; never silently drop it.
- A selector matching **more than one** candidate stops the skill. Ask which.
- Ordinals resolve against the **last table the user saw**, in its row order —
  not against your internal ordering.
- **Never widen.** `all` means all findings in that table. It does not mean
  re-reviewing for new ones.
- **Never add a finding of your own.** Something you notice while fixing goes in
  loose ends at step 6, not into the fix set.
- Design proposals from `pre-pr-design-pass` (`BC<n>`) keep that skill's grade
  rule: `all` takes `REWORK` only. `WORTH IT` and `NOTED` need naming explicitly.

## 3. Verify each selected finding

Do this before the first edit, for every selected finding. Read the code at
current HEAD, not the diff.

Checks — run the ones that apply:

- **Locate by symbol, not by line.** Report line numbers drift.
- **Already fixed?** Read the current code. Check `git log -3 --oneline` on the
  file if the report is from an earlier round.
- **Reachability.** Grep every call site of the function, method or type. Show
  that some caller can produce the failing input. A failure scenario nobody can
  reach is not a defect.
- **Upstream guards.** A validation, a schema constraint, a type, a caller-side
  invariant that makes the scenario impossible. This is the most common
  refutation — look for it before agreeing with the report.
- **"Missing X" findings** (await, error handling, cleanup, transaction, bound
  check): grep the surrounding paths for X. The handling often lives one level
  up.
- **Signature or behaviour changes**: check every call site repo-wide, not only
  the ones in the diff.
- **Config and manifests**: read the sibling files in the directory and whatever
  the change transitively references.
- **Test-coverage findings**: grep the test files for the symbol before agreeing
  the path is uncovered.
- **The report's suggested fix.** A real finding can carry a wrong fix. Verify
  the proposed change separately from the defect.

Assign one verdict per finding:

| Verdict | Meaning | Action |
|---|---|---|
| `CONFIRMED` | real, and the failure scenario holds | fix |
| `PLAUSIBLE` | not confirmable from the code, reasoning stands | fix only if the fix is small and cannot regress; otherwise report and ask |
| `ALREADY_FIXED` | not present in current code | no edit; report with the evidence |
| `REFUTED` | the reasoning does not survive the code | no edit; report with the evidence that kills it |

Hard rules:

- **Never fix a REFUTED finding "to be safe."** A guard against an impossible
  state is dead code, and dead code is what the next review reports.
- **Never downgrade a CONFIRMED finding** to avoid the work.
- A finding whose fix needs a refactor, a schema change, or a design decision:
  stop on that one, ask, and continue with the rest.

Verify **inline**, in this context — the report and most of the files are
already here, and a subagent would read them from cold. Only when more than 8
findings are selected, delegate to at most 4 parallel verifiers.

Print one verdict line per finding before planning.

## 4. Plan

Short and numbered. One line per finding, each with its verification check:

```
1. P1-R1#3 — await the flush in closeWriter (src/writer.ts) → verify: writer tests pass
2. P2-R1#5 — drop the unreachable branch (src/parse.ts)     → verify: lint + parse tests
```

Group by file. State ordering where it matters: two findings in one function,
the structural one goes first. Name collisions explicitly — two findings whose
fixes contradict each other are a decision for the user, not a merge for you.

Then, before the first edit:

- **Record the baseline.** Run the test suite and write down the exact numbers
  (`7 suites / 86 tests passing`). Without that number a later failure cannot be
  attributed to a specific fix.
- **Establish the build topology.** Where one workspace package consumes another
  through its build output (`dist`, `target`, a generated client), rebuild the
  dependency before testing — every time, not only the first.

Print the plan, then implement. There is no approval gate; the user asked for
the fixes.

## 5. Implement

One finding at a time, in plan order.

1. Make **only** that change. `CLAUDE.md` applies in full: surgical edits, no
   improvement of adjacent code, match the existing style, zero comments by
   default.
2. **Least complexity wins.** The smaller, clearer fix beats the thorough,
   complex one.
3. Run the project's own checks as separate bash calls — `pnpm fix` (or
   `pnpm lint`), or `cargo fmt` then `cargo clippy`. Fix every lint error the
   run reports, not only the ones in your lines.
4. Run the tests covering the affected path. Compare against the baseline.
5. **Never relax a test, an assertion, or a check to make a fix pass.** If a fix
   genuinely requires an expectation to change, prove the new expectation is the
   correct one first, and say so in the notes column. Weakening a check to reach
   green is a regression wearing a fix's clothes.
6. Re-read the comments around the changed code. Update any that no longer match
   the new behaviour; delete any that now only restate it.
7. Only then start the next finding.

Stop at the first finding that cannot be applied cleanly, and report where you
got to. A half-applied set is worse than an unstarted one.

## 6. Report

The table is the last output. Exactly three columns:

| Finding | Resolution | Notes / next steps |
|---------|------------|--------------------|

- **Finding** — the ID the report used, plus a label of ≤ 60 chars.
- **Resolution** — one of `Fixed`, `Fixed (partial)`, `Already fixed`,
  `Refuted`, `Deferred`, `Blocked` — plus the file(s) touched.
- **Notes / next steps** — ≤ 120 chars, the one thing the reader needs: the
  evidence for a refutation, what is left for a partial, the follow-up for a
  deferral. `—` when there is nothing.

One line above the table: baseline versus final state
(`Tests: 86 → 88 passing; lint clean`). If a check could not be run, say which
and why — a skipped suite must never read as a green one.

Below the table, only loose ends, as a short list: findings you noticed but were
not asked to fix, follow-ups, decisions the user owes. No prose re-summary of the
fixes; the table already said it.

Do not commit. Do not push. Do not mention pushing.

If the findings came from an open PR, close with exactly one line:

`Dispositions are in context — run /answer-existing-review to reply on the threads.`

Nothing goes to GitHub from this skill.

## 7. Persist — only when there is something to remember

Save a fix-round record through the `save-plan` skill (context `fix-round`) when
either holds:

- Any finding ended `Refuted`, `Deferred`, `Blocked`, or `Already fixed`.
- More than 5 findings were touched.

Otherwise the chat table is the whole deliverable. Never write the file
directly.

The saved chapter carries, per finding: ID, verdict, what changed with
`path:line`, the evidence behind a refutation, and what is still open.

## Failure modes worth knowing

- **Stale line numbers.** The report's line is from an older tree. Find the code
  by symbol; a blind edit at the cited line hits the wrong statement.
- **A real finding with a wrong suggested fix.** Verify the fix separately.
- **Two findings on one line.** Fix once, report both rows.
- **Refuted, fixed anyway.** The commonest damage this skill can do. A guard for
  an unreachable state is dead code.
- **Scope creep.** A defect you spotted while fixing belongs in loose ends. Not
  in the diff.
- **Green by expectation change.** A suite that goes green because a test's
  expectation moved is not evidence. Check whether that change is the fix or the
  cover-up.
- **Design proposals judged as defects.** A `BC<n>` item has no failure scenario.
  Verification asks whether the reuse target actually fits, not whether something
  breaks.
