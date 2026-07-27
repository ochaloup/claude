---
name: topology-review
description: Invariant-class review for changes that alter topology, multiplicity, or scope — one process becoming many, many becoming one, a new discriminator on shared storage, a type gaining a collection variant. Finds defects where every hunk is locally correct but a property previously guaranteed by the structure is silently gone. Use when the user runs /topology-review, and as the fourth engine chained from the code-review skill.
when_to_use: a diff consolidates/splits processes, queues or databases, adds a scope key to shared storage, or changes a type to its collection variant — defects diff-reading cannot see; for ordinary hunk-level review use code-review
argument-hint: "[--base <ref>] [--thesis <text>] [--criteria <text|file>] [--embedded]"
---

# Topology Review

Diff-anchored review asks *"is this hunk correct?"*. This skill asks a different
question: **"what did the old structure guarantee that the new structure no longer
does?"**

Every finding this skill targets has the same shape — **the changed code is locally
correct, and the defect is in what merging, multiplying, or re-scoping the context
did to a property that used to hold structurally.** Line-by-line review cannot see
these, which is why they survive codex, the built-in engine, and a careful manual
pass alike.

Worked examples this skill exists to catch (all three survived a three-engine review
of marinade-finance/native-staking#153):

- A consumer loop **unchanged by the diff** becomes a head-of-line blocker once N
  pods on N vhosts collapse into one process on one queue.
- `IntCounter` → `IntCounterVec` keeps every call site compiling and every label
  arity correct, but silently changes `reset()` from "zero one counter" to
  "delete all label series".
- A per-instance constructor that was right when called once opens 2×N connections
  when called per authority.

## Inputs

- `--base <ref>` — base ref for the diff. If absent, resolve like the code-review
  skill: try `main`, then `master`, then the merge-base with the PR's base branch.
- `--thesis <text>` — the structural change in one line, e.g.
  `"N processes → 1 process; N databases → 1 merged DB; N queues → 1 queue"`.
  If absent, derive it (see **Deriving the thesis**).
- `--criteria <text|file>` — acceptance criteria / ticket requirements. Optional but
  **the highest-value input**: it is what turns "this is now serialized" into "this
  violates the no-regression-in-unstake criterion". If a ticket ID appears in the
  branch, PR title, or PR body, try to fetch it before falling back to none.
- `--embedded` — return candidates to the calling skill instead of writing a report
  (see **Output**).

## Deriving the thesis

When `--thesis` is absent, spend one cheap inline pass before any fan-out. Read the
diffstat, the PR body, and any config schema change, then write the thesis yourself.
State it explicitly in the output — a wrong thesis produces confidently wrong
findings, so it must be visible and challengeable.

## Gate — when NOT to run

This engine is worth its cost only when the diff actually changes structure. Skip it
(and say so in one line) unless at least one trigger fires:

1. **One → many, or many → one.** A config field, CLI arg, or type moves between
   scalar and collection. Processes, pods, queues, vhosts, databases, or schedules
   are merged or split.
2. **New discriminator on shared storage.** A column, key prefix, label, or tenant ID
   is added so one store can hold what used to live in separate stores.
3. **Type gains a collection variant.** `T` → `Vec<T>` / `Map<K,T>` / `TVec` —
   especially metrics (`Counter`→`CounterVec`), caches, pools, registries.
4. **Shared resource introduced or removed.** Connection pool, rate limiter, prefetch
   budget, lock, cache, thread pool, or global counter now spans what were separate
   domains.
5. **Base-branch drift.** The branch is behind its base *and* both modified the same
   files. This one is cheap and worth checking even alone.

Triggers 1–4 justify the full fan-out. Trigger 5 alone → run only the drift lens.

## Engine

Invoke the workflow below. It is authored inline deliberately — no dependency on
workflow discovery, so the skill is portable across repos.

Pass `args` as an object: `{ base, thesis, criteria, level }`.

```js
export const meta = {
  name: 'topology-review',
  description: 'Invariant-class review: what did the old structure guarantee that the new one does not?',
  phases: [
    { title: 'Find', detail: 'one agent per invariant class' },
    { title: 'Verify', detail: 'adversarial check per surviving candidate' },
  ],
}

const FINDINGS = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'lost_property', 'summary', 'failure_scenario', 'fix', 'severity'],
        properties: {
          file: { type: 'string', description: 'repo-relative path' },
          line: { type: 'number', description: '1-indexed anchor line' },
          lost_property: { type: 'string', description: 'the guarantee that used to hold structurally' },
          summary: { type: 'string' },
          failure_scenario: { type: 'string', description: 'concrete inputs/state -> wrong behaviour' },
          fix: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          diff_visible: { type: 'boolean', description: 'false if the anchor line is unchanged by the diff' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'reason'],
  properties: {
    verdict: { type: 'string', enum: ['CONFIRMED', 'PLAUSIBLE', 'REFUTED'] },
    reason: { type: 'string' },
  },
}

const base = args.base
const thesis = args.thesis
const criteria = args.criteria || '(none supplied — skip the acceptance-criteria lens)'

const PREAMBLE = `You are reviewing a change whose structural thesis is:

  ${thesis}

Base ref for the diff: ${base}. Inspect with \`git diff ${base}...HEAD\` and read whole
files, not just hunks.

CRITICAL FRAMING: you are NOT looking for incorrect lines. Assume every hunk is
locally correct — it usually is. You are looking for a property that used to hold
because of the old structure and no longer holds under the new one. The anchor line
for a real finding is very often a line the diff did not touch at all.

Report a finding only with a concrete failure scenario: specific inputs or state
leading to specific wrong behaviour. No scenario means no finding — return an empty
list rather than speculation. Do not report style, naming, or ordinary bugs; the
line-by-line engines already cover those.`

const LENSES = [
  {
    key: 'isolation-loss',
    prompt: `${PREAMBLE}

LENS: ISOLATION LOSS.
Enumerate what per-instance separation used to guarantee for free, then check each
one against the new structure:
- Fault isolation — does one instance's panic, OOM, poison message or bad config now
  take down the others? Check panic hooks, \`process::exit\`, shared runtimes.
- Performance isolation — is work now serialized across instances? Look hard at
  consumer loops, \`while let ... .await\` bodies without \`tokio::spawn\`, shared
  worker pools. Head-of-line blocking is the classic finding here.
- Fairness — shared prefetch/QoS, shared priority queues, shared rate limiters or
  semaphores with no per-tenant budget.
- Ordering — did per-instance sequencing guarantees survive interleaving?
- Blast radius — a retry storm, a poison message, or a slow dependency belonging to
  one tenant now affecting all.
- Security/authz — is a per-instance boundary now enforced only by a query predicate?`,
  },
  {
    key: 'fan-out',
    prompt: `${PREAMBLE}

LENS: FAN-OUT / MULTIPLICITY.
Ask exhaustively: what now executes N times that used to execute once?
Walk every per-instance construction path and count. Look for network connections,
channels, subscriptions, background/watcher tasks, timers, file and keypair reads,
one-time initialisations, schema or mint bootstraps, and metric registrations.
For each: is N× intended, or is the resource shareable because it carries no
per-instance state? Flag anything where the per-instance identity travels in the
message/request rather than in the resource itself — that is a resource that should
have been hoisted and shared.
Also check the reverse: something that must run per instance but is now built once
and shared, silently coupling instances.`,
  },
  {
    key: 'type-semantics',
    prompt: `${PREAMBLE}

LENS: TYPE-SEMANTICS DRIFT.
List every type changed by this diff (especially T -> collection-of-T: Counter to
CounterVec, Gauge to GaugeVec, T to Map<K,T>, single handle to registry).
For EACH such type, enumerate every method called on it anywhere in the codebase and
compare the method's MEANING at the old type versus the new type. Read the actual
library source or docs for both — do not assume.
Compilation success proves nothing here: the dangerous cases are methods that exist
on both types with the same signature and different semantics. Canonical example:
\`reset()\` zeroes one counter on Counter but deletes every label series on
CounterVec.
Also check: iteration order, equality/hashing, Default, Drop, Clone depth, and any
method whose cost changes from O(1) to O(n).`,
  },
  {
    key: 'missing-discriminator',
    prompt: `${PREAMBLE}

LENS: MISSING DISCRIMINATOR.
If this change introduces a scope key (tenant/authority/instance/shard column, label,
or key prefix) so that one store or namespace holds what used to live separately,
then EVERY read, write, aggregate, subquery, uniqueness constraint, index and
in-memory collection must account for it.
Enumerate them all and find the ones that do not. Pay special attention to:
- nested subqueries (an outer query can be scoped while its subquery is global)
- aggregates: MAX/MIN/COUNT/SUM over the whole table
- \`ON CONFLICT\` targets and unique constraints that are now too narrow or too wide
- pagination/keyset cursors that are not unique once rows from multiple scopes coexist
- HashMap/registry inserts that silently overwrite when two entries collide
- pre-existing rows that predate the new column and are now NULL/unset, therefore
  invisible to every scoped query — check whether any backfill exists
Report each unscoped site separately with its failure scenario.`,
  },
  {
    key: 'base-drift',
    prompt: `${PREAMBLE}

LENS: BASE-BRANCH DRIFT.
Determine the branch's base (PR base branch, else main/master) and compute both
\`git rev-list --left-right --count <base>...HEAD\` and the merge-base.
If the branch is behind, list every commit the base gained since the merge-base and
intersect the files those commits touched with the files this branch modifies.
For each overlapping file, determine what the base added and whether this branch's
rewrite would drop it on a naive "keep our version" merge resolution. Features added
on the base and silently lost at merge time are the target — health probes, security
headers, auth checks, migrations, bug fixes.
Also flag work this branch duplicates that the base already did (benign but wasteful
conflicts), and any file this branch adds that ASSERTS behaviour only present on the
base.`,
  },
  {
    key: 'acceptance-criteria',
    prompt: `${PREAMBLE}

LENS: ACCEPTANCE-CRITERIA ADVERSARY.
The stated acceptance criteria / requirements are:

${criteria}

If no criteria were supplied, return an empty findings list immediately — do not
invent requirements.
Otherwise take each criterion in turn and argue ADVERSARIALLY that this change
violates it. Your job is prosecution, not balance: find the input, timing, tenant
mix, failure mode or deployment step under which the criterion breaks. Only concede a
criterion holds after genuinely trying to break it.
Weight operational and business criteria — latency, throughput, no-regression,
data-retention, auditability, rollback — over purely functional ones, since the
functional ones are already covered by the line-by-line engines.`,
  },
]

phase('Find')
const raw = await parallel(
  LENSES.map(lens => () =>
    agent(lens.prompt, { label: `find:${lens.key}`, phase: 'Find', schema: FINDINGS })
      .then(r => (r && r.findings ? r.findings.map(f => ({ ...f, lens: lens.key })) : []))),
)

// Barrier is deliberate: several lenses legitimately land on the same site from
// different directions (fan-out and isolation-loss both find a shared connection),
// and the cap below must rank across the whole pool, not per lens.
const pooled = raw.filter(Boolean).flat()
const byLocation = new Map()
for (const f of pooled) {
  const key = `${f.file}:${f.line}`
  const prior = byLocation.get(key)
  if (!prior || (f.failure_scenario || '').length > (prior.failure_scenario || '').length) {
    byLocation.set(key, f)
  }
}

const RANK = { high: 0, medium: 1, low: 2 }
const deduped = [...byLocation.values()].sort((a, b) => (RANK[a.severity] ?? 3) - (RANK[b.severity] ?? 3))

const MAX_VERIFY = 8
const toVerify = deduped.slice(0, MAX_VERIFY)
const dropped = deduped.slice(MAX_VERIFY)
log(`${pooled.length} raw -> ${deduped.length} deduped -> verifying ${toVerify.length}`)
if (dropped.length) {
  log(`CAPPED: ${dropped.length} lower-severity candidate(s) NOT verified: ${dropped.map(d => `${d.file}:${d.line}`).join(', ')}`)
}

phase('Verify')
const verdicts = await parallel(
  toVerify.map(f => () =>
    agent(`${PREAMBLE}

Adversarially verify this single claim. Try to REFUTE it — read the code and the
surrounding call graph and look for the reason it does not hold.

  file: ${f.file}:${f.line}
  lost property: ${f.lost_property}
  claim: ${f.summary}
  failure scenario: ${f.failure_scenario}

Return REFUTED if the reasoning does not survive contact with the code (for example:
the property was never actually guaranteed before; something else still enforces it;
the scenario cannot physically occur). Return CONFIRMED only if you can trace the
failure scenario concretely in the code. Return PLAUSIBLE if the reasoning stands but
cannot be settled from the code alone — for instance it depends on deployment
topology or configuration not present in the repo.

Default to REFUTED when genuinely uncertain.`,
      { label: `verify:${f.file}`, phase: 'Verify', schema: VERDICT })
      .then(v => ({ ...f, verdict: v ? v.verdict : 'REFUTED', verdict_reason: v ? v.reason : 'verifier failed' }))),
)

const survived = verdicts.filter(Boolean).filter(v => v.verdict !== 'REFUTED')
const refuted = verdicts.filter(Boolean).filter(v => v.verdict === 'REFUTED')

return {
  thesis,
  confirmed: survived.filter(v => v.verdict === 'CONFIRMED'),
  plausible: survived.filter(v => v.verdict === 'PLAUSIBLE'),
  refuted,
  not_verified_due_to_cap: dropped,
}
```

## Interpreting the result

- `diff_visible: false` findings are the ones this skill exists for. Do **not**
  discount them for lacking a diff hunk — that is the signature, not a weakness.
- A finding whose "lost property" was never actually guaranteed before is a false
  positive; the verifier should have caught it, but sanity-check the premise yourself
  against the pre-change code (`git show <base>:<file>`) before reporting.
- Distinguish **pre-existing** from **introduced**. A defect can have existed before
  and have had its blast radius multiplied by this change — say exactly that, and
  cite the pre-change code. It changes who owns the fix and stops the finding reading
  as an accusation.
- Always report `not_verified_due_to_cap` explicitly. Silent truncation reads as
  full coverage.

## Output

**Standalone** (`/topology-review`): report in chat, then persist via the `save-plan`
skill with `TYPE = REVIEW`. Lead with the thesis — every finding is conditional on
it. State which lenses fired and which returned empty.

**Embedded** (`--embedded`, invoked from `code-review`): do not call `save-plan` and
do not print a table. Return the candidate list to the calling skill so it folds them
into its own verification ladder, ID assignment, and report. Carry each candidate's
`verdict` through — they are already verified here; the caller must not re-verify.

Mark every finding's provenance as the topology engine plus its lens
(e.g. `topology/fan-out`) so the compound report shows which engine earned it.
