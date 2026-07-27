---
name: code-review
description: Review this branch's changes against a base ref using git diff, pooling three engines — your own objectives, a parallel codex review, and Claude Code's built-in multi-agent review workflow — then verifying every candidate before it becomes a finding. Assigns round-scoped IDs, persists the report through the save-plan skill, and ends with a summary table. Use when the user runs /code-review, or when the pr-review-followup skill needs a review scoped to new changes.
when_to_use: reviewing branch/uncommitted work against a base ref; for reviewer feedback on an open PR use pr-review instead
argument-hint: "[--base <ref>] [low|high|xhigh|max]"
---

# Code Review

Review the changes in this branch against a base ref using git diff.
Defaults to main/master if `--base` is not provided.

Determine the base ref as follows:
- If an argument `--base <ref>` is provided in this prompt, use that ref.
- Otherwise, try `git diff main` first; if that fails or returns nothing, try `git diff master`.

Determine the engine level: if a bare `low`, `high`, `xhigh`, or `max` token is
present in the invocation, that is LEVEL; otherwise LEVEL is `high`. It controls
only the built-in engine's fan-out, not your own analysis.

For each changed file, read the full file — not just the diff — to understand context, 
detect duplication, and identify broken invariants.
For structureal changes and config/manifest directories, also read sibling files in the same directory and any file the diff transitively references 
- bugs in declarative config are usually inconsistencies across files, not within one.

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
6. **Simplification opportunities** — Identify code that could be meaningfully 
   shortened or clarified without changing behavior: unnecessary abstractions, 
   overly defensive checks, verbose constructs replaceable by a standard library 
   call, or logic that can be collapsed. Provide the simplified version inline.
   Only flag if the simplification reduces lines or cognitive complexity meaningfully 
   (not just style preference or minor renaming).
7. **Code reusability** — Check shared libraries before writing utility logic.
   For TS: use typescript-common (expected location $HOME/marinade/typescript-common/)
   if a package from that present in package.json; if not, notify that it should be considered.
8. **Security awareness** — Be mindful of common vulnerabilities: avoid exposing secrets or credentials in code,
   validate and sanitize inputs, prefer well-maintained libraries over custom crypto/auth implementations,
   and flag any suspicious patterns (e.g. SQL injection risks, unsafe deserialization, overly permissive access controls).
9. **Configuration & manifest consistency (YAML/K8s/IaC)** — For changes to
   declarative config (K8s manifests, Helm, Kustomize, Argo CD, Terraform,
   CI configs), check cross-file consistency, not just local correctness.
   Read sibling files and anything the diff transitively references
   (Application sources, Kustomize bases, Helm values).
   Verify:
   - **Enumerated lists match reality.** Explicit lists of namespaces,
     services, envs, accounts, repos (ECR auth CronJob, ApplicationSet
     generators, NetworkPolicy peers, RBAC subjects, Kustomize `resources:`)
     stay in sync with what's actually defined elsewhere.
   - **References resolve.** ServiceAccount, Secret, ConfigMap, Role,
     PVC, Service, Ingress backend, image refs point at something that
     exists in the right namespace.
   - **New namespaces are enrolled in shared infra.** Image pull secrets,
     monitoring selectors, logging, NetworkPolicies, cert-manager,
     external-secrets, backups, RBAC. Catches `ImagePullBackOff` /
     no-metrics / default-deny surprises.
   - **GitOps picks it up.** New manifests are selected by some Application
     or ApplicationSet (path globs, generators, value files). Otherwise
     it's dead config.
   - **Selectors and labels are symmetric.** Service → Pod, NetworkPolicy
     podSelector, HPA target, ServiceMonitor — selectors match the labels
     actually set, and don't over-match.
   - **Schema sane.** `apiVersion`/`kind` valid and not deprecated; required
     fields present; image tags pinned in prod; resource requests/limits
     where namespace enforces them.
   - **No plaintext secrets.** Use the repo's external secret convention
     (SealedSecrets, ExternalSecrets, SOPS).
   Render-time check: would `kustomize build` / `helm template` /
   `kubectl apply --dry-run=server` / `argocd app diff` succeed?

Only report problems. No praise, no neutral observations.


## Parallel codex review

In parallel with your own analysis, ask `codex` to review the same diff and fold its findings in.

