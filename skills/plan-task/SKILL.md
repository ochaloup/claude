---
name: plan-task
description: Plan a task before any code is written. Researches the codebase through cheap delegated agents, derives one approach and says why it beat the alternatives, breaks it into verifiable steps, and ends with the open questions and doubts that must be answered first. Saves the plan through the save-plan skill. Runs on Fable — the plan is made once and read many times, so the reasoning is worth the credits. Writes no code.
when_to_use: a task is defined and needs a design before implementation starts; re-invoke with `finalize` once the open questions have been answered. To persist an already-finished plan use save-plan; to review code that exists use code-review.
argument-hint: "[<what the task is>] | finalize"
model: fable
disallowed-tools: ["Edit", "NotebookEdit"]
---

# Plan a task

Arguments: $ARGUMENTS

Produce the plan that implementation will follow, and the list of things that must
be settled before it starts. Implementation happens in a later session, on a
cheaper model, from the saved document alone.

**Write no code.** No edits, no scaffolding, no "example implementation" that is
really the change. Code snippets belong in the plan only where a signature or a
data shape is the decision being made.

## Cost discipline — read this first

This skill runs on Fable, which bills from a separate credit pool. What justifies
that is judgment, not reading. Every token of raw grep output or file dump you
pull into this context is paid for at the premium rate and adds nothing a cheap
model could not have found.

So: **you do not explore. Agents explore for you.**

- Every `Agent` call in this skill passes `model: "sonnet"` explicitly. Subagents
  inherit the parent model, so omitting it runs the exploration on Fable. That is
  the single most expensive mistake available here.
- At most 4 agents in parallel.
- Read a file yourself only when an agent's answer left a specific decision
  genuinely unsettled, and then only the part that settles it.
- Never read a file to confirm something an agent already quoted.

## Stage detection

- Argument is `finalize` → **Stage 2**.
- Anything else → **Stage 1**, and the argument is the task.

If Stage 1 runs with no argument, take the task from the conversation. If the
conversation does not carry one either, ask what the task is and stop.

## Stage 1 — Research

Name the decisions the plan has to make, then send one agent per decision. Not one
agent per file, not one agent per directory — per open decision.

```
Agent({ subagent_type: "Explore",
        model: "sonnet",
        description: "<the decision>",
        prompt: "<what to find, and what makes an answer complete>" })
```

Ask each agent for what the codebase *does today*: the existing mechanism, its call
sites, its idioms, the constraints it already enforces. Ask for quoted `file:line`
evidence, not summaries. An agent that returns prose you cannot check has told you
nothing you can plan on.

Ask a second round only when the first changed what the decisions are.

## Stage 1 — The plan

Derive the approach from what came back. One approach, chosen — not a menu.

Constraints that are not negotiable while planning:

- Reuse over addition. If the base already offers the mechanism, the plan uses it.
- One mechanism per concept. Two ways to do the same thing is a defect in the plan.
- The smallest change that solves the stated problem. Nothing speculative, no
  configurability nobody asked for.
- Every step ends in something checkable. "Add validation" is not a step;
  "tests for invalid input fail, then pass" is.

## Stage 1 — Open questions

This is the part the plan exists for. The common failure is to pick one reading of
an ambiguous requirement, plan around it, and never say so. Do not do that.

A question earns its place only if **the plan changes depending on the answer.**
Say what it changes.

Each one takes this shape:

```
Q3. Does a partial fill keep its original order id, or get a new one?
    Assumed: original id kept.
    If instead a new id — step 4 needs an id-mapping table and step 6's
    idempotency key changes. Roughly two extra steps.
    Blocking: yes.
```

- **Assumed** — what the plan currently does. Never leave this blank; a question
  with no working assumption means the plan stops there instead.
- **If instead** — the concrete consequence for the plan. Name the steps.
- **Blocking** — yes if implementation cannot correctly start without it. No if the
  plan holds either way and the answer only refines a detail.

Do not ask what the code answers — go find out. Do not ask style preferences. Do
not ask anything with an obvious default. Every such question spends the user's
attention, which is scarcer than the credits.

If nothing is genuinely open, say so in one line. A fabricated question is worse
than none.

Deliver them as a numbered list in chat. Never `AskUserQuestion` — a design doubt
rarely reduces to four discrete options, and the number is what the answer and the
document refer back to.

## Stage 2 — Finalize

The answers are in the conversation. For each question:

1. Record the answer against its number.
2. Change the plan to match. An answer that contradicted the assumption means
   steps get rewritten — do it, do not append a note beside the stale step.
3. If an answer opens a new question, ask it. Do not resolve a plan around a
   second-order doubt you invented an assumption for.

The plan is ready only when every blocking question is answered. Say which ones
were left open and non-blocking.

## Document

Both stages save through the `save-plan` skill. Never write the file directly.

Body, in this order:

```
Status: OPEN — 3 questions unresolved (2 blocking)

## Goal
<the task, in the user's own terms, plus what "done" means>

## Approach
<the design, and the one reason it beat the alternatives>

## Rejected
- <alternative> — <why not>, one line each

## Steps
1. <step> → verify: <check>

## Open questions
<the numbered list, in the shape above>

## Resolutions          # stage 2 only
Q3 — <answer>. Changed: steps 4 and 6 rewritten.
```

Stage 2 replaces `Status:` with `Status: RESOLVED — ready to implement`, and moves
answered questions into Resolutions.

The reader is a fresh session with zero context. Absolute paths, real signatures,
real data shapes. Do not summarise what implementation will need to know.

## Output

1. The approach, in four or five sentences. What changes, and why this way.
2. The saved document's absolute path, on its own line.
3. The open questions, numbered, in full — last, and nothing after them.

Stage 2 replaces item 3 with one line: what is now settled, what was left open and
non-blocking, and that implementation can start.

Do not summarise the steps in chat. They are in the document, and repeating them
here is what makes this turn expensive for nothing.
