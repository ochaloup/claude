---
name: gen-task
description: Find the Notion GEN task linked to the current work and return its requirements as a fixed block — id, URL, title, status, numbered asks. Looks for the id in the argument, the conversation, the branch name, the PR title and body, or a notion.so link. Exact id match only, never a guessed task. Judges nothing; the caller decides what to do with the asks.
when_to_use: a skill or the user needs the requirements of the GEN task behind a branch or PR — code-review task conformance, implement context, pre-pr-design-pass contract. To create a new task use maintenance-task.
argument-hint: "[GEN-<n> | <notion.so url>]"
---

# GEN task lookup

Arguments: $ARGUMENTS

One plain command per bash call. No pipes, `;`, `&&`, redirects or `$(...)`.

## 1. Find the id

Take the first hit, in this order:

1. The argument — `GEN-<n>` or a `notion.so` link.
2. A `GEN-<n>` or `notion.so` link the user named in the conversation.
3. The branch name — `git branch --show-current`.
4. The PR — `gh pr view --json title,body`: title, then body, then a `notion.so`
   link in the body. No PR → skip this source silently.

Match the id case-insensitively, with or without brackets: `GEN-9202`, `gen-9202`,
`[GEN-9202]`. Normalise it to `GEN-<n>`.

Two different ids across the sources → stop and ask which one is meant.

## 2. Fetch the task

Load the tools with `ToolSearch` (`notion-search notion-fetch`).

- A `notion.so` link → `notion-fetch` it.
- An id → `notion-search` for `GEN-<n>`. Keep only the hit whose id property is
  exactly `GEN-<n>`, then `notion-fetch` it.

Notion unavailable, or no exact hit → return the no-task line. Never fall back to
the closest-looking task.

## 3. Extract the asks

From the page, list each requirement and acceptance criterion as a numbered item,
quoted or tightly paraphrased. A vague task gives a short list. Do not invent
criteria to fill it.

## Output

Exactly this block, and nothing else:

```
Task: GEN-<n> — <title>
URL: <notion url>
Status: <status>
Asks:
1. <ask>
2. <ask>
```

No task → exactly one line:

```
Task: none — <reason: no id found | Notion unavailable | no exact hit for GEN-<n>>
```
