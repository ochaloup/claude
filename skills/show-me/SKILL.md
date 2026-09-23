---
name: show-me
description: Draw a flow, a structure or a change as a plain-ASCII diagram in the terminal instead of describing it in prose. Draws a free-text topic, or with --base what a branch changed (added/removed/changed boxes marked). Every box names something real that was read; unverified parts are marked. Use when the user runs /show-me or says "show me", and as the embedded diagram step chained from the code-review skill.
when_to_use: the answer has a shape — a flow, a call chain, a before/after, a component layout — and prose would make the reader rebuild it in their head
argument-hint: "[<topic>] [--base <ref>] [--embedded]"
---

# Show Me

If the reader would have to read it twice, draw it once. The diagram lives in the
terminal as plain text: no browser, no HTML, no images.

## Inputs

- `<topic>` — what to draw, e.g. `the withdraw flow` or `how settle reaches the DB`.
- `--base <ref>` — draw what the branch changed against `<ref>`. If neither a topic nor
  `--base` is given, draw the branch against `main`, then `master`.
- `--embedded` — called from another skill: return only the diagram block, no preamble.

Every bash call is one plain command: no `$(...)`, no `&&`/`;` chains, no pipes, no
redirects.

## Pick one shape

Choose the one shape that carries the point. Never stack several.

- **Flow** — boxes and arrows, left to right or top down. Call chains, pipelines, jobs.
- **Sequence** — one column per actor, arrows between columns in time order. Requests
  crossing services.
- **Before / after** — two small panels side by side, or top and bottom. Merges, splits,
  re-routing.
- **Tree** — indented hierarchy. Module layout, config nesting, ownership.

## Drawing rules

- Plain ASCII only: `+ - | > < v ^ [ ]`. No box-drawing Unicode, no tabs — they misalign
  in PR comments and some fonts.
- At most 80 columns wide and about 20 lines tall. Too big means it shows too much:
  cut detail, do not shrink the font of the idea.
- Label each box with the real name: service, module, function or table.
- Label each arrow when it's not obvious what it carries (`HTTP`, `queue`, `SQL`).
- Wrap it in a ```` ```text ```` fence so it stays monospace.
- For a change diagram, mark every changed element and add a one-line legend beneath:
  `[+] added  [-] removed  [~] changed`. Unmarked boxes are unchanged context. Keep them
  to the minimum needed to place the change.

```text
 client --HTTP--> api --------> [~] vault --SQL--> postgres
                   |
                   +--HTTP--> [+] validator-bonds API
[+] added  [-] removed  [~] changed
```

## Do not guess

Draw only what you read. Every box and arrow must trace to code, config or a document
you opened in this session. If a piece could not be checked, draw it with a `?` suffix
(`bonds-api?`) and add `Not verified: <what is missing>` under the legend. Never draw a
component from its name alone.

## The one-sentence test

Before printing, ask: does the diagram show something the surrounding text does not?
A lone box, a straight line of two steps, or a rename says nothing a sentence can't.
Then skip it and print one line instead:

`Diagram: none — <reason, e.g. no structural change>.`

## Check before you print

Re-read the block line by line. Vertical connectors must sit in the same column on
every line. Arrows must meet the box they point to. No line may exceed 80 columns.
Fix it before showing it — a misaligned diagram misleads more than no diagram.

## Output

Standalone: one lead sentence saying what the diagram shows, then the block, then the
legend and any `Not verified` line. Nothing else.

`--embedded`: the block, legend and `Not verified` line only — or the `Diagram: none`
line.
