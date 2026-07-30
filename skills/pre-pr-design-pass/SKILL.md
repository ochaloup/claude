---
name: pre-pr-design-pass
description: Design-level pass over a finished branch, asking whether the same outcome could be reached with less new code by reusing what the base branch already offers. Reads the base version of every touched file rather than the diff alone, treats the branch as a proven PoC, and re-derives the implementation from scratch against the current base — reuse over addition, one mechanism per concept, the base's own idioms. Functionality and readability are fixed constraints; nothing may be relaxed to make the diff smaller. Reports graded proposals, applies them only when invoked with `apply`.
when_to_use: the branch works and is nearly ready for a PR — code written, review addressed — and you want a last design-level look at whether it fits the existing codebase before anyone reads it as a PR
argument-hint: "[--base <ref>] [--criteria <text|file>] [apply]"
---

# Pre-PR Design Pass

Arguments: $ARGUMENTS

The branch works. Treat it as a proof of concept that has already earned its
keep: it proved the requirement can be met, and it fixed the meaning of *done*.
This skill asks the one question that only becomes answerable now that the code
works:

> **If you started this implementation today, against the base branch as it
> stands, knowing everything the branch taught you — how much of this diff would
> you write?**

The answer is not "less code at any cost". The answer is code a reader of the
base branch recognises: it reuses what is already there, it speaks the vocabulary
the base already established, and it introduces a new concept only where the base
genuinely has none.

**"Closer to main" is not the goal either.** Reusing the base's idioms is; moving
the diff back toward the base for its own sake is not an improvement and must
never be argued as one. The test is whether a reader of the base recognises the
code — not whether the diff shrank.

## Read the base, not the diff

The diff shows what changed. Only the base version of each touched file shows
**what the change was competing with**, and that is where the findings are:

```
git show <base>:<path>
```

Do this for every modified file before forming any opinion about it. The base
often achieves a behaviour *implicitly* — through a write-time invariant, a schema
constraint, a default — where the branch achieves it explicitly. From the diff
alone, the branch's explicit version reads as new, required logic; against the
base, it is a replacement for something that was already guaranteed. No hunk shows
that difference.

This rule and the two constraints below are what keep the pass honest. Skipping
the base read is how a pass produces confident, wrong proposals.

## Two constraints that bind harder than the goal

1. **Functionality is fixed.** Every behaviour, edge case, error path, log line,
   metric, migration and test the branch delivers must survive every proposal.
   There is no acceptable relaxation — not a weakened assertion, not a dropped
   edge case, not a test made laxer so a smaller implementation fits. A proposal
   that costs functionality is not a candidate; drop it, do not downgrade it.
2. **Readability is fixed.** Never propose shorter identifiers, statements
   squeezed together, clever one-liners, an obscure operator in place of an
   explicit conditional, or the removal of named intermediate values. If the
   smaller version is harder for a human to read, the branch's version wins and
   there is no finding.

This is a design pass, not a diet. "Could be smaller" is not a finding. "Would
not have been written this way from scratch, and here is the specific existing
thing it should have used instead" is a finding.

## Duplication is not the enemy

**Derivable is not the same as redundant.** Some duplication is the point, and
proposing its removal is a defect of this skill, not of the branch:

- A **derivable field held in a DTO** is wanted — the reader sees the value
  instead of reconstructing it. Derivable *and* explicit is a legitimate design
  choice, as long as drift is impossible: the object is immutable after
  construction, or every mutation path recomputes the field. Verify which one
  holds; do not assume.
- If **neither** holds, that is a real finding — but a correctness one: the
  stored value can disagree with its own derivation. Report it as such, not as a
  DRY violation.
- Two similar-looking blocks that serve two different concepts stay two blocks.
  Only a *shared concept implemented twice* is a finding (see lens 2).

## Shell discipline

One plain command per bash call — no `$(...)` or backticks, no `&&`/`;` chains,
no redirects or heredocs. Those shapes are classified as dangerous before
allowlist matching and stall on a permission prompt. Resolve a computed value
(merge-base, branch name, base ref) in its own call and substitute the literal
result into the next one. This applies to any subagent prompt this skill
constructs.

## 1. Resolve scope and calibrate

Base ref: `--base <ref>` if given; otherwise `main`, then `master`, then the
merge-base with the PR's base branch — same resolution as the `code-review`
skill.