1. **Kick off codex early.** Right after you've resolved the base ref and before you start reading files, run `codex exec review` as a background bash call so it works while you do:
   ```
   codex exec review --base <ref>
   ```
   Use the same `--base <ref>` you resolved for your own review. Use `Bash` with `run_in_background=true` so you continue immediately. Do NOT redirect output to a file — a redirect triggers an interactive permission prompt; the harness captures stdout/stderr of the background call.
2. **Do your own review** per the Objectives above. Do not wait for codex — your analysis is independent and primary.
3. **When codex finishes**, read its captured output from the background task result.
4. **Integrate** codex findings into your compound review:
   - Valid finding you missed → add it to the compound review.
   - Duplicate of one of your findings → leave your version in place.
   - Wrong or noise → drop it from the compound review (it still appears in the raw subsection for audit).
   No inline attribution needed in the compound review; the raw subsection records provenance.
5. **Preserve the raw output** verbatim under the REVIEW chapter — see Output below.

If `codex` is not installed (`which codex` fails) or the background call errors, skip the raw subsection and note the reason in one line — do not block the rest of the review.


## Built-in review engine

Claude Code ships a multi-agent review pipeline — Scope → Find → Verify → Sweep →
Synthesize — registered as a workflow named `code-review`. Run it as a third engine.

Kick it off in the same step as codex, right after the base ref is resolved:

```
Workflow({ name: "code-review", args: "<LEVEL> <BASE_REF>" })
```

Invoking this skill is itself the opt-in for that Workflow call — do not ask for
separate confirmation. The workflow's own concurrency limit governs its fan-out.

It returns immediately with a task ID and notifies on completion, so continue with
your own analysis meanwhile. Its findings arrive already verified by its internal
per-candidate verifier and carry a CONFIRMED or PLAUSIBLE verdict — carry that
verdict through instead of re-verifying.

Fold its findings into the compound review on the same terms as codex: valid and
missed → add; duplicate of yours → keep your version; wrong → drop from the
compound review, leaving it in the raw subsection for audit.

Its five correctness angles (line-by-line scan, removed-behavior audit, cross-file
caller tracing, language pitfalls, wrapper/proxy routing) overlap your Objectives
only partially — do not treat its silence on Objectives 7-9 as a clean bill, since
it has no notion of typescript-common reuse or K8s/IaC cross-file consistency.

If workflows are unavailable or the call errors, skip this engine and note the
reason in one line — do not block the rest of the review.


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

Before assigning IDs, pool the candidates from all three engines and put the
unverified ones through one verification pass. Candidates returned by the built-in
workflow are already verified — keep their verdict and skip them here.

1. **Dedup.** Collapse candidates pointing at the same line and the same mechanism,
   keeping the one with the most concrete failure scenario.
2. **Verify each remaining candidate.** Give the verifier the diff, the relevant
   file(s), and that candidate alone. It returns exactly one of:
   - **CONFIRMED** — the defect is real and the failure scenario holds.
   - **PLAUSIBLE** — not confirmable from the code at hand, but the reasoning stands
     and it warrants a human look.
   - **REFUTED** — the reasoning does not survive contact with the code.
   Delegate to subagents when available, at most 4 in parallel; otherwise verify
   sequentially in this context.
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

Whether `save-plan` creates a new file or a new `REVIEW` chapter inside an existing multi-type file, the chapter body must be ordered as:

1. **Compound review** (first, primary) — your verified findings with the codex and built-in-engine findings folded in. This is the actionable part the reviewer reads. Each finding uses its `<ID>` (e.g. `P1-R1#1`) and carries its verdict.
2. **Carried-forward prior findings** (if any) — STILL_PRESENT / UNCERTAIN entries from prior rounds, original IDs preserved.
3. **Raw codex review** (subsection, e.g. `### Raw codex review`) — the verbatim captured output of the `codex exec review` background call. Do not edit, trim, summarize, or reformat it; preserve it as-is so the reader can audit independently.
4. **Raw built-in review** (subsection, e.g. `### Raw built-in review`) — the verbatim report returned by the `code-review` workflow, including candidates it REFUTED, under the same no-editing rule.

For any engine that was unavailable or failed, omit its raw subsection and add one line under the compound review noting why (e.g. `codex unavailable: <reason>`, `built-in engine unavailable: <reason>`). Say which engines actually ran — a review that silently lost an engine must not read as a three-engine review.
