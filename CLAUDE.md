# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## Strict rules (non-negotiable)

- Never run `git push` or any remote-writing git command. Ask only when a push is actually the next action; don't preemptively mention, offer, or seek permission for pushes otherwise.

## 0.1. System settings

- Max 4 parallel agents when delegating tasks. Exception: inside explicitly requested workflows (Workflow tool), the workflow's own concurrency limit applies.
- For any code output that can be useful for copy&paste purposes (testing, check-ups, placing to editor...): no formatting, flush left, no trailing whitespace.
- Comments:
  - ZERO by default. At most 1 short line, ONLY when the WHY is not derivable from names, types, or surrounding code. Comments carry rationale/design/context — never restate WHAT the code does.
  - Redundancy test (delete if it fails): a comment is banned if its content is already visible in adjacent code, INCLUDING a log/error message on a neighboring line. Restating or paraphrasing a warn!/error!/log message in a comment above it is the canonical bug. Good: a non-obvious invariant or a cross-module assumption. Bad: anything a reader sees in the next 1-2 lines.
  - Never multi-line: no ///, no /** */, no stacked //. A comment block >1 line is a bug — fix it.
  - Never put a source line number in a comment (e.g. // see line 200, // as in L42). Diff-gutter numbers like `255 +` are NOT part of the code and must never end up in a comment. Pointing to a file and/or function name is fine.
  - Never put tickets numbers, code number lines into comments
- If a Docker-dependent step (testcontainers, `docker` CLI, etc.) fails with `SocketNotFoundError("/var/run/docker.sock")` or "Cannot connect to the Docker daemon", this machine likely runs Podman, not Docker. Suggest the user export `DOCKER_HOST=unix:///run/user/1000/podman/podman.sock` and retry — do not chase it as a code bug.

### 0.21. Shell discipline

- Run ONE command per bash invocation. No pipes (|), no semicolons (;), no redirects (>).
- To save command output: let Claude capture it from stdout, or use the Write tool.
- To post-process JSON: run jq as a separate bash call on a file written in a prior step.
- Reason: multi-command strings don't match the project's permission allow-list patterns
  and will trigger interactive permission prompts.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

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

- Check if the project has a `pnpm fix` script in `package.json`. If it exists, run it after every change and fix any reported issues before proceeding.
- When applying fixes (e.g. during code review), always prefer the solution with the least added complexity. Avoid over-engineering; a smaller, clearer change is better than a thorough but complex one.

### 10. GitHub

- When I ask you to respond on PR be transparent that the response is generated by you - Claude. At the start of the response add a prefix of style: '🤖 claude:'

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
