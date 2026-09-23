---
name: code-review
description: Review this branch's changes against a base ref using git diff. Runs lean by default — your own analysis plus a parallel codex review, verified inline. A parallel agent describes the change, its design impact (design-impact skill) and an ASCII diagram (show-me skill). Heavier engines (an inline multi-agent review workflow, the topology-review skill) are opt-in via --deep / --topology / max. Assigns round-scoped IDs, persists the report through the save-plan skill, and ends with a summary table. Use when the user runs /code-review, or when the pr-review-followup skill needs a review scoped to new changes.
when_to_use: reviewing branch/uncommitted work against a base ref; for reviewer feedback on an open PR use pr-review instead
argument-hint: "[--base <ref>] [--deep] [--topology] [max]"
---

# Code Review

Review the changes in this branch against a base ref using git diff.
Defaults to main/master if `--base` is not provided.

Determine the base ref as follows:
- If an argument `--base <ref>` is provided in this prompt, use that ref.
- Otherwise, try `git diff main` first; if that fails or returns nothing, try `git diff master`.

## Shell discipline

Every bash call this skill makes — and every one its subagents make — is a single
plain command: no `$(...)` or backticks, no `&&`/`;` chains, no redirects or
heredocs. Those shapes are classified as dangerous before allowlist matching and
stall the review on a permission prompt. When a command needs a computed value
(merge-base, branch name, PR number), resolve it in its own call and substitute the
literal result into the next one.

## Engine selection

**Default is lean: your own analysis + codex, verified inline. Nothing else.**
Extra engines cost real money and run only when explicitly asked for.

| Invocation | Engines |
|---|---|
| `/code-review` | your analysis + codex |
| `/code-review --deep` | + inline multi-agent review workflow |
| `/code-review --topology` | + topology-review skill |
| `/code-review max` | all of the above |

Never add an engine the invocation did not ask for. If the diff looks like it
would benefit from one — e.g. it merges processes or turns a `T` into a `Vec<T>` —
say so in one line at the end of the report and let the user re-run with the flag.
Do not escalate on your own initiative.

## When lean is not enough

Right after resolving the base ref, run `git diff --stat <ref>` and count the
changed files. Over ~10 changed files, or when one edit is repeated across many
call sites, a single-pass lean review does not cover the diff — one reader catches
the first instance of a repeated defect and misses the third.

Do not silently narrow the scope, and do not escalate on your own. Review the whole
diff as best you can and make the shortfall the **first line** of the chat summary:

`Lean coverage is insufficient for this diff (<N> files) — re-run with --deep.`

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

## Targeted checks

The objectives say what to look for; these say how to find it without re-reading the
repo. Each one is a grep over the diff's own symbols, not a file read — run it, then
judge the hits. This list is what keeps the lean path from being a shallow path.

- **Every caller of a changed signature.** For any function, method or type whose
  signature, return shape, nullability or error behaviour changed, grep its name
  repo-wide and check each call site. Never assume the diff updated them all.
- **Early returns and error paths.** A `return`/`throw`/`?`/`catch` added to or
  removed from a touched function — establish what now skips the code below it.
- **Missing `await`.** Grep the diff for async calls without `await`, and for
  `.map(async` / `forEach(async` with no awaited `Promise.all`.
- **Resource lifecycle.** Connections, locks, streams, subscriptions and intervals
  created in the diff: opened once, or once per call? Released on every path,
  including the error path?
- **Money arithmetic.** Token amounts, rates and balances on JS `number` rather than
  `Decimal`/`bigint`; float equality; rounding direction on a value that leaves the
  process.
- **Test coverage of changed branches.** For each new conditional branch, grep the
  test files for the symbol. Name the uncovered scenario — do not just note absence.
- **Reuse before new utility code.** For every new helper in the diff, grep for an
  existing equivalent (and typescript-common for TS) before accepting it.

## Change description — always, in parallel

The report says what is wrong with the diff. The reader also needs to know what the
diff *does*. A subagent writes that while you review, so it costs no serial time.

