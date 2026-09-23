---
name: design-impact
description: High-level design summary of a diff against a base ref — API endpoints, message contracts, process flows, business logic, services, service coupling, data schema, big dependency changes, config and other service-design shifts. Every hit cites file:line; empty categories are stated as none, unchecked ones as not verified. No findings, no verdicts. Use when the user runs /design-impact, and as the embedded step chained from the code-review skill.
when_to_use: you need to know what a branch changes at the service-design level, not whether the code is correct; for defects use code-review
argument-hint: "[--base <ref>] [--embedded]"
---

# Design Impact

Say what the diff changes at the service-design level. Not whether it is correct —
that is code-review's job. The reader should know in ten seconds whether an API,
a flow, a business rule, a service or a dependency moved.

## Inputs

- `--base <ref>` — base ref. If absent, try `git diff main`, then `git diff master`.
- `--embedded` — called from another skill: return only the output block, no preamble.

Every bash call is one plain command: no `$(...)`, no `&&`/`;` chains, no pipes, no
redirects. Resolve computed values in their own call and reuse the literal result.

## Method

1. Run `git diff --stat <ref>`, then `git diff <ref>`.
2. For each category below, look at the diff with the hints given. Grep the diff's own
   symbols; read the enclosing code only when a hunk alone cannot tell you what changed.
3. Classify each category: a hit, `none`, or `not verified`.

| Category | What counts | Where to look |
|---|---|---|
| API endpoints | HTTP/gRPC/RPC routes, CLI commands, public library exports, on-chain instructions — added, changed, removed | route registrations, handlers, OpenAPI/proto/IDL files, `pub`/`export` surface |
| Message contracts | queue, topic, webhook and event payloads or names | producers, consumers, schema/type files for messages |
| Process flows | a new or reordered sequence of steps, a state machine, a job or schedule | orchestrating functions, cron/schedule config, state enums |
| Business logic | a formula, threshold, rate, fee, eligibility or scoring rule, rounding direction, or a user-visible state transition changes its outcome — including an unchanged formula fed a different input | constants, calc/rules modules, conditionals on money or eligibility, changed expected values in tests |
| Services | a service, worker, deployment or binary added, removed, split or merged | new `main`/entrypoints, Dockerfiles, K8s/Helm manifests, CI deploy jobs |
| Service coupling | a new outbound call, a new shared DB/queue/cache, a dependency direction reversed | HTTP/RPC clients, connection strings, new env vars naming hosts |
| Data & schema | migrations, tables, columns, indexes, storage keys, on-chain account layouts | `migrations/`, SQL, ORM models, account structs |
| Dependencies | a new dependency, a removed one, a major-version bump; patch/minor only when it changes behaviour | `package.json`, `Cargo.toml`, `pyproject.toml`, lockfile diffstat |
| Config & env | new or renamed env vars, config keys, feature flags, secrets | `.env*`, config loaders, `process.env`, `std::env::var`, Helm values |
| Other design | auth boundary, concurrency model, caching strategy, error-handling contract | judgement over the whole diff |

For every API or message-contract hit, state whether it is **breaking** for existing
callers: removed or renamed field, changed type, new required input, changed status or
error shape.

For every business-logic hit, state the rule before and after, and who gets a
different result. A renamed variable or a refactor that keeps every outcome is not a hit.

## Do not guess

Cite `file:line` for every hit. A hit without a location is a guess, so drop it.
The line is the line in the file at HEAD, found with `grep -n` on that file — never a
position in the `git diff` output. Removed code is cited at the base, `path@<base>:line`,
found with `git show <base>:path`. A deleted file is cited as `path (deleted)`.
If a category could not be checked — a generated file too large to read, a contract
defined in another repo — mark it `not verified` and name what is missing. Never infer
a change from a filename.

## Output

Hits first, grouped by category. One bullet per category, at most 40 words and 3
locations — name the headline change and drop the detail. The whole block stays under
300 words. Then one line for the empty categories, omitted when there are none.

The `Not verified` line is always printed. List every unclear part: a contract, API or
schema owned by another repo that the diff calls or changes, a file only sampled, a
business-logic outcome the code alone cannot settle. Only when all of it was checked,
print `Not verified: nothing — all categories checked.`

```
**Design impact**
- API endpoints: `POST /v1/withdraw` added, non-breaking. `GET /v1/stake` drops field
  `epoch`, breaking — `src/api/routes.ts:41`, `src/api/stake.ts:88`.
- Business logic: withdraw fee goes from 0.3% of amount to 0.3% capped at 5 SOL, so
  withdrawals above ~1667 SOL pay less — `src/fees.ts:22`.
- Service coupling: calls `validator-bonds` API on every settle — `src/settle.ts:120`.
- Dependencies: `@solana/web3.js` 1.x → 2.x — `package.json:14`. Run /dependency-update-check.
- No change: message contracts, process flows, services, data & schema, config & env, other design.
- Not verified: IDL for `bonds` program lives in another repo.
```

If nothing at all changed at design level, print the `none` line, then the
`Not verified` line:
`**Design impact:** none — internal change only.`

Standalone runs print the block and stop. `--embedded` returns the block verbatim.