Then three cheap calls, before reading anything:

```
git diff --stat <base>...HEAD
```
```
git diff --stat --diff-filter=A <base>...HEAD
```
```
git log --oneline <base>..HEAD
```

**Split added files from modified ones.** New files are where speculative
structure hides — point lenses 1, 4 and 5 there. Modified files are where drift
hides — point lenses 2, 6 and 7 there. Judging both piles the same way finds
neither.

**Count test lines separately from production lines.** A feature branch can be
mostly tests — 900 of 1600 lines is unremarkable when the area of the base it
touches had one test file. Without that split, a well-tested branch reads as
bloated and the cuts get proposed in the wrong pile. Tests are contract, not
volume.

State the requirement in one line, then compare it to the *production* line count.
**A production diff much larger than its requirement is the primary signal that
lenses 1-3 will pay off** — volume usually means the implementation fought the
existing structure instead of using it. A small, proportionate diff means
calibrate down: run the lenses, but expect the honest answer to be "aligned, merge
as-is".

## 2. Write down the functional contract

"No relaxation" is unenforceable against an unstated contract, so state it first.
Sources, in order of authority:

- **The conversation** — what the user asked for, and every constraint they
  accepted or rejected along the way.
- **The saved work documents** — resolve the literal path once via
  `python3 -c 'import os; print(os.environ.get("SAVE_PLAN_PATH",""))'` and glob
  `<DIR>--<BRANCH>--*.md` (`PLAN`, `IMPLEMENTATION_DETAIL`, `INVESTIGATION`,
  `REVIEW`). Never use `$SAVE_PLAN_PATH` inside a bash command; use `Glob`/`Read`
  with the resolved literal.
- **The ticket** — if the branch or PR title carries `[GEN-<number>]` and Notion
  is reachable, read the task description.
- **`--criteria <text|file>`** — acceptance criteria passed in directly.
- **The branch's own tests** — the executable part of the contract, and the part
  that survives when the prose is vague.

Write it as a **minimum requirement list**: numbered, one line each, no
implementation in them. Then ask of every hunk in the diff — *which requirement is
this?* A hunk that maps to none is a candidate, but be precise about which kind:

- Scaffolding serving no requirement → a cut (lens 5).
- A **good change that answers no requirement of this feature** — an unrelated fix
  or improvement the branch picked up along the way — is **not** a cut. It is a
  candidate for its own PR. Say that, and keep it out of the cut list.

This list is the checklist every proposal is measured against, and the checklist
step 7 re-verifies if anything is applied.

**A reaffirmed item is closed.** Once the user states a behaviour is
non-negotiable, stop looking for a way to design it away and price it honestly
instead: *"the stored exit detail costs ~250 lines and most of it cannot be
designed away"* is the useful answer. A redesign that quietly claws part of it
back is not.

## 3. Learn the base before judging the branch

The dominant failure mode of this skill is a confident "reuse X" where X does not
actually fit, or missing the X that does. Both come from judging the branch
without reading its neighbourhood. So, for the area the branch touches:

- **The base version of every touched file**, per the rule above
  (`git show <base>:<path>`). This is the first read, not the last.
- **The siblings.** Read the files that sit next to each new file the branch adds,
  and the nearest shared/util module. That is where the reusable thing lives if it
  exists.
- **The vocabulary.** For each new symbol the branch introduces, grep the base for
  its concept words — not its exact name. The base's version is rarely named the
  same.
- **Every new config field, flag or enum, traced to its consumers.** Find each read
  site and what the value is actually bound to before forming an opinion. A field
  named like a row filter that turns out to be bound only to a `CASE` expression
  and never to a `WHERE` is a different thing entirely — and that single fact
  decides whether a proposal touching it is safe. Never judge a config field by
  its name.
- **For TypeScript**, check `$HOME/marinade/typescript-common/` when a package
  from it is already a dependency; note it as a candidate if it is not.
- **What the base learned recently.** `git log --oneline <base> -30` over the
  touched directories. A branch written weeks ago against an older base often
  reimplements an abstraction that has since landed — those are the "ideas brought
  to main" the branch should now stand on.

## 4. Design lenses

Run each lens over the diff. Every one is a structural question; none of them is
about naming, formatting, or a line-level edit. A lens that fires nothing gets one
word in the report — that is a result, not a gap.