The same agent also runs the `design-impact` and `show-me` skills, which sit next to
this skill's directory. Resolve their absolute `SKILL.md` paths and substitute them.

Kick it off right after resolving the base ref, alongside the codex call:

```
Agent({ subagent_type: "Explore",
        description: "Describe branch changes",
        prompt: "Run `git diff --stat <BASE_REF>`, then `git diff <BASE_REF>`. Say what
                 the change does, in plain english. Return one lead sentence, then 3-6
                 bullets. One bullet per change. Start each bullet with the file or
                 area it touches. Say the intent, not the mechanics. Short sentences.
                 No findings, no verdicts, no praise. Under 120 words total.
                 Then read <DESIGN_IMPACT_SKILL_MD> and follow it with
                 `--base <BASE_REF> --embedded`. Then read <SHOW_ME_SKILL_MD> and follow
                 it with `--base <BASE_REF> --embedded`, drawing what the design-impact
                 block names. Return three parts in order: description, design-impact
                 block, diagram block. Every bash call is one plain command." })
```

This is the shape it must come back in:

```
Withdrawals now settle through one code path instead of two.

- `src/vault.rs` — the two withdraw branches merged into `settle()`.
- `src/fees.rs` — fee is taken once, in `settle()`, not per branch.
- `tests/withdraw.rs` — new test for a withdrawal that hits the fee cap.
```

If a bullet needs a second sentence to be understood, keep it — readable beats short.
The 120-word cap covers the description only, not the other two parts.
If the agent is unavailable or errors, write all three parts yourself from the diff
you already read, following the two skills. They are never skipped, and never retried
with a second agent.

## Parallel codex review

Codex runs on a separate quota, so it is the cheapest second opinion available.
Always run it.

1. **Kick it off early.** Right after resolving the base ref and before reading
   files, run it as a background bash call:
   ```
   codex exec review --base <ref>
   ```
   Use `Bash` with `run_in_background=true`; the harness captures stdout/stderr of
   the background call, so no redirect is needed.
2. **Do your own review** meanwhile. Do not wait for codex — your analysis is
   independent and primary.
3. **When codex finishes**, read its captured output from the background task result.
4. **Integrate**: valid finding you missed → add it; duplicate of yours → keep
   yours; wrong or noise → drop it.

If `codex` is not installed (`which codex` fails) or the call errors, note the
reason in one line and continue.

## Deep review engine — only with `--deep` or `max`

The heavy engine is a workflow this skill carries itself. **Claude Code ships no
workflow named `code-review`** — `Workflow({name: "code-review"})` fails with
`not found`. Pass the script below inline via `script`, so the engine travels with
the skill and cannot be silently absent.

```
Workflow({
  args: { base: "<BASE_REF>", level: "<LEVEL>" },
  script: "<the script below, verbatim>"
})
```

`LEVEL` is `high` for `--deep` and `xhigh` for `max`. It sets each agent's
reasoning effort and how many skeptics rule on each candidate — one for `--deep`,
three with a majority rule for `max`. Never run it below `high`: `--deep` is the
pre-merge verification pass, and a discounted run of the expensive engine is the
worst of both — you pay for it and still do not know what it missed.

Cost: 7 finders plus one verifier per surviving candidate, capped at 7 candidates.
So at most 14 agents under `--deep`, 28 under `max`.

