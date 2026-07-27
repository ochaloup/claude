---
name: code-review
description: Review this branch's changes against a base ref using git diff. Runs lean by default — your own analysis plus a parallel codex review, verified inline. Heavier engines (Claude Code's built-in multi-agent review workflow, the topology-review skill) are opt-in via --deep / --topology / max. Assigns round-scoped IDs, persists the report through the save-plan skill, and ends with a summary table. Use when the user runs /code-review, or when the pr-review-followup skill needs a review scoped to new changes.
when_to_use: reviewing branch/uncommitted work against a base ref; for reviewer feedback on an open PR use pr-review instead
argument-hint: "[--base <ref>] [--deep] [--topology] [max]"
---

# Code Review

Review the changes in this branch against a base ref using git diff.
Defaults to main/master if `--base` is not provided.

Determine the base ref as follows:
- If an argument `--base <ref>` is provided in this prompt, use that ref.
- Otherwise, try `git diff main` first; if that fails or returns nothing, try `git diff master`.

## Engine selection

**Default is lean: your own analysis + codex, verified inline. Nothing else.**
Extra engines cost real money and run only when explicitly asked for.

| Invocation | Engines |
|---|---|
| `/code-review` | your analysis + codex |
| `/code-review --deep` | + built-in multi-agent workflow |
| `/code-review --topology` | + topology-review skill |
| `/code-review max` | all of the above |

Never add an engine the invocation did not ask for. If the diff looks like it
would benefit from one — e.g. it merges processes or turns a `T` into a `Vec<T>` —
say so in one line at the end of the report and let the user re-run with the flag.
Do not escalate on your own initiative.

## Reading policy

Read the diff first. Then read **only** what you need to judge it:

- The enclosing function/module of each hunk, and direct callers of anything whose
  signature or behaviour changed.
- The full file only when the hunk's correctness genuinely depends on distant state
  in that file (invariants, init order, shared mutable state). Not by default.
- For declarative config, sibling files in the same directory and anything the diff
  transitively references.

Do not read every changed file end to end. That habit is what makes this review
expensive, and it rarely changes a verdict.

## Objectives

1. **Logical flaws** — Bugs, incorrect assumptions, edge cases, off-by-one errors,
   race conditions, improper error handling, broken invariants.
2. **Regression risk** — Changes that could break existing behavior. Note whether
   tests cover the affected paths; if not, describe what scenarios need coverage.
3. **Data correctness** — Data corruption risks, SQL query issues (injection, wrong
   joins, missing transactions), race conditions on reads/writes/inserts.
4. **Dead code** — Unreachable code, unused exports/functions/variables. Propose removal.
5. **Code quality** — Violations of DRY, unnecessary complexity, poor naming,
   missed abstractions. Suggest a concrete fix, not just a flag.
6. **Simplification opportunities** — Code that could be meaningfully shortened or
   clarified without changing behavior: unnecessary abstractions, overly defensive
   checks, verbose constructs replaceable by a standard library call, or logic that
   can be collapsed. Provide the simplified version inline. Only flag if it reduces
   lines or cognitive complexity meaningfully — not style preference or renaming.
7. **Code reusability** — Check shared libraries before writing utility logic.
   For TS: use typescript-common (expected location $HOME/marinade/typescript-common/)
   if a package from that is present in package.json; if not, notify that it should
   be considered.
8. **Security awareness** — Avoid exposing secrets or credentials in code, validate
   and sanitize inputs, prefer well-maintained libraries over custom crypto/auth,
   and flag suspicious patterns (SQL injection, unsafe deserialization, overly
   permissive access controls).
9. **Configuration & manifest consistency** — Only when the diff touches K8s/Helm/
   Kustomize/Argo/Terraform/CI config: read `config-review.md` in this skill's
   directory and apply it. Skip entirely otherwise.

Only report problems. No praise, no neutral observations.

## Parallel codex review

Codex runs on a separate quota, so it is the cheapest second opinion available.
Always run it.

1. **Kick it off early.** Right after resolving the base ref and before reading
   files, run it as a background bash call:
   ```
   codex exec review --base <ref>
   ```
   Use `Bash` with `run_in_background=true`. Do NOT redirect output to a file — a
   redirect triggers an interactive permission prompt; the harness captures
   stdout/stderr of the background call.
2. **Do your own review** meanwhile. Do not wait for codex — your analysis is
   independent and primary.
3. **When codex finishes**, read its captured output from the background task result.
4. **Integrate**: valid finding you missed → add it; duplicate of yours → keep
   yours; wrong or noise → drop it.

