---
name: read-context
description: Load the saved context of the current branch — the $K knowledgebase docs (plans, reviews, investigations), the GEN task, the repo docs and Claude memory that touch the branch — then verify the codebase against it. Maps plan steps and review findings to commits, checks each claimed fix in the code, and runs fmt/lint/tests. Read-only; ends with a layered status report.
when_to_use: resuming work on a branch — "read the context", "where are we on this branch", "verify the state of the codebase".
argument-hint: "[GEN-<n> | context words]"
---

# Read branch context and verify the code

Arguments: $ARGUMENTS

Read-only. No edits, no commits, no PR comments, no `/save-plan` unless asked.
One plain command per bash call. Never write `$K` or any `$VAR` in bash — resolve it with
`printenv K` and use the literal path.

## 1. Probe

Run in parallel:

- `printenv K` — the knowledgebase dir. Empty → stop, report it as a blocker.
- `git branch --show-current`
- `git status --short`
- `git log --oneline main..HEAD` (use `master` if `main` does not exist).

## 2. Find the context docs

Docs are named `<repo-dir>--<branch>--[<context>--]<TYPE>.md`, with `/` in the branch
turned into `-`. Match on the filename, not the content — grepping content for the repo name
returns hundreds of unrelated files.

- `find <K> -maxdepth 1 -name "*--<branch>--*"`
- No hit → `grep -rlF <branch> <K> --include=*.md`, then try the PR number (`pr-<n>`).
- `ls -lt` the hits, then read them all in one message, newest first.
- A doc's Sources may name other docs as context. Read those too, one hop only.

From the docs, collect:

- Plan: goal, "done means", steps, status, out-of-scope items.
- Decisions: user decisions, rejected options, standing decisions (`D<n>`) — never re-raise these.
- Review findings (`R<round>#<n>`) with their proposed fixes, and open questions.

The newest doc can predate the newest commits. The code wins over the doc.

## 3. Repo docs and memory

Read only what touches this branch. A repo-wide read floods the context.

- **Repo docs.** `git diff --name-only <base>..HEAD` gives the touched paths. Read the `.md` files
  the branch changed, and the `README.md`, `ARCHITECTURE.md` or `docs/` page nearest to each
  touched directory. A nested `CLAUDE.md` in a touched directory counts too; the root one is
  already loaded. Collect invariants, conventions and the documented commands for fmt, lint and
  test — step 5 uses them over the defaults.
- **Memory.** The memory index (`MEMORY.md`) is already in context. Open the entries whose
  description names this repo, branch, GEN task or topic, from the memory dir your system prompt
  names. Never guess that path. Memory is a past snapshot: verify every file, function or flag it
  names before relying on it.

A repo doc or memory that contradicts the code is stale. Report it as a finding; do not fix it.

## 4. GEN task

Invoke the `gen-task` skill, passing an id when the argument, a doc or the PR title names one.
It returns an exact match or a no-task line. One GEN id can be an umbrella shared by many
unrelated tasks; if no task fits this work, say so in one line and move on.

## 5. Verify the code

1. Start the checks in the background first, so they run while you read. Write a script to the
   scratchpad and run `bash <script>` with `run_in_background`. Print a marker after each
   step so the result is easy to grep:
   - Rust: `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
     `cargo test` (use the packages the plan's "done means" names).
   - TypeScript: `pnpm lint` (not `pnpm fix` — this skill is read-only), then `pnpm test`.
   When it completes, grep the output file for the markers, `test result`, `FAILED` and `error`.
2. Map each plan step and each review finding to a commit. Commit messages often name them.
3. For each claimed fix, read the diff (`git show <sha> -- <paths>`) and the current code at the
   cited location. Check that it does what the doc proposed.
4. Check that every test named in the plan or review exists (grep its name).
5. Check that a test isolates the branch it claims to cover. Example: failing an RPC method that
   several reads share passes for the wrong reason as soon as the read order changes.

## 6. Report

Follow the layered reply format from CLAUDE.md:

1. One bold sentence: is the branch in the state the docs promise, and what is still open.
2. Bullets:
   - the docs read, by filename — `$K` docs, repo docs and memory entries;
   - stale repo docs or memory, with the code that contradicts them;
   - the GEN task line;
   - plan steps: done or missing, with the commit;
   - findings: fixed, open or declined, with `file:line`;
   - check results with pass/fail counts.
3. Open items that need a user decision, each with the options the docs give.

End with a **Blockers** list (missing `$K`, Notion unavailable, a failed check), or omit it.
