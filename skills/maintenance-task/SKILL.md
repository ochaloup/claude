---
name: maintenance-task
description: File a task in the Marinade Notion "General System Maintenance/Improvements" project — Backlog status, chalda as Assignee and Notify, severity mapped to Priority. Writes a short why-first task body (Context / Why it matters / Intended fix / Reference), never a step-by-step implementation plan.
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
## Context
## Why it matters
## Intended fix (direction, not prescription)
## Reference
```

- **Context** — one short paragraph. What broke or what is wrong, and where.
  Name the concrete trigger and the real identifiers (file, instruction, build,
  epoch, address). State the mechanism once; do not walk through the code.
- **Why it matters** — one short paragraph. The consequence of leaving it. This
  is the section that justifies someone's time: blast radius, who gets paged,
  what stays broken or stranded. If a workaround already exists, say why it is
  not enough.
- **Intended fix** — 2–4 sentences, direction only. Name the *property the fix
  must achieve* and the constraint it must respect. No code, no file-by-file
  plan, no ordered steps.
- **Reference** — bullets of bare identifiers only. Build numbers, addresses,
  commits, URLs. No prose.

## Style rules

The task is informative about **why**, not **what**. A reader must finish it
knowing why it matters and roughly where to start — not how to write the patch.

- Whole body under ~250 words. If it runs longer, cut from *Intended fix* first.
- No code blocks. Inline identifiers in backticks are fine.
- No `Steps`, `Implementation plan`, `Acceptance criteria`, or `Testing` sections.
- No bullet lists in Context or Why it matters — prose paragraphs.
- Never restate what the code does. State the intent it violates.
- No hedging ("it might be worth considering") and no filler ("As you know").
- Write for a colleague who knows the system but not this bug.

## After creating

Print the created task URL and nothing else — no summary, no restatement of the
body.