```js
export const meta = {
  name: 'code-review-deep',
  description: 'Fan out review dimensions over a diff, then adversarially verify each finding',
  phases: [
    { title: 'Review', detail: 'one finder per review dimension' },
    { title: 'Verify', detail: 'skeptics try to refute each pooled candidate' },
  ],
}

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          summary: { type: 'string' },
          failure_scenario: { type: 'string' },
          suggested_fix: { type: 'string' },
          priority: { type: 'number' },
        },
        required: ['file', 'summary', 'failure_scenario', 'priority'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['CONFIRMED', 'PLAUSIBLE', 'REFUTED'] },
    evidence: { type: 'string' },
  },
  required: ['verdict', 'evidence'],
}

const DIMENSIONS = [
  { key: 'correctness', brief: 'Logical flaws, wrong assumptions, edge cases, off-by-one, race conditions, improper error handling, broken invariants. Trace every early return, throw and `?` the diff adds to or removes from a touched function, and establish what now skips the code below it.' },
  { key: 'regression', brief: 'Behaviour existing callers rely on that this diff changes. Grep repo-wide for every call site of anything whose signature, return shape, nullability or error behaviour changed — never assume the diff updated them all. For each new conditional branch, grep the test files for the symbol and name the uncovered scenario.' },
  { key: 'data', brief: 'Data corruption, SQL injection, wrong joins, missing transactions, races on read/write/insert. Token amounts, rates and balances on floating point instead of Decimal/bigint; float equality; rounding direction on a value that leaves the process.' },
  { key: 'lifecycle', brief: 'Async calls with no await, including `.map(async` and `forEach(async` with no awaited Promise.all. Connections, locks, streams, subscriptions and intervals created in the diff: opened once or once per call, and released on every path including the error path.' },
  { key: 'quality', brief: 'Dead or unreachable code, unused exports, DRY violations, unnecessary complexity, overly defensive checks, verbose constructs a standard-library call replaces. Give the simplified version inline. Report only what meaningfully cuts lines or cognitive load — never style preference or renaming.' },
  { key: 'reuse', brief: 'New helper code that duplicates something the repository already provides. Grep for an existing equivalent behind every new helper in the diff. For TypeScript, also judge whether the shared typescript-common package should own it instead.' },
  { key: 'security', brief: 'Secrets or credentials in code, unvalidated or unsanitized input, hand-rolled crypto or auth where a maintained library exists, unsafe deserialization, overly permissive access control.' },
]

const base = args.base
const effort = args.level === 'xhigh' ? 'xhigh' : 'high'
const skeptics = args.level === 'xhigh' ? 3 : 1
const CAP = 7

const rounds = await parallel(DIMENSIONS.map(d => () => agent(
  `Review the changes of \`git diff ${base}\` in this repository. Your dimension, and nothing else: ${d.brief}\n\n` +
  `Read the diff first. Then read only the enclosing function or module of each hunk, plus the direct callers of anything whose signature or behaviour changed. Read a whole file only when a hunk's correctness genuinely depends on distant state in it. Do not read every changed file end to end.\n\n` +
  `Report only defects — no praise, no neutral observations. Every finding needs a concrete failure scenario: the specific inputs or state, and the wrong output, crash or corruption they produce. Omit anything you cannot give such a scenario for. priority: 1 high, 2 medium, 3 low.`,
  { label: `find:${d.key}`, phase: 'Review', schema: FINDINGS, effort }
)))

// Barrier is deliberate: dimensions overlap, so candidates must be deduped across all
// of them before anything expensive runs, and an empty pool skips verification entirely.
const byKey = new Map()
rounds.forEach((round, index) => {
  if (!round) return
  round.findings.forEach(f => {
    const key = `${f.file}:${f.line || 0}`
    const kept = byKey.get(key)
    // The dimension rating a shared line highest wins the slot, so arrival order never caps out a P1.
    if (kept && kept.priority <= f.priority) return
    byKey.set(key, { ...f, dimension: DIMENSIONS[index].key })
  })
})
const pooled = [...byKey.values()]

if (!pooled.length) {
  log('no candidates from any dimension — nothing to verify')
  return { findings: [], not_verified_due_to_cap: [] }
}

pooled.sort((a, b) => a.priority - b.priority)
const queue = pooled.slice(0, CAP)
if (pooled.length > queue.length) {
  log(`verifying ${queue.length} of ${pooled.length} candidates (cap ${CAP}); ${pooled.length - queue.length} not verified due to cap`)
}

