---
name: review-lesson
description: Propose at most three review lessons from the review round in this conversation — a defect a later fix PR exposed (--retro), findings an earlier round missed — as detailed checks of what to look at more closely, ask the user which to keep, and append only the ticked lines to the code-review skill's lessons files. Never proposes skip lines, never writes a line the user did not approve, never commits.
when_to_use: at the end of a review round — code-review-marinade-all calls it after --first and --followup — or by hand when a review missed something; to run a review use code-review
argument-hint: "[<pr-url>] [--retro <prior-pr-url>] [<free-text lesson>]"
---

# Review lesson

Arguments: $ARGUMENTS

Lessons are one-line checks that `code-review` reads on every run. Each one costs
tokens on every review, so a line earns its place only if it will fire again. This
skill proposes; the user decides.

Lessons only ever add checks — what to look at more closely. Never propose a `skip:`
line: whether a point is a defect depends on the repo and the situation.

Every bash call is one plain command: no pipes, `;`, `&&`, redirects or `$(...)`.

## 1. Resolve the files

- Lessons dir: `lessons/` in the `code-review` skill's directory, next to this one.
  Resolve its absolute path.
- Repo owner and name: from the PR URL in the arguments or the conversation, else
  from `git remote -v`.
- Read each file that exists: `_global.txt`, `marinade.txt` when the owner is
  `marinade-finance`, `<repo>.txt`.

## 2. Collect candidates

Take them from these sources, in this order:

1. **Free text** in the arguments — the user's own lesson.
2. **`--retro <prior-pr-url>`** — the current PR fixes code that a PR the user
   reviewed earlier touched. Read the prior PR's saved review under `$SAVE_PLAN_PATH`
   (finding headings only) and this PR's diff. Decide: which defect this PR fixes,
   whether it was inside the prior diff or one step from it, and whether the prior
   review had a finding for it. A miss becomes a candidate: the check that would
   have caught it. Name the defect class too (e.g. memory exhaustion from an
   unbounded read), so the check also catches its siblings, not only this instance.
3. **Earlier-round misses** — findings in this conversation marked `pre-existing`
   by pr-review-followup.

Declined or dropped findings are never candidates.

## 3. Filter

Drop a candidate when:

- an existing lesson line or a `code-review` objective or targeted check already
  covers it — the review applied a known check badly, which is not a new lesson;
  say that in one line instead;
- it is a one-off fact no future diff would trigger;
- it restates a lint rule or a style preference.

Keep at most three, the most likely to fire again first.

## 4. Write each line

- **Scope.** `_global.txt` when it holds for any repo, `marinade.txt` when it is a
  Marinade convention, `<repo>.txt` when it names this repo's facts.
- **Shape.** The trigger, then the check in detail, then the source:
  `<when a diff …>, <what to trace or measure, and what proves it safe> (<PR URL>)`.
  One line, under 300 characters. Generic enough to fire again, concrete enough to
  act on. Example: `When a diff reads a request/response body or file, find where its
  size is bounded before it is buffered; unbounded → flag memory exhaustion, and ask
  for a test far over the bound that asserts peak memory (<PR URL>)`.

## 5. Ask

No candidate survived → print `No lesson candidates this round.` and stop. Do not ask.

Otherwise one `AskUserQuestion`, `multiSelect: true`. One option per candidate:
label is a short name, description is the full line and its target file. Wait.

## 6. Append

For each ticked option, append its line to the end of its target file; create the
file when it does not exist. Never touch a line that is already there.

A file past 40 lines does not grow. Show the user its lines with the new one and
propose which to merge or drop; write only what they approve.

Report one line per appended lesson: `<file> — <line>`. Nothing ticked →
`No lessons added.` Never commit.