1. **Reuse before addition.** For every helper, type, error, config reader,
   client, or abstraction the branch adds: does an equivalent already exist on the
   base or in a shared library? This lens has the highest yield and the cheapest
   fix — deleting new code in favour of an import.
2. **One mechanism per concept.** Did the branch solve a problem the base already
   solves, its own way — a second retry loop, a second cache, a second error
   taxonomy, a second way to parse the same config? Two mechanisms for one concept
   is the defect regardless of which one is better. Name which survives. The
   strongest and least visible variant is **one rule written down more than once**:
   the same invariant ("each role has its own authority and its own aggregation")
   restated in four places, the fourth in a different file. Hunk-level review
   cannot see that; only following the concept end to end can.
3. **Extension point bypassed.** Does the base have a trait, interface, registry,
   visitor, or hook that this change was supposed to plug into, which the branch
   worked around with a dedicated code path? Fitting the seam usually deletes most
   of the new code.
4. **Placement and boundary.** Is the new code in the layer it belongs to?
   Something added to a service that belongs in a shared lib (or the reverse),
   business logic in a handler, a helper buried in a leaf file that three modules
   will want next month. Placement mistakes are the most expensive to fix later
   and the cheapest to fix now.
5. **PoC scaffolding.** What exists only because of how the branch was arrived at
   — an abstraction with one call site, configurability nobody asked for, a flag
   with one possible value, an indirection layer with one implementation, handling
   for a state that cannot occur, remnants of an approach abandoned mid-branch.
   From-scratch code would not contain these. One measurable check belongs here:
   **count representable states against realized ones.** Three boolean-ish fields
   represent eight combinations; if only two are ever constructed, the shape is
   over-parameterized. That ratio is evidence, not taste.
6. **Idiom drift.** Where the branch does the same *kind* of thing the base does
   but differently: naming scheme, error handling and propagation, layering, module
   placement, test structure, how config reaches the code. Not a bug — it makes the
   code read as foreign and taxes every future change to it.
7. **Base convergence.** Beyond reuse: has the base moved under this branch? A
   migration, refactor, or renamed API that landed after the branch diverged, which
   the branch either duplicates or will silently undo at merge time.
8. **Cascade from one decision.** For each significant new concept the branch
   introduces, list everything that exists *only* because of it — a type, two
   derived lists, a projection function, a fold in a controller, a hundred lines of
   test. Each item is individually justified by the one before it, which is exactly
   why hunk-level review clears the whole chain. Judge the root decision against
   the full cascade, and price the cascade rather than the leaf.

**Evidence rule.** Every finding must either cite the concrete existing thing to
reuse — `path:line` at the base ref, quoted — or be a pure-deletion proposal with
the specific code to delete. A finding that merely gestures at "consider
extracting a shared abstraction" has no evidence and does not get reported.

**Symmetry rule.** Use the branch's own reasoning against itself, in both
directions. If its design doc traded a compile-time guard for "a registry test
that fails naming the actual mistake", that trade is now available everywhere in
the branch — apply it consistently, and drop any proposal that invokes it only
where convenient.

## 5. Grade each candidate for pre-PR cost

The branch works. Reworking working code has real cost, and hiding that cost
behind a design argument is how this skill turns into churn. Grade every surviving
candidate:

| Grade | Meaning |
|---|---|
| `REWORK` | Do before opening the PR. |
| `WORTH IT` | Clear improvement, safe, but the PR is fine without it. |
| `NOTED` | Recorded for the record; do not act now. |

Grade by the cost of reworking working code, not by elegance. Four inputs, in this
order:

1. **Does it remove a second mechanism for one concept, or a wrong boundary?**
   Those compound — every later change pays for them. This is what earns `REWORK`.
2. **How much new code disappears**, and does anything need to be *written* for it?
   Reuse that is a net deletion is nearly free; reuse that requires generalising an
   existing helper is not.
3. **Regression risk against the contract from step 2**, and whether tests cover
   the affected paths. Rewriting working, untested code for a modest gain is
   `NOTED` — never `REWORK`, however good the design argument.
4. **Reviewer cost of leaving it.** Idiom drift a reviewer will trip over is worth
   more than its line count suggests.

Cap the report at the ~8 highest-value candidates. If more survive, say how many
were dropped and why — silent truncation reads as full coverage.

## 6. Output

Print in this order, and nothing else.

**Verdict line**, one of:

- `ALIGNED — merge as-is.` The honest and frequent outcome. Say it plainly, list
  which lenses fired nothing, and stop. Do not manufacture findings to justify the
  run.
- `MINOR DRIFT — N proposals, none blocking.`
- `SIGNIFICANT REWORK — N proposals, M graded REWORK.`

**Table**, findings in grade order (`REWORK`, `WORTH IT`, `NOTED`):

| ID | Branch does | Base already has | Proposal | Δ | Grade |
|----|-------------|------------------|----------|---|-------|

IDs are `BC<n>`, 1-indexed. `Δ` is the rough net line change (`-140`, `-60 +15`).
Keep every cell to one line; the detail goes below.

**Per finding**, under a `### BC<n> — <one-line summary>` heading:

- Lens it came from, and the branch code it concerns (`path:line`).
- The existing thing to reuse, quoted, with its `path:line` at the base ref — or
  the code to delete outright.
- The smaller path, concretely enough to implement. Show the replacement code when
  it is short.
- **Contract impact**: which contract items from step 2 the proposal touches, and
  why each one still holds afterwards. "None" is a valid and common answer — but
  it must be stated, not omitted.
- **Risk**: what could regress, and whether a test would catch it.

**Considered and kept** — a short list of what the pass examined and deliberately
left alone, one line each with the reason. Naming what stays is worth as much as
naming what goes: it is the evidence the pass was not cutting for its own sake,
and it stops the same ground being re-litigated next round.

**Closing line**: which lenses fired, which returned nothing, and any candidates
dropped by the cap.

No praise, no summary of the branch's merits, no restatement of the table.

### When the user pushes back

- **An objection that lands kills the proposal in one sentence.** Do not re-argue
  it and do not return with a variant of it. A readability objection is the
  constraint deciding, not an opinion to be weighed — and it usually means the
  proposal fused two things that belong apart (a mechanism *and* a shape in one
  enum, say), which is a readability loss on its own terms.
- **Price a reaffirmed requirement instead of re-litigating it** — see step 2.

## 7. Applying — only with `apply`

Without `apply`, the report is the entire deliverable. Never edit code on the
strength of your own design argument alone; the grades are a recommendation for
the user, who owns the merge.

With `apply`, two things happen before any edit:

- **Record the baseline.** Run the full suite and write down the exact starting
  state (`7 suites / 86 tests passing`). Without that number a later failure cannot
  be attributed to a specific finding.
- **Establish the build topology.** Where one workspace package consumes another
  through its build output (`dist`, `target`, a generated client), a stale build
  produces failures that have nothing to do with the source you just changed.
  Rebuild the dependency, then test — every time, not just the first.

Then take only `REWORK` items — never `WORTH IT`, never `NOTED` — and handle them
**one at a time**, in table order:

1. Make the change, and only that change. The rules in `CLAUDE.md` apply in full:
   surgical edits, no improvement of adjacent code, match existing style.
2. Run the project's own verification — `pnpm fix` / `pnpm lint`, or
   `cargo fmt` then `cargo clippy` for a Rust-only project — then the build and the
   tests covering the affected paths, compared against the baseline.
3. Re-check the step 2 contract items that finding listed. If any behaviour moved,
   revert that finding and report it as not applied. **Nothing gets relaxed to make
   an applied change pass** — not a test, not an assertion, not a check.
4. Only then start the next finding.

Stop at the first item that cannot be applied cleanly and report where you got to.
A half-applied design change is worse than the PoC it replaced.

## 8. Persisting

The chat report is normally the whole deliverable — this runs minutes before a PR
is opened. Persist it via the `save-plan` skill (`TYPE = REVIEW`) when the verdict
is `SIGNIFICANT REWORK`, when anything was applied, or when the user asks for a
durable record. `NOTED` items are the main reason to save: they are the ones
nobody will otherwise remember.

## Relation to the other skills

- Run this **after** `code-review` and before `pr-description`. `code-review` asks
  whether each hunk is correct; this asks whether the hunk should exist at all.
- Its findings are design proposals, not defects — keep them out of
  `code-review`'s `P<priority>-R<round>#<seq>` ID space and out of its round
  tally.
- A correctness bug noticed while running the lenses (the drifting DTO field
  above, for instance) is still worth reporting — mark it clearly as a correctness
  finding so it is not weighed as an optional design proposal.
