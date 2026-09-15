---
name: save-plan
description: Persist a plan, review, investigation, or implementation note as a canonical markdown document under $SAVE_PLAN_PATH, resolving the filename from repo/branch/content and merging any local draft files. Invoked directly as /save-plan, and by the code-review, pr-review, and pr-review-followup skills to write their reports.
when_to_use: any time a plan/review/investigation document must land in $SAVE_PLAN_PATH — never write those files directly
argument-hint: "[context]"
---

# Save Processing Data

## Purpose

Save processing artifacts (plans, reviews, implementation details, investigations) as markdown documents. These serve two audiences:

1. **Human review** — preserving reasoning, decisions, and context behind code changes, traceable alongside the branch.
2. **Claude Code continuation** — the document must be self-contained enough that a fresh session can load it, understand the full context, locate all relevant resources, and execute the plan without re-discovery. Write it as instructions to your future self.

This means: be explicit about file paths, endpoint signatures, data shapes, and decision rationale. Don't summarize — be precise. A reader with zero prior context should be able to pick up and implement from the document alone.

## Invocation
```
/save-plan [context]
```

**context** — optional positional argument, free-text. Lowercase, spaces/slashes replaced with `-`.

## Prerequisites
- `$SAVE_PLAN_PATH` set and pointing to an existing directory. Fail with clear error otherwise.
- A git repo is **preferred but not required**. The filename strategy adapts (see **Filename** below):
  - Inside a git repo on a feature branch → branch name drives the filename.
  - Inside a git repo on `main` / `master` (or detached HEAD) → derive a 3-4 word slug from the content instead.
  - Outside any git repo → derive a 3-4 word slug from the content instead.
  - Work spanning multiple repositories → drop DIR, let the slug carry repo hints.
  Do **not** ask the user for this slug — produce it from the conversation context.

## Path Resolution & Tool Choice (avoid permission prompts)

Never use `$SAVE_PLAN_PATH` (or any shell variable) directly in bash — quoted or unquoted. Claude Code's `simple_expansion` guard prompts for any `$VAR` use in bash regardless of allow-list rules.

Workflow:

1. Gather every environment fact in **one** bash call. Every extra call re-reads the whole session context, which is where a save's cost goes:
   ```
   python3 -c 'import os,subprocess,json,datetime,glob; g=lambda c:subprocess.run(c,capture_output=True,text=True).stdout.strip(); print(json.dumps({"save_plan_path":os.environ.get("SAVE_PLAN_PATH",""),"cwd":os.getcwd(),"in_git":g(["git","rev-parse","--is-inside-work-tree"]),"branch":g(["git","branch","--show-current"]),"generated":datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),"drafts":sorted(glob.glob("*.md"))}))'
   ```
   Permitted by the existing `Bash(python3 -c *)` allow rule and free of shell expansion. It answers **Filename**, **Mode detection**, the `Generated:` line and the draft scan at once — never re-run `pwd`, `git` or `date` separately.

2. Use the returned literal strings in every subsequent operation. Concatenate the filename in your head (or in your reasoning), not in the shell.

3. Prefer dedicated tools for file I/O — they take literal paths and never trigger expansion prompts:
   - **Read the draft files** named by the probe's `drafts`: `Read`, all in one message
   - **Read the destination only when merging chapters** into an existing multi-type file. A single-type save replaces it wholesale, and saved documents reach 700KB — reading one needlessly loads context that every later turn pays for.
   - **Write destination file**: `Write`

   Do not verify the result afterwards; `Write` fails loudly when it cannot write.

4. If bash is unavoidable, use the literal resolved path inline (e.g. `ls /home/user/plans/...`) — never `ls "$SAVE_PLAN_PATH"/...`.

## Filename

Pick exactly one of these forms based on the detected mode:

```
A. <DIR>--<BRANCH>--<TYPE>.md                       # git, feature branch
B. <DIR>--<BRANCH>--<CONTEXT>--<TYPE>.md            # git, feature branch, with CONTEXT
C. <DIR>--<SLUG>--<TYPE>.md                         # git on main/master, or no git
D. <DIR>--<SLUG>--<CONTEXT>--<TYPE>.md              # same as C, with CONTEXT
E. <SLUG>--<TYPE>.md                                # multi-repo work (DIR dropped)
F. <SLUG>--<CONTEXT>--<TYPE>.md                     # multi-repo, with CONTEXT
```

