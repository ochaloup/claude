---
name: answer-existing-review
description: Answer the review comment threads on a PR from findings already triaged in this conversation — one reply per thread carrying its disposition (fixed / deferred / declined). Bot-authored threads are replied to and resolved in the same turn; human-authored threads get a reply only and stay open for the reviewer. A thread reply is the only thing it creates on GitHub — never a PR-level comment, a new thread, or a review; findings with no thread are folded into a related reply or reported in chat.
when_to_use: a review round has been decided — each finding is fixed, deferred, or declined — and the PR threads need answering. This is the posting step after pr-review, pr-review-followup, or code-review; it does not review anything itself. To raise new comments of your own on a PR, use post-review-comments instead.
argument-hint: "[<pr-url>|<pr-number>|<branch>]"
---

# Answer PR Review Threads

Arguments: $ARGUMENTS

GitHub token setup lives in `../pr-review/SETUP.md` — read it only if GitHub
access fails.

This skill only **answers threads that already exist**. Raising new comments of
your own on a PR is the `post-review-comments` skill.

This skill **posts**. It does not review, re-triage, or re-verify. The findings
and their dispositions already exist in the conversation; the job is to put each
one on the right thread, in the right form, and then close what may be closed.

"post", "comment", "reply", "resolve", "close" all mean **now, this turn**. Never
show a draft and wait for approval.

## 0. Preconditions

Refuse to run and say why if either is missing:

- **A PR** — from arguments, or from the conversation, or from the current branch.
- **Decided findings** — every item to be answered has a disposition: `fixed`,
  `deferred`, or `declined`. If some are still undecided, post the decided ones
  and list the undecided in the loose ends at step 8. Do not invent a decision.

Local git state is irrelevant here. Do not check whether work is committed or
pushed, do not mention it, do not wait for it. Pushing is the user's job, on
their own schedule. A fix that exists is reported as done.

## 1. Resolve the PR

Tokens in `$ARGUMENTS`, all optional: a PR URL, a bare PR number, or a branch
name. If none is given, take the PR from the conversation; if the conversation
has none, use the current branch.

```bash
~/.claude/scripts/git-pr-info.sh
```

Yields BRANCH, REMOTE, OWNER_REPO. Then, for a branch target:

```bash
gh pr list --repo OWNER_REPO --head TARGET --state open --json number,title,url,headRefName -L 1
```

If no open PR is found, abort with:
`No open PR found for branch '<TARGET>' in <OWNER_REPO>.`

Do not check out, fetch, or switch branches. This skill only talks to GitHub.

## 2. Fetch the threads

```bash
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 20) {
            nodes {
              id
              databaseId
              body
              path
              line
              author { login __typename }
              url
            }
          }
        }
      }
    }
  }
}
' -F owner=OWNER -F repo=REPO -F pr=PR_NUMBER
```

Write the result to a file and query it with `jq` in a separate call — one
command per bash invocation, no pipes.

Two fields matter per thread beyond the body:

- `id` (`PRRT_…`) — needed to resolve.
- `comments.nodes[0].databaseId` — the **numeric** id of the thread's first
  comment, needed to reply. The `PRRC_…` node id will not work with the REST
  reply endpoint. The numeric id is also the number in the comment URL
  (`#discussion_r3815629212`).

## 3. Map findings to threads

Match each decided finding to the thread it answers, by file + line + the
comment's content. One reply per thread — if two findings landed on one thread,
answer both in a single reply.

Three cases:

| case | action |
|---|---|
| finding has a thread | answer it (steps 4–6) |
| thread has no matching finding | leave it completely alone — no reply, no resolve |
| finding has no thread | never its own PR comment. Fold it into a related thread reply if one fits, otherwise chat only — step 7 |

That last row is the rule this skill exists to enforce, and it is about **where**
a finding may be posted, not whether it may be mentioned. A finding raised in a
review-body summary, a PR-level comment, an automated pre-merge check, or found
by your own reading has no thread of its own. It may still be *answered* — inside
an existing thread whose subject it genuinely belongs to, within the same 1–2
sentences — or *reported in chat*. What it must never do is become a new
standalone comment on the PR.

## 4. Classify each thread: human or automation

This decides whether the thread gets resolved, so get it right.

**Automation** if any of:

- `author.__typename == "Bot"`, or
- the login ends in `[bot]`, or
- the login is a known review bot: `coderabbitai`, `copilot-pull-request-reviewer`,
  `github-advanced-security`, `sonarcloud`, `codecov`, `sourcery-ai`,
  `deepsource-autofix`, `renovate`, `dependabot`, `greptile-apps`, `ellipsis-dev`.

Note that some review bots run as ordinary User accounts — `coderabbitai` has no
`[bot]` suffix and reports `__typename: "User"`. The login list is what catches
those, so check it, not just the typename.

**Human** otherwise. **When uncertain, treat it as human.** Wrongly resolving a
person's thread hides their feedback behind a collapsed conversation; wrongly
leaving a bot thread open costs nothing.

## 5. Compose the reply

Every reply, both kinds of author:

- Starts with the literal prefix `🤖 claude:` — the reader must know a machine
  wrote it.
- Is **1–2 sentences**. State the decision, plus the one reason that matters.
  Longer reasoning belongs in the chat, never on GitHub.
