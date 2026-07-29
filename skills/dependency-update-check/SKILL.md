---
name: dependency-update-check
description: Verifies a dependency version bump won't break the service before it merges — resolves exactly which packages changed and by how much, installs the new versions, builds/typechecks, starts the service locally to confirm it boots and stays healthy, runs the test suite when that's reasonable, and researches each meaningfully-bumped package's changelog (web retrieval + prior knowledge) for breaking changes the codebase actually exercises. Ends with a SAFE/RISKY/UNSAFE verdict.
when_to_use: before merging a manual pnpm/cargo/pip update or a Renovate/Dependabot PR, when "CI is green" isn't enough assurance that the new versions won't crash the service
argument-hint: "[<package>[@<version>]|<PR#>|<PR-url>|--base <ref>|(none = uncommitted manifest changes, else branch vs base)]"
---

# Dependency Update Safety Check

Arguments: $ARGUMENTS

The question this answers is never "does it compile" alone — it's **"will this
crash the running service."** Compiling, booting, passing tests, and having no
known breaking change in the exercised surface are four independent checks;
report on all four, don't let a pass on one stand in for the others.

## Shell discipline

One plain command per bash call — no `$(...)`, no `&&`/`;` chains, no redirects.
Resolve a computed value (merge-base, PR branch, current version) in its own call
and reuse the literal result. This applies to any subagent prompt this skill
constructs too.

## 1. Resolve scope

Parse the arguments:

- **`<package>[@<version>]`** — a bump not yet applied. Read the package's current
  declared version from the manifest, then apply the bump yourself (edit the
  manifest / run the manager's upgrade command) before continuing to step 2. This
  is a local, reversible change (`git checkout` undoes it) — proceed, but say
  what you changed.
- **`<PR#>` / `<PR-url>`** — check `git status` first; if there's uncommitted work,
  stash it (`-u`) before checking out the PR branch. Resolve owner/repo/branch the
  same way the `pr-review` skill does, then `gh pr checkout <PR#>`. Diff base is
  the PR's base branch.
- **`--base <ref>`** — diff the current branch against `<ref>`.
- **none** — check `git status` for uncommitted changes to manifest/lock files
  (`package.json`, `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`,
  `Cargo.toml`, `Cargo.lock`, `pyproject.toml`, `poetry.lock`, `requirements*.txt`,
  `go.mod`, `go.sum`). If any exist, that's the scope. Otherwise diff the current
  branch against `main`, then `master` (same fallback as `code-review`). If
  neither shows a manifest/lock change, say so and stop — nothing to check.

## 2. Identify ecosystem, package manager, and affected workspace

Detect from the manifest files present:

| Ecosystem | Manifest | Lockfile | Install | Build/typecheck | Test |
|---|---|---|---|---|---|
| npm/pnpm/yarn | `package.json` | `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` | `pnpm install` / `npm ci` / `yarn` | `pnpm build`, `tsc --noEmit` | `pnpm test` |
| Cargo | `Cargo.toml` | `Cargo.lock` | `cargo fetch` | `cargo check` / `cargo build` | `cargo test` |
| pip/poetry | `pyproject.toml` / `requirements*.txt` | `poetry.lock` | `poetry install` / `pip install -r` | — | `pytest` |
| Go | `go.mod` | `go.sum` | `go mod download` | `go build ./...` | `go test ./...` |

If the repo is a workspace/monorepo (`pnpm-workspace.yaml`, Cargo workspace
members, `go.work`), scope everything below to only the workspace package(s)
whose own dependency graph includes the changed package(s) — don't rebuild or
start unrelated services.

Check for a `pnpm fix` / `pnpm lint` script, or `cargo fmt && cargo clippy` for a
Rust-only project, per the standing project convention — run it in step 4 if
present.

## 3. Enumerate exact version deltas

From the resolved diff, extract per changed package: name, from → to version,
bump type (major/minor/patch), and whether it's declared directly in the
manifest or only moved in the lockfile (transitive).

Table every **direct** dependency change individually. Collapse transitive-only,
patch-level bumps into a single summary line ("N transitive deps, patch-level
only") — they're not worth a row each, and step 7 skips deep research on them
unless something later traces a failure back to one.

## 4. Install, build, typecheck, lint

Run the ecosystem's install command from the table above, capturing full output
— peer-dependency conflicts and engine-mismatch warnings are exactly the failure
mode this check exists to catch; don't let them scroll by unread.

Then run the project's own verification commands and record each result:
build/typecheck, then `pnpm fix`/`pnpm lint` or `cargo fmt && cargo clippy` if
the project has them. A failure here is high-signal — an incompatible major bump
usually shows up here first, before runtime.

## 5. Start the service locally

Skip this step with a one-line note if the repo has no long-running process
concept (a library, an on-chain program, a CLI invoked per-run) — say so rather
than fabricating a boot check that doesn't apply.

Only proceed if step 4's build/typecheck passed (or there is no build step) —
starting something that doesn't compile just reproduces the same failure.

Determine the start command, in priority order: `package.json`
`scripts.dev`/`scripts.start`, `wrangler dev` for Workers projects (see the
`wrangler` skill for flags), `cargo run`, `go run .`, a `docker-compose` service
definition, or the README's quick-start. In a workspace, start only the
service(s) whose dependency tree includes the changed package(s).

Run it as a background process with a bounded boot window (~30-45s covers most
dev servers; extend once if logs show active compilation still running). Judge
success from all of:

- the process is still alive at the end of the window
- a "listening"/"ready"/compiled-successfully log line, an open port, or a 2xx
  from a health endpoint if one exists
- no crash signature in the captured output (uncaught exception, unhandled
  rejection, panic, traceback, non-zero early exit)

Missing local infra (a DB, queue, or secret this environment doesn't have) is
**not** the same as "broken by the update" — report it as **could not verify
startup (missing: X)**, not a failure.

**Always kill the background process before finishing this check**, whether it
started cleanly or not. Never point the started instance at anything but
local/dev config — never use production secrets or endpoints to work around a
missing-infra gap.

## 6. Run the test suite, if that's reasonable

"Reasonable" means: a test command exists, it doesn't require infrastructure or
secrets this environment lacks, and it isn't a suite you have reason to know is
a slow/flaky full end-to-end run. If unsure, run a scoped subset first (tests
covering the changed package's actual usage sites) rather than skipping
entirely.

If tests are skipped, state why explicitly in the report — never omit this
section silently.

## 7. Research compatibility for meaningfully-bumped packages

Bound the effort — not every changed package needs research:

- **Always research**: any major version bump, and any minor bump whose own
  changelog flags breaking notes (common in pre-1.0 packages, where minor ==
  breaking).
- **Skip deep research**: patch-only and transitive-only bumps, unless step 4/5/6
  already traced a failure back to one.
- **Cap at ~6 packages** if more qualify. Note which were skipped and why —
  silent truncation reads as full coverage.

For 3 or more packages needing research, parallelize via the `Agent` tool
(`general-purpose`, max 4 concurrent) — one self-contained prompt per package
with the repo path, package name, and exact from/to version range. For 1-2
packages, do it inline. Each research pass must:

1. Retrieve the changelog/release notes for exactly the version range crossed
   (npm registry page, GitHub releases, crates.io, PyPI — whichever applies) via
   `WebFetch`/`WebSearch`. Don't rely on pretrained knowledge alone — it may
   predate the release. Explicitly flag when retrieval failed and the verdict
   falls back to pretrained knowledge (knowledge cutoff January 2026 — anything
   released after is unverifiable from training alone).
2. Grep the codebase for actual usage of the package's changed surface (imported
   symbols, config keys, CLI flags named in the breaking-change notes). A
   breaking change to an API this codebase never calls is not a risk here.
3. Record a verdict — **safe** / **caution** / **breaking** — with the evidence
   (quote or link) that justifies it.

## 8. Verdict and report

Combine steps 3-7 into one report, printed to chat:

```
## Dependency Update Safety Check

Scope: <ecosystem> · <package manager> · <N> package(s) changed (<M> direct, <T> transitive-only)

| Package | From | To | Bump | Risk |
|---|---|---|---|---|
| ... |

### Install — PASS/FAIL
<details>

### Build / typecheck / lint — PASS/FAIL/SKIPPED
<details>

### Local startup — STARTED CLEANLY / CRASHED / COULD NOT VERIFY (reason) / N/A (no service)
<details, including health-check result>

### Tests — RAN (<scope>) PASS/FAIL / SKIPPED (reason)
<details>

### Compatibility research
<package> <from> -> <to> (<bump type>)
- Breaking changes found: ...
- Used in this codebase: yes/no — <files/APIs>
- Verdict: safe / caution / breaking
- Source: <URL, retrieved> or "prior knowledge only — retrieval failed/unavailable"
(repeat per researched package; list skipped-from-research packages in one line)

### Overall verdict: SAFE / SAFE WITH CAVEATS / RISKY / UNSAFE
<one paragraph rationale>

### Recommended next steps
<only if not a clean SAFE>
```

Verdict rules:

- **UNSAFE** — build/typecheck failed, the service crashed on boot, or a
  researched package has a confirmed breaking change this codebase actually
  exercises.
- **RISKY** — everything ran, but a package landed in "caution" (ambiguous
  exposure, or research fell back to pretrained knowledge for a release past the
  cutoff), or tests were skipped for a change touching a package with real usage.
- **SAFE WITH CAVEATS** — install/build/tests/research all clean, but startup or
  tests couldn't be verified locally (missing infra) — name the gap so it's
  covered elsewhere (staging/CI) before merge.
- **SAFE** — install, build, startup, and tests all passed, and every
  meaningfully-bumped package researched clean.

## 9. Persisting

This is normally a one-off local check — the chat report is the whole
deliverable. Persist it via the `save-plan` skill (`TYPE=REVIEW`) only when the
user asks for a durable record, or the verdict is RISKY/UNSAFE on an update
spanning enough packages that someone else will need the reasoning later (a
batched Renovate/Dependabot PR, for example).

## 10. Cleanup

Before finishing: confirm no background service process from step 5 is still
running, and if you checked out a PR branch in step 1, leave the working tree as
you found it (switch back, pop any stash) unless the user asked to stay on it.