const ruled = await parallel(queue.map(f => () =>
  parallel(Array.from({ length: skeptics }, (_, i) => () => agent(
    `Argue against this review finding, then rule on it.\n\n` +
    `File: ${f.file}${f.line ? ':' + f.line : ''}\n` +
    `Claim: ${f.summary}\n` +
    `Alleged failure: ${f.failure_scenario}\n\n` +
    `Read the code at current HEAD, locating it by symbol rather than by the line above. Hunt for what kills the claim: an upstream validation, a schema constraint, a type, a caller-side invariant that makes the scenario impossible — that is the commonest refutation. Then check that some caller can actually reach the failing input.\n\n` +
    `REFUTED if the reasoning does not survive contact with the code. CONFIRMED if the defect is real and the scenario holds. PLAUSIBLE only when the reasoning stands but the code at hand cannot settle it. Default to REFUTED when uncertain.`,
    { label: `verify:${f.dimension}#${i + 1}`, phase: 'Verify', schema: VERDICT, effort }
  ))).then(votes => {
    const cast = votes.filter(Boolean)
    if (!cast.length) return null
    const refuted = cast.filter(v => v.verdict === 'REFUTED').length
    if (refuted * 2 > cast.length) return null
    const confirmed = cast.filter(v => v.verdict === 'CONFIRMED').length
    return {
      ...f,
      verdict: confirmed * 2 > cast.length ? 'CONFIRMED' : 'PLAUSIBLE',
      evidence: cast.map(v => v.evidence).join(' | '),
    }
  })
))

const survivors = ruled.filter(Boolean)
log(`${survivors.length} of ${queue.length} candidates survived the adversarial pass`)
return { findings: survivors, not_verified_due_to_cap: pooled.slice(CAP) }
```

Passing `--deep` is itself the opt-in — do not ask for separate confirmation. The
call returns immediately with a run ID and notifies on completion, so continue with
your own analysis meanwhile.

It returns `{findings, not_verified_due_to_cap}`. Every entry in `findings` already
carries a `CONFIRMED` or `PLAUSIBLE` verdict from the adversarial pass — carry that
verdict through instead of re-verifying, and fold them in on the same terms as
codex. Candidates its skeptics refuted never come back; that is what you paid for.
Report `not_verified_due_to_cap` entries rather than dropping them silently.

Its dimensions cover Objectives 1-8. **Objective 9 is not among them** — when the
diff touches K8s/Helm/Kustomize/Argo/Terraform/CI config, append an eighth
dimension built from `config-review.md` instead of assuming the engine looked.

**If the `Workflow` tool is unavailable in this session, or the call errors, the
review the user asked for did not happen.** Do not bury it. Say so as the first line
of the chat summary, in these words:

`--deep requested but the deep engine did not run (<reason>) — this is a lean
review only.`

Then continue with the lean review. A degraded run must never read as a deep one.

**Iterating without resending the script.** Every invocation persists its script
under the session directory and returns the path. To adjust a dimension mid-round,
edit that file and re-invoke with `{scriptPath: "<path>", resumeFromRunId: "<runId>"}`
— unchanged `agent()` calls return cached results instantly and only the edited
stage onward re-runs.

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

If the skill is unavailable or errors, report it the same way as a failed deep
engine: first line of the chat summary, naming the reason, stating that the
requested engine did not run.

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

**Delegate the scan and the extraction to the `locator` agent** — saved REVIEW
files reach 200KB+ and only the finding index is needed here. Give it this task:

> List the files in <resolved path> matching <glob>, newest by mtime first. From
> the newest one only, return verbatim, for every `#### P<pri>-R<round>#<seq>`
> heading: the heading line, the section heading above it, the `file:line`
> reference, and the `Fix plan:` line. Never truncate a fix plan. Omit every other
> line. Also list the distinct `R<n>` values you saw. Lead with the ledger line.

Check the ledger before going on: headings found must equal headings returned.
Take `ROUND` from the highest `R<n>` it reports, plus one. Read the file inline
instead if the agent is unavailable or the ledger fails.
3. **Round detection:**
   - No matching file → `ROUND = 1`.
   - Matching file → parse findings for the highest `R<n>` ID and set `ROUND = highest + 1`.
