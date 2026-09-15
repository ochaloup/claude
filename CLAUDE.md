# CLAUDE.md

**SUPER IMPORTANT**: Write short, simple sentences. No compound-complex sentences. Be concise, use plain english.

**SUPER IMPORTANT**: Summary first, then depth. Layer every chat reply so I can stop at any boundary:

1. One bold sentence that answers the question or names the outcome.
2. Bullets with the facts behind it — file:line, values, the decision.
3. Deeper detail last, and only when it changes what I do next.

Each layer stands alone if I stop there. Each layer only adds — never restate an earlier one. Drop a layer that carries nothing. Example:

**The retry loop never fires — the guard returns early.**
- `shouldRetry()` at client.ts:88 checks `attempts > max`, but `attempts` resets on each call.
- So every request gets one attempt.
- Fix: move the counter to the caller.

Why it was hard to see: the reset lives in a different function than the check.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## Strict rules (non-negotiable)

- Never run `git push` or any remote-writing git command. Ask only when a push is actually the next action; don't preemptively mention, offer, or seek permission for pushes otherwise. Posting or resolving PR comments is never such a case.

## 0.1. System settings

- Max 4 parallel agents when delegating tasks. Exception: inside explicitly requested workflows (Workflow tool), the workflow's own concurrency limit applies.
- For any code output that can be useful for copy&paste purposes (testing, check-ups, placing to editor...): no formatting, flush left, no trailing whitespace.
- Comments:
  - ZERO by default. At most 1 short line, ONLY when the WHY is not derivable from names, types, or surrounding code. Comments carry rationale/design/context — never restate WHAT the code does.
  - Redundancy test (delete if it fails): a comment is banned if its content is already visible in adjacent code, INCLUDING a log/error message on a neighboring line. Restating or paraphrasing a warn!/error!/log message in a comment above it is the canonical bug. Good: a non-obvious invariant or a cross-module assumption. Bad: anything a reader sees in the next 1-2 lines.
  - Never multi-line, in ANY syntax: no ///, no /** */, no stacked //, no stacked # (YAML, TOML, shell, Python, Dockerfile). One comment = one line, ≤100 chars. A second consecutive comment line is a bug — fix it.
  - If the WHY needs more than one line, the file is the wrong place. It goes in the commit message or PR body. Write the one line that names the constraint, drop the rest.
  - Never put a source line number in a comment (e.g. // see line 200, // as in L42). Diff-gutter numbers like `255 +` are NOT part of the code and must never end up in a comment. Pointing to a file and/or function name is fine.
  - Never put tickets numbers, code number lines into comments
- Markdown docs (README.md, ARCHITECTURE.md, any *.md — NOT config files, which follow the Comments rules above verbatim): the Comments rules above apply to prose too. Say the WHY and the WHAT in the fewest sentences that carry them. Never narrate the investigation, never restate what the code, a table, or a log message on the page already says. Two or three sentences beat a paragraph; a worked example earns its place only if a reader must act on it. Edit the existing sentence instead of appending a new paragraph beside it, and delete what your change made redundant.
- If a Docker-dependent step (testcontainers, `docker` CLI, etc.) fails with `SocketNotFoundError("/var/run/docker.sock")` or "Cannot connect to the Docker daemon", this machine likely runs Podman, not Docker. Suggest the user export `DOCKER_HOST=unix:///run/user/1000/podman/podman.sock` and retry — do not chase it as a code bug.

### 0.21. Shell discipline

- Run ONE command per bash invocation. No pipes (|), no semicolons (;), no redirects (>).
- To save command output: let Claude capture it from stdout, or use the Write tool.
- To post-process JSON: run jq as a separate bash call on a file written in a prior step.
- Reason: multi-command strings don't match the project's permission allow-list patterns
  and will trigger interactive permission prompts.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Ask clarifying questions before answering.

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Be Strict with Testing

If you relax a check, you must clearly explain and verify why. Never remove or weaken assertions without adding explicit validation. Be strict. ALWAYS.

You cannot say:
“Re-processing can produce a second exit order, so I’ll remove the limit.”
If you claim that, you must add a check that proves this behavior is valid and expected.

You cannot say:
“The redo log watcher may produce a duplicate exit order, so at least one valid order is enough.”
Only allow this if it is explicitly validated. Prefer keeping strict expectations and add a separate check that confirms when `count == 2` is valid.

## 6. Be cautious

Do not use expressions like: "the comment is technically valid but not a real problem in the current architecture".

When the architecture changes then the function call still has to be working well.

## 7. Code Reuse & Dependencies

- Match the code style (formatting, naming, patterns) of the project you're operating on.
- Before adding a new dependency, verify it isn't already used in the repo. If it's truly new, ask for explicit approval before adding it.
- Check if the project has `pnpm fix` (or `pnpm lint` - older TS projects, `cargo fmt && cargo clippy --fix` for rust only projects) build target in package.json. If so then run it after every change and fix the reported issues.
  And also fix all lint errors when there are any — don’t be narrowly focused only on the changes you just made (don’t say "lint errors are pre-existing")


## 8. Typescript code

- Before implementing generic/utility functionality, check `/home/chalda/marinade/typescript-common/` for existing reusable code.
  When creating new generic functionality, evaluate if it belongs in `typescript-common/` rather than the current project. If so, add it there and consume it as a dependency.
- Prefer `bigint` when applicable
- Prefer `Decimal` (from `decimal.js`) over JavaScript `number` for arithmetic — especially for token amounts, rates, and financial calculations.

### 9. Code Quality

- When applying fixes (e.g. during code review), always prefer the solution with the least added complexity. Avoid over-engineering; a smaller, clearer change is better than a thorough but complex one.
- After applying a review fix, re-read the comments around the changed code (above and nearby). Update any that no longer match the new behavior, or delete them if they now only restate the code.

### 10. GitHub

- When I ask you to respond on PR be transparent that the response is generated by you - Claude. At the start of the response add a prefix of style: '🤖 claude:'
- Keep every PR comment to 1-2 sentences. State the decision (fixed / declining) plus the one reason that matters — longer reasoning belongs in the chat, not on GitHub.
- Never mention local repository state in a PR comment: no "not yet pushed", "uncommitted", "will push shortly", or branch mechanics. Write it as if the change is already part of the PR.
- "post" means post now. On "post the comments" (or comment / reply / resolve / close), do it in the same turn. Never show a draft and wait for approval.
- Local git state never blocks a PR action. Uncommitted or unpushed work is still reported as done. Do not check for a push, mention one, or wait for one — pushing is my job, at my own time.
- "close the comments" means resolve every thread you posted on — fixed and declined alike.
- After posting, report one line per thread: id, decision, link. Nothing else. No re-summary of the fix.
- Loose ends go in a short list after that report. They never delay the posting.

### 11. "3 step" summaries

`3 step` plus a link means: read the full source — not the abstract, not the preview — then write one continuous summary in three layers of growing length.

- **Layer 1** — one paragraph. The whole piece at maximum compression.
- **Layer 2** — two paragraphs. Mechanism, key evidence, how the result was produced.
- **Layer 3** — three paragraphs. Methodology specifics, numbers, context, limitations, implications.

Label each layer with a short bold line of its own ("Layer 1"). No other headers or formatting inside them. Every layer continues from the previous one and never restates it, so 1, 1+2 and 1+2+3 each read as a complete summary at their own depth. Compression is the point; analysis serves it.

Write plain, direct sentences for a smart reader outside the field. Use the standard technical term whenever it is shorter or more precise than a paraphrase — never trade precision or brevity for simplicity. Gloss a term only if that reader would not know it, in a few words, once.


---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