- Names no local repository state. No "not yet pushed", "uncommitted", "will
  push shortly", no branch mechanics. Write as if the change is already part of
  the PR, because from the reader's side it will be.
- Carries the decisive fact — the version, the function, the file, the number —
  not a vague "addressed".

Shape per disposition:

- **fixed** — what now holds, in the present tense.
  `🤖 claude: Fixed — the regenerated lockfile drops the override and carries the current versions, so a frozen install succeeds.`
- **deferred** — say it is deferred, why, and where it now lives.
  `🤖 claude: Deferred — the migration has to land as one unit with the lockfile refresh, tracked separately rather than widened here.`
- **declined** — say declining, and the one reason.
  `🤖 claude: Declining — this repo's CLAUDE.md bans /** */ blocks, so satisfying the threshold would violate its own documented convention.`

## 6. Post, then resolve

**Quote the body through a file, not the shell.** Reply text contains
apostrophes, backticks and em-dashes; a `-f body='…'` argument mangles them and
you will be patching a live comment afterwards. Write JSON with python, then:

```bash
python3 -c 'import json;open("/tmp/reply.json","w").write(json.dumps({"body":"🤖 claude: …"}))'
```

```bash
gh api repos/OWNER_REPO/pulls/PR_NUMBER/comments/<databaseId>/replies --input /tmp/reply.json
```

Then, **for automation threads only**, resolve in the same turn:

```bash
gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "PRRT_…"}) { thread { id isResolved } } }'
```

Resolve every automation thread you replied to, whatever the disposition —
fixed, deferred and declined alike. Resolving is idempotent, so a thread the bot
already closed is fine to resolve again.

**Deferred threads still get closed — but a closed thread is an invisible
thread.** A resolved conversation collapses out of the PR, so a `deferred` item
loses the only place it was visible. Do not skip the resolve. Do this instead,
both parts:

1. **The reply must name where the work now lives** — the tracker ticket, the
   spec file, the saved review document. This is required for `deferred`, not
   optional, because that sentence is the only durable trace left on GitHub once
   the thread collapses.
2. **Report it in chat**, in the `Deferred and closed` block at step 8. Whoever
   asked for the posting must see, in the same turn, which reminders just went
   invisible.

If a deferral has no durable home yet, say so plainly in that chat block and
offer to file one with the `maintenance-task` skill. Never let "the reply
mentioned it" stand as the record on its own.

**Never resolve a human's thread** unless the user asks for that thread by name.
The reviewer closes their own conversation once they are satisfied with the
reply.

Then verify:

```bash
gh api graphql -f query='query { repository(owner: "OWNER", name: "REPO") { pullRequest(number: PR_NUMBER) { reviewThreads(first: 100) { nodes { id isResolved } } } } }'
```

## 7. Never post at PR level

Do not use `gh pr comment`. Do not submit a review. Do not open a new thread. Do
not post a summary, a status update, a "here is what changed" recap, or a note
about something you noticed but nobody asked about. **A reply inside an existing
thread is the only thing this skill is allowed to create on GitHub.**

That is a constraint on the channel, not a gag order on the content. Something
with no thread of its own — an off-thread finding, a failing automated gate, a
declined item whose source was a PR-level comment, a fix nobody raised — has two
legitimate outlets:

1. **Inside a thread reply**, when an existing thread's subject genuinely covers
   it. Same 1–2 sentence budget; it earns its place only if the thread's reader
   needs it to make sense of the answer. Do not staple unrelated notes onto a
   thread just to get them onto the PR — that is the banned behaviour wearing a
   different hat.
2. **In the chat report**, under `Off-thread` in step 8.

When in doubt, chat. The user decides whether any of it ever reaches GitHub.

## 8. Report

After posting, print exactly one line per thread and nothing else. No re-summary
of the fixes — the reply already said it and the chat already knows.

```
<ID or thread ref> | <fixed|deferred|declined> | <reply URL>
```

Then these blocks, each only when it applies. `Deferred and closed` is **not**
optional — print it whenever at least one deferred thread was resolved, even if
the per-thread lines above already mention those threads. The duplication is the
point: a `deferred` line in a list of `fixed` lines does not register.

```
Deferred and closed (no longer visible on the PR):
- <finding> — now tracked in <ticket|spec|document>
- <finding> — NO durable home yet; file one?

Off-thread (not posted):
- <finding> — <why it has no thread> — <recommendation>

Loose ends:
- <item>
```

Loose ends never delay the posting. Post first, list after.

## Failure modes worth knowing

- **Numeric vs node id.** The REST reply endpoint needs `databaseId`; passing the
  `PRRC_…` node id fails. Read the number out of the comment URL if in doubt.
- **Shell quoting.** An apostrophe inside a single-quoted `-f body='…'` breaks
  the argument, and a workaround backtick renders as a literal backtick in the
  posted comment. Use `--input` with a JSON file, always.
- **A bot login without `[bot]`.** `coderabbitai` looks like a person to a
  typename check. Use the login list.
- **Already-resolved bot threads.** Still worth answering when the finding was
  decided in this conversation — the reply is the record of why. Re-resolve after.
- **Stale bot summaries.** A walkthrough or merge-risk block that no longer
  matches reality is not a thread and not yours to argue with. Note it in the
  chat report and move on.