If `codex` is not installed (`which codex` fails) or the call errors, note the
reason in one line and continue.

## Built-in review engine — only with `--deep` or `max`

Claude Code ships a multi-agent review pipeline registered as a workflow named
`code-review`. It is the single most expensive part of this skill, which is why it
is opt-in.

```
Workflow({ name: "code-review", args: "high <BASE_REF>" })
```

Passing `--deep` is itself the opt-in — do not ask for separate confirmation. It
returns immediately with a task ID and notifies on completion, so continue with
your own analysis meanwhile.

Its findings arrive already verified with a CONFIRMED or PLAUSIBLE verdict — carry
that verdict through instead of re-verifying. Fold them in on the same terms as
codex.

Its correctness angles overlap your Objectives only partially — do not treat its
silence on Objectives 7-9 as a clean bill, since it has no notion of
typescript-common reuse or K8s/IaC cross-file consistency.

If workflows are unavailable or the call errors, note the reason in one line and
continue.

## Topology engine — only with `--topology` or `max`

The engines above are **diff-anchored**: they read hunks and ask whether each hunk
is correct. A whole class of defect is invisible to that — where every hunk *is*
correct and the damage is to a property the old structure guaranteed for free. The
`topology-review` skill asks that different question.

It fans out six finder agents, so it runs only when explicitly requested.

```
Skill({ skill: "topology-review",
        args: "--base <BASE_REF> --embedded --thesis <one-line structural thesis> --criteria <acceptance criteria if known>" })
```

**Supply `--criteria` whenever you can get it** — the linked ticket, the PR body, or
what the user stated in conversation. Without it the acceptance-criteria lens returns
empty. Pass user-stated requirements verbatim.

Its findings arrive already adversarially verified — carry the verdict through, do
not re-verify. Two handling rules specific to this engine:

- A finding anchored to a line the diff did not touch is **expected**, not suspect.
  That is the signature of the class. Do not downgrade it for lacking a hunk.
- It distinguishes pre-existing defects whose blast radius this change multiplied
  from ones the change introduced. Preserve that distinction — it determines who
  owns the fix.

Report `not_verified_due_to_cap` entries rather than dropping them silently.

If the skill is unavailable or errors, note the reason in one line and continue.

## Reporting

- Check if there is an open PR for the current branch using `gh pr view --json url,number` (fall back to `gh pr list --head <branch>`).
- If a PR exists, store its URL and number. You will need these to construct permalink URLs.
- For every finding, include a clickable GitHub permalink to the relevant code (when the branch is pushed to github, otherwise construct nothing). Build the URL as:
  `https://github.com/<owner>/<repo>/blob/<branch>/<file>#L<start>-L<end>`
  If a PR exists, prefer the PR files-changed URL format:
  `<pr_url>/files#diff-<sha256-of-filepath>R<line>`

## Round detection and prior unaddressed findings

Before assembling the report, look up any prior saved review file so this run
can pick up where the last one left off.

1. Resolve `$SAVE_PLAN_PATH` (`python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'`).
2. Scan for prior saved reviews matching this branch/PR — typically
   `*--<branch>--*REVIEW*.md` or `*--<branch>--pr-<N>--REVIEW*.md`.
3. **Round detection:**
   - No matching file → `ROUND = 1`.
   - Matching file → parse findings for the highest `R<n>` ID and set `ROUND = highest + 1`.
4. **Prior re-verification:** for each finding in the most recent matching file,
   re-check against current code. Classify:
   - **ADDRESSED** — gone. Record ID in tally only.
   - **STILL_PRESENT** — carry forward, keep original ID.
   - **UNCERTAIN** — carry forward, keep original ID.

## Verify candidates (3-state ladder)

Pool the candidates from every engine that ran and put the unverified ones through
one verification pass. Candidates from the built-in workflow and the topology
engine are already verified — keep their verdict and skip them here.

1. **Dedup.** Collapse candidates pointing at the same line and the same mechanism,
   keeping the one with the most concrete failure scenario.
2. **Verify each remaining candidate inline, in this context** — re-read the
   relevant code and argue against the candidate. Do not spawn verifier subagents;
   you already have the files in context and a subagent would re-read them from
   cold. Only under `--deep` or `max`, and only when there are more than 8
   unverified candidates, delegate to at most 4 parallel subagents.
   Each candidate returns exactly one of:
   - **CONFIRMED** — the defect is real and the failure scenario holds.
   - **PLAUSIBLE** — not confirmable from the code at hand, but the reasoning stands
     and it warrants a human look.
   - **REFUTED** — the reasoning does not survive contact with the code.
