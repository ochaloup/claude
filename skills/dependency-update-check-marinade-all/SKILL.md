---
name: dependency-update-check-marinade-all
description: Find every open Dependabot PR in marinade-finance, skip skip-list, archived and inactive repos, drafts and superseded bumps, then run the dependency-update-check skill on each remaining PR, one at a time, each in a throwaway worktree under ~/marinade/.dependabot-worktrees. Ends with one table — repository, summary, PR link, merge recommendation with its reason. PRs I reacted to with 👀 are parked and skipped; --park adds that reaction. Never merges, approves, closes or comments on a PR.
when_to_use: the user wants all pending Dependabot PRs across marinade-finance checked for breakage and supply-chain risk in one run, and a merge/no-merge list at the end
model: sonnet
argument-hint: "[--dry-run] [--repo <name>] [--limit <n>] | --park <pr-url>..."
---

# Dependency update check — all marinade Dependabot PRs

Arguments: $ARGUMENTS

With `--park <pr-url>...`, run only this and print one line per PR, then stop:

```
python3 ~/.claude/skills/dependency-update-check-marinade-all/dependabot_all.py park <pr-url>...
```

It adds my 👀 reaction to the PR description. It means "not now", not "rejected".
To unpark, remove the reaction in the GitHub UI.

## 1. Triage

```
python3 ~/.claude/skills/dependency-update-check-marinade-all/dependabot_all.py triage [--repo <name>]
```

It prints a JSON list, one row per open Dependabot PR. `status` is one of:

- `CHECK` — run the check on it.
- `SUPERSEDED` — a newer PR in the same repo bumps the same package.
- `CI-RED` — the PR head's CI failed. Not checked: CI gets fixed first.
  `detail` lists the failing jobs as `<workflow> / <job>`.
- `SKIPPED` — skip-list repo, archived repo, inactive repo (no default-branch
  commit within `INACTIVE_DAYS`), draft, or parked (my 👀 reaction on the PR
  description). `detail` says which.

`ci` is the PR head's combined check state. The skip list is the shared
`MARINADE_ALL_SKIP_REPOS` env var (see code-review-marinade-all). The inactivity
threshold lives in the script; edit it there.

With `--dry-run`, print the output of step 3 with every `CHECK` row as
`READY` and stop. With `--limit <n>`, check only the first `n` `CHECK` rows; the
others get `NOT RUN`.

## 2. Check each PR, one at a time

Never run two checks at once. For each `CHECK` row, in order:

1. `python3 ~/.claude/skills/dependency-update-check-marinade-all/dependabot_all.py prepare <repo> <number>` — clones the repo if missing,
   fast-forwards the local default branch, fetches the PR head and creates a
   detached worktree. It prints `dir`, `base`, `branch` and `warn`. On `error`,
   record the row as `FAILED` with that message and go to the next PR.
2. Run one `Agent` (`general-purpose`, `model: sonnet`) with this prompt,
   filled in:

   ```
   Invoke the dependency-update-check skill with arguments: --repo <dir> --base <base>
   This is Dependabot PR <url> (#<number>, branch <branch>). The worktree is detached at the PR head; use the PR number wherever the skill looks up the PR.
   Run unattended. Never ask the user. Where the skill says to ask (installing a toolchain, cloning), skip that check and report it as an open gap. Do not persist through save-plan.
   Do not skip steps 4-6 because the change is lockfile-only or small; run install, build and startup unless the skill itself marks them N/A. Apply the verdict rules exactly: unverified startup or tests mean SAFE WITH CAVEATS, not SAFE.
   Run every step 7b lookup, install-time code included; any lookup you skip makes SUPPLY_CHAIN PARTIAL.
   If the Agent tool is unavailable, do the skill's delegated steps inline.
   Run the skill to its full report, then reply with ONLY these lines:
   VERDICT: SAFE | SAFE WITH CAVEATS | RISKY | UNSAFE
   SUMMARY: <what the PR bumps, one short line, e.g. "vite 7.3.5 -> 7.3.7 (patch, dev)">
   REASON: <the one decisive fact behind the verdict>
   SUPPLY_CHAIN: CLEAN | FLAGGED <what> | PARTIAL <what failed>
   FIXES: <GHSA ids this bump fixes, or none>
   GAPS: <open gaps, or none>
   ```

3. Wait for its result. Then `python3 ~/.claude/skills/dependency-update-check-marinade-all/dependabot_all.py cleanup <repo> <number>`, also after a
   failed check.
4. Print one progress line: `<i>/<total> <repo>#<number> <VERDICT>`.

Never fix a `FAILED` row. Uncommitted changes or a diverged default branch are
the user's call. Never merge, approve, close or comment on any PR. The only
write is the 👀 reaction in `--park` mode.

## 3. Output

One bold line: `<c> checked — <m> merge, <h> hold, <d> don't merge, <r> red CI, <s> superseded, <f> failed`.
Then one table with every `CHECK`, `CI-RED`, `SUPERSEDED` and `FAILED` row:

| Repository | Summary | PR | Recommendation |
|------------|---------|----|----------------|

PR is a markdown link `[#<n>](<url>)`. Recommendation is a bold word and a short
reason:

- SAFE → **MERGE**, plus `fixes <GHSA>` when `FIXES` lists one.
- SAFE WITH CAVEATS → **MERGE AFTER** — the gap to close first.
- RISKY → **HOLD** — the `REASON`. A too-new release reads `HOLD — re-check after <date>`.
- UNSAFE → **DON'T MERGE** — the `REASON`.
- CI-RED → **FIX CI** — the failing jobs from `detail`, e.g. `Static Analysis / clippy, Trivy - Scan / Trivy Scan`.
- SUPERSEDED → **CLOSE** — `superseded by #<n>`.
- FAILED → **NOT CHECKED** — the error.

Sort by recommendation in that order, then by repository. A `warn` from
`prepare` goes into the Recommendation cell. Under the table, one line with the
skipped counts by reason, e.g. `Skipped: 100 archived, 22 skip-list, 3 parked, 2 inactive`.
Nothing after that line.