- **DIR**: basename of the probe's `cwd`. As-is casing. **Omit** when in multi-repo mode (E/F).
- **BRANCH** (forms A/B only): the probe's `branch`. As-is casing, `/` → `-`. If it is empty or equals `main` / `master`, do not use forms A/B — switch to the SLUG forms (C/D/E/F).
- **SLUG** (forms C/D/E/F): derive a **3-4 word kebab-case** identifier of what this document is about, directly from the conversation/content being saved. Lowercase, alphanumerics + `-` only. Do not ask the user. Examples: `jwt-refresh-flow`, `db-migration-rollback`, `oncall-paging-fix`.
  - For multi-repo (E/F), elaborate the slug so it conveys the multi-repo nature — include short repo identifiers or a `multi` hint, e.g. `auth-backend-frontend`, `multi-repo-deploy-rollout`.
- **CONTEXT**: from positional arg if provided. Lowercase, spaces/slashes replaced with `-`.
- **TYPE**: resolved from content, always UPPERCASE snake_case.

### Mode detection (decide once, up front)

Resolve in this order:

1. Is the work spanning **multiple repositories**? Judge from the conversation context — references to >1 distinct repo / project root, plans that touch separate codebases, or cross-repo analyses. If yes → **multi-repo mode** (E/F).
2. Read `in_git` and `branch` from the probe.
   - `in_git` is `true` AND `branch` is non-empty AND not `main` AND not `master` → **feature-branch mode** (A/B).
   - Anything else (no git, detached HEAD, `main`, `master`) → **slug mode** (C/D).

**Examples:**
```
backend--feature-add-auth--PLAN.md                       # A
backend--feature-add-auth--login-flow--REVIEW.md         # B
backend--jwt-refresh-flow--PLAN.md                       # C (on main, no useful branch)
api-server--db-migration-rollback--INVESTIGATION.md      # C (no git repo here)
backend--memory-leak-probe--phase-2--INVESTIGATION.md    # D (slug + CONTEXT)
auth-backend-frontend--token-refresh-rollout--PLAN.md    # E (multi-repo)
multi-repo-deploy-rollout--q2-launch--PLAN.md            # F (multi-repo + CONTEXT)
```

## Document Structure

Every document **must** start with a `Generated:` timestamp line directly under
the title, followed by a **Sources** section before any content. Use the probe's
`generated` value, refreshed on every save. If the incoming content already carries its own timestamp
line (e.g. `Reviewed: ...` from a review skill), keep that line in the body —
the `Generated:` line reflects when the file was last written.

```markdown
# feature-add-auth: Plan

Generated: 2026-06-04 14:32 CEST

## Sources
- **Endpoints**: `POST /api/auth/login`, `GET /api/users/me`
- **Database**: `users` table, `sessions` table
- **Files reviewed**: `src/auth/handler.rs`, `src/middleware/jwt.rs`
- **External resources**: RFC 7519 (JWT), internal auth design doc
- **APIs/Services**: Redis session store, OAuth2 provider

## PLAN
...content...
```

The Sources section must list all resources, inputs, and references used to produce the analysis. This includes but is not limited to: endpoints, database tables/queries, files read or reviewed, external documentation, APIs, services, config files, logs. Omit categories that don't apply — but at least one source must be listed.

## Type Resolution

Single type when possible:

- `PLAN` — architecture, task breakdowns, approach rationale
- `REVIEW` — code review notes, feedback, change requests
- `IMPLEMENTATION_DETAIL` — coding decisions, edge cases, specifics
- `INVESTIGATION` — spikes, research, debugging analysis
- *Fallback*: infer reasonable uppercase snake_case name

Multiple types only when content genuinely spans them. Combine names (`PLAN_REVIEW`), structure with `## CHAPTERS` after the Sources section.

## Draft files in the current directory

The probe's `drafts` already lists every `*.md` in the current working directory. Select the entries whose names end in the resolved TYPE — e.g. `PLAN.md`, `REVIEW.md`, `*-PLAN.md`, `*-REVIEW.md`, or any `*<TYPE>.md` pattern. Do not re-scan the directory.

For each match:
1. Read its content and fold it into the document you are about to save (Sources, body, chapters), applying the rules in **Merge Strategy** below.
2. After the destination file has been written successfully, delete the draft from the current directory.

Rationale: these are working notes the user accumulated while preparing the document. The goal is to consolidate them into the canonical file under `$SAVE_PLAN_PATH` and leave the working tree clean.

## Merge Strategy

**Single-type file:** replace entire content.

**Multi-type file (chapters):**
- Existing chapter + new content → replace chapter
- Existing chapter + no new content → leave untouched
- New chapter not in file → append
- **Sources section**: always merged — new sources are added, existing ones preserved

## After Saving

Once the file has been written successfully, print its full absolute path as the
final line of output (the same literal path passed to the `Write` tool — no shell
expansion, no `~`, no relative form). This is the only required confirmation; do
not also paste back the file contents or a summary.
