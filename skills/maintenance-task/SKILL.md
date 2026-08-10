---
name: maintenance-task
description: File a task in the Marinade Notion "General System Maintenance/Improvements" project — Backlog status, chalda as Assignee and Notify, severity mapped to Priority. Writes a skimmable why-first task body (Why / What / Intended fix / Reference) — two sentences of intent, then bullets — never a step-by-step implementation plan.
when_to_use: a defect, risk, or maintenance item found during work needs to be recorded as a Notion task rather than fixed now
argument-hint: "[low|medium|high|critical] <what the task is about>"
---

# Maintenance task → Notion

Create one task in the Tasks database under the General System
Maintenance/Improvements project.

## Fixed target

| | |
|---|---|
| Parent | `data_source_id: bd076786-8fe6-433e-b182-3fd194c74ffd` |
| Project page | `https://app.notion.com/p/32fe465715a4804eaa65fa60fb76be9d` |
| User (chalda) | `144e986a-db1a-4872-9b87-0efad80cd2e4` |

Use the `notion-create-pages` tool. Never write the page any other way.

## Severity

Parse a leading `low` / `medium` / `high` / `critical` token from the invocation.
Default is `high`. Everything after the token is the subject.

| Argument | `Priority` | Extra |
|---|---|---|
| `low` | `Low` | |
| `medium` | `Medium` | |
| `high` (default) | `High 🔥` | |
| `critical` | `High 🔥` | add `Emergency` to `Tags` |

`Priority` has exactly three options — `High 🔥`, `Medium`, `Low`. There is no
Critical option, so `critical` rides the top priority plus the `Emergency` tag.
The emoji in `High 🔥` is part of the value; omitting it fails the write.

## Properties

```
Name      <title>
Status    Backlog
Priority  <from the table above>
Assignee  144e986a-db1a-4872-9b87-0efad80cd2e4
Notify    ["144e986a-db1a-4872-9b87-0efad80cd2e4"]
Projects  ["https://app.notion.com/p/32fe465715a4804eaa65fa60fb76be9d"]
Tags      <what fits, e.g. Backend, Tech Debt, Infrastructure, Bug>
```

`Assignee` takes a single user ID; `Notify` takes an array. Do not set `Task ID`
— it auto-increments.

**Title:** imperative, specific, names the actual defect — not the area it lives in.
Good: `Fix fund_settlement underflow on deactivated stake with withdrawn lamports`.
Bad: `Improve settlement error handling`.

## Body

Exactly these four sections, in this order:

```markdown
## Why
## What
## Intended fix (direction, not prescription)
## Reference
```

A reader gets a few seconds. They must land on *Why*, understand the point, and
be able to stop there. Prose lives only in *Why*; everything below it is bullets.

- **Why** — the intent, as prose. Two sentences carry it: what is wrong or
  missing, then why it matters — the consequence of leaving it, blast radius, who
  gets paged, what stays broken or stranded. Add one or two more sentences on the
  goal (the end state the system should reach) only when the task has one that is
  not obvious from the first two. Four sentences is the ceiling; two is the norm.
  If a workaround already exists, say in half a sentence why it is not enough.
- **What** — 2–4 bullets, one sentence each. The defect and where it lives:
  real identifiers (file, instruction, build, epoch, address) and the trigger.
  State the mechanism once. Never walk through the code.
- **Intended fix** — 1–3 bullets, direction only. Name the *property the fix must
  achieve* and the constraint it must respect. No code, no file-by-file plan, no
  ordered steps.
- **Reference** — bullets of bare identifiers only. Build numbers, addresses,
  commits, URLs. No prose. Every entry must be openable by the Marinade
  audience — see *Links and attachments*.

Detail that does not fit these limits is not squeezed in. It goes into an
attached document (see *Links and attachments*) or it is dropped.

The shape to match:

```markdown
## Why
A single deactivated stake account makes `fund-settlement` underflow and abort
the whole batch, so payouts stall for every validator in the epoch. Funding
should be per-settlement independent — one bad source account skips, the run
continues.

## What
- `fund_settlement` subtracts withdrawn lamports without checking the source
  stake is still delegated
- Hit in epoch 918 by a stake deactivated between init and fund
- Retries pick the same account, so the batch never completes

## Intended fix
- Tolerate a non-delegated source account and skip it, leaving the remaining
  settlements in the batch fundable
- The skip must surface in the pipeline notification, not pass silently

## Reference
- https://buildkite.com/marinade/fund-settlements/builds/1234
```

## Links and attachments

The task is read by people who are not me, on machines that are not mine. Every
link must resolve for them.

**Link these** — anything visible org-wide or publicly: GitHub PRs, issues,
commits, blob/line links; Buildkite builds; other Notion pages; Slack
permalinks in the Marinade workspace; docs, dashboard and API URLs; on-chain
addresses and transaction signatures. Prefer these over any description of
where the evidence sits.

**Never link or name these** — a local filesystem path, a `$SAVE_PLAN_PATH`
document, a Dropbox or personal-drive path, a scratchpad file, a `localhost`
URL, or any repo the org cannot see. Not as a link, not as a bare filename, not
as "see my investigation notes". If that is the only place the evidence lives,
upload it or restate the finding inline instead.

**Uploading local investigation notes.** Their content is welcome; their
filename is useless to the reader. Never name a local file and stop there — that
is the failure this section exists to prevent. To include one:

1. `Read` the file.
2. Call `notion-create-attachment` with `filename` (keep the `.md` extension)
   and `content` set to the file's full text. The cap is 200 KiB after UTF-8
   encoding; above that, call `notion-create-file-upload`, POST the file to the
   returned `upload_url` with the returned `upload_headers`, then call
   `notion-create-attachment` with the resulting `source_file_id`.
3. Put the returned `markdown_source` on its own line in the `content` passed
   to `notion-create-pages`, at the end of `Reference`.

The page is still created by `notion-create-pages` — the attachment call only
prepares the file. Attached content does not count against the body word
budget, but strip anything not fit for a general audience (credentials, tokens,
absolute home paths, unrelated work) before uploading.

## Style rules

The task is informative about **why**, not **what**. A reader must finish it
knowing why it matters and roughly where to start — not how to write the patch.
Informative and really concise, both at once.

- Whole body under ~150 words. If it runs longer, cut from *Intended fix* first,
  then from *What*. Never cut *Why* to fit.
- One sentence per bullet, no terminal period. No sub-bullets, no bullet that
  grows into a paragraph.
- No code blocks. Inline identifiers in backticks are fine.
- No `Steps`, `Implementation plan`, `Acceptance criteria`, or `Testing` sections.
- Implementation detail belongs in an attached document, never in the body.
- Never restate what the code does. State the intent it violates.
- No hedging ("it might be worth considering") and no filler ("As you know").
- Write for a colleague who knows the system but not this bug.

## After creating

Print the created task URL and nothing else — no summary, no restatement of the
body.