4. **Prior re-verification:** use only the most recent matching file — it already
   carries forward everything still unaddressed from earlier rounds, so older files
   add context without adding findings. For each finding the agent returned from it,
   re-check against current code. Classify:
   - **ADDRESSED** — gone. Record ID in tally only.
   - **STILL_PRESENT** — carry forward, keep original ID.
   - **UNCERTAIN** — carry forward, keep original ID.

## Verify candidates (3-state ladder)

Pool the candidates from every engine that ran and put the unverified ones through
one verification pass. Candidates from the deep engine and the topology engine are
already verified — keep their verdict and skip them here.

1. **Dedup.** Collapse candidates pointing at the same line and the same mechanism,
   keeping the one with the most concrete failure scenario.
2. **Verify each remaining candidate inline, in this context** — re-read the
   relevant code and argue against the candidate. Do not spawn verifier subagents;
   you already have the files in context and a subagent would re-read them from
   cold. **The default path spawns no subagent except the change-description one.**
   Only under `--deep` or
   `max`, and only when there are more than 8 unverified candidates, delegate to at
   most 4 parallel subagents.
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
save full report via the `save-plan` skill, (3) change description, then the final
table as the last step.**

Before producing any output, resolve the current date and time by running
`date '+%Y-%m-%d %H:%M %Z'` as its own bash call. Both the chat summary and
the saved REVIEW chapter must start with a line:
`Reviewed: <YYYY-MM-DD HH:MM TZ>`

### Step 1 — Chat summary

**Coverage banner first.** If any of these apply, they lead the summary, above the
prose, in this order — a requested engine that did not run, then a lean run that did
not cover the diff. Never demote one into a closing footnote; they change how much
the findings below are worth.

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

### Step 3 — Change description, then the final summary table (last step)

After `save-plan` reports the saved file path, print, in this order and nothing else:

1. The change description from the parallel agent, under a `**Changes under review**`
   heading — lead sentence plus its bullets, as shown in the section above. Trim any
   preamble the agent added.
2. The agent's design-impact block, verbatim.
3. The agent's diagram block, or its `Diagram: none` line, verbatim.
4. The absolute saved-file path from step 2, on its own line.
5. The table, as the **last** output. No prose after it.

The table rows, in this order:
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

### REVIEW content structure

The chapter body is ordered as:

0. **Changes under review** — the agent's three parts: description, design-impact
   block, diagram.
1. **Compound review** (first, primary) — your verified findings with the findings
   of whichever other engines ran folded in. Each finding uses its `<ID>` and
   carries its verdict. Note the engine that earned it (e.g. `codex`,
   `topology/fan-out`).
2. **Carried-forward prior findings** (if any) — STILL_PRESENT / UNCERTAIN entries
   from prior rounds, original IDs preserved.
3. **Raw codex review** — codex's findings verbatim, so the reader can audit
   independently. Drop only its reasoning preamble and progress chatter; never edit,
   merge or summarise a finding itself.

Do **not** paste the deep engine's or the topology engine's raw output into
the report — they are long and re-inflate context for little value. Instead, for
each engine that ran, record one line: how many candidates it produced, how many
survived, and for topology its thesis, which lenses fired, and any
`not_verified_due_to_cap` entries. The thesis in particular must appear — every
topology finding is conditional on it.

### Topology self-check (one line, always)

When the topology engine did not run, spend no agents and no file reads — just check
the diff you have already read against its triggers: one→many or many→one
(processes, queues, pods, databases, schedules; scalar ↔ collection); a new
discriminator on shared storage; a type gaining a collection variant; a per-instance
constructor now called per something else.

If a trigger fires, end the report with one line naming it:
`Topology trigger: <what> — re-run with --topology to cover it.`
If none fires, say `Topology triggers: none` and leave it there. Do not run the
engine on your own initiative either way.

End with one line naming which engines actually ran and how many findings each
contributed. A review that silently lost an engine must not read as a full-fanout
review. An engine that ran but returned nothing usable is **not** the same as an
engine that ran clean; state which happened. If a heavier engine was not requested,
say so plainly (e.g. `deep engine: not run (no --deep)`).