3. **Keep CONFIRMED and PLAUSIBLE. Drop REFUTED** — a refuted candidate reaches
   neither the report, the saved MD, nor the table.

A candidate with no concrete failure scenario is not a finding; drop it rather than
filing it as PLAUSIBLE. Every surviving finding carries its verdict into the report.

Verification decides whether a candidate is real — it does not soften an objective.
Never downgrade a CONFIRMED finding to PLAUSIBLE to avoid reporting it.

## Finding IDs

Assign a unique ID to every current-run finding.

**Format:** `P<priority>-R<ROUND>#<seq>`

- `<priority>` — `1` (high) / `2` (medium) / `3` (low). Map from the severity
  you'd otherwise tag the finding with.
- `<ROUND>` — from the previous section.
- `<seq>` — 1-indexed within the round, unique across all priorities.

Carried-forward prior findings keep their original IDs.

## Output

The output happens in this strict order: **(1) summary in chat, (2)
save full report via the `save-plan` skill, (3) final table as the last step.**

Before producing any output, resolve the current date and time by running
`date '+%Y-%m-%d %H:%M %Z'` as its own bash call. Both the chat summary and
the saved REVIEW chapter must start with a line:
`Reviewed: <YYYY-MM-DD HH:MM TZ>`

### Step 1 — Chat summary

- Write a short prose summary.
- If a PR exists, the summary MUST include the PR URL and clickable GitHub links (show directly in console whole link! with whole hash etc, no simplification via some md formatting) to all findings.
- If no PR exists, use blob permalinks against the branch instead.

### Step 2 — Persist the full report via the `save-plan` skill

Invoke the `save-plan` skill (pass `pr-<N>` as context if a PR exists; no
arg otherwise). Do not write any file directly.

The MD must contain **all detail useful for fixing**:
- File path + line range + clickable GitHub permalink for every finding
- Code snippets / current code
- Concrete suggested fix
- Verdict (`CONFIRMED` / `PLAUSIBLE`) and which engine surfaced it
- For carried-forward findings: original ID, round it came from, re-check notes.

Every finding's body uses its `<ID>` as the heading anchor (e.g. `### P1-R1#1 — ...`).

### Step 3 — Final summary table (last step)

After `save-plan` reports the saved file path, print a single table as the
**last** output. No prose after it.

Include, in this order:
1. Every carried-forward prior finding still unaddressed (STILL_PRESENT /
   UNCERTAIN), in original-ID order across all prior rounds.
2. Every current-run finding in ID order.

Table columns:

| ID | Description | Recommendation |
|----|-------------|----------------|

- **ID** — e.g. `P1-R1#1`.
- **Description** — one-line summary (≤ 150 chars) of what / where.
- **Recommendation** — concise concrete fix (≤ 80 chars). Append ` (PLAUSIBLE)` for
  findings that verified as PLAUSIBLE rather than CONFIRMED. For carried-forward
  items append ` (STILL_PRESENT from Rn)` or ` (UNCERTAIN from Rn)`.

Above the table print the absolute saved-file path from step 2 on its own line.

### REVIEW content structure

The chapter body is ordered as:

1. **Compound review** (first, primary) — your verified findings with the findings
   of whichever other engines ran folded in. Each finding uses its `<ID>` and
   carries its verdict. Note the engine that earned it (e.g. `codex`,
   `topology/fan-out`).
2. **Carried-forward prior findings** (if any) — STILL_PRESENT / UNCERTAIN entries
   from prior rounds, original IDs preserved.
3. **Raw codex review** — the verbatim captured output of the `codex exec review`
   call, unedited, so the reader can audit independently.

Do **not** paste the built-in workflow's or the topology engine's raw output into
the report — they are long and re-inflate context for little value. Instead, for
each engine that ran, record one line: how many candidates it produced, how many
survived, and for topology its thesis, which lenses fired, and any
`not_verified_due_to_cap` entries. The thesis in particular must appear — every
topology finding is conditional on it.

End with one line naming which engines actually ran and how many findings each
contributed. A review that silently lost an engine must not read as a full-fanout
review. An engine that ran but returned nothing usable is **not** the same as an
engine that ran clean; state which happened. If a heavier engine was not requested,
say so plainly (e.g. `built-in engine: not run (no --deep)`).
