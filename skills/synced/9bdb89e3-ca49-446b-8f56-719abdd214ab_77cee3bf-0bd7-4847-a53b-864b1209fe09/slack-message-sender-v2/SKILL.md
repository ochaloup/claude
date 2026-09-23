---
name: slack-message-sender-v2
description: >
  Compose and send Slack messages that follow Marinade's official Slack Guide format
  (situational awareness prefixes, RACI tagging, thread-first structure).
  Use this skill whenever the user asks to send, post, draft, or compose a Slack message,
  notify someone on Slack, ping a channel, post an update, share info on Slack,
  send a KUDOS, escalate something, or coordinate via Slack.
  Also trigger when the user says things like "tell the team", "let X know",
  "post this to #channel", "message X about Y", "slack X about Y",
  or any variant where the intent is to produce a Slack message.
  Even if the user doesn't mention "Slack" explicitly, trigger this skill when
  the context implies a Slack message is the right delivery mechanism
  (e.g., after completing a task the user said they'd report on).
---

# Slack Message Sender v2

Send Slack messages formatted according to Marinade's Slack Guide — including channel selection, full RACI tagging, initial message, and thread body.

---

## Core Message Format

Every top-level Slack message MUST follow this structure:

```
`PREFIX` - Short description, max ~10 words @responsible cc: @consulted @informed
```

**Rules:**
- The PREFIX is wrapped in backticks: `` `PREFIX` ``
- Description after the dash is concise — aim for one line, two max
- @-mentions go at the END of the initial message line, never in the middle
- @responsible (who must act) comes first, then `cc:` for consulted/informed
- One message = one purpose. Never combine multiple asks.
- **Always use `<@USER_ID>` format** — never plain names, never `#username`
- **All messages are in English** — regardless of what language the user writes in. Only deviate if the user explicitly requests another language.

---

## Prefixes

| Prefix | Use when... |
|---|---|
| `ACTION` | Assigning a task or deliverable |
| `CHANGE` | Updating a prior decision |
| `COORD` | Coordinating across teams |
| `DECISION` | Something requires final approval |
| `INFO` | Sharing information, no action needed |
| `QUESTION` | Asking for a clear answer |
| `REQUEST` | Requesting a resource or approval |
| `KUDOS` | Recognizing someone's work |

Infer the prefix when not specified:
- "let them know" / "FYI" / "sharing" → `INFO`
- "can you ask" / "find out" → `QUESTION`
- "please do" / "make sure" / "need X to" → `ACTION`
- "great job" / "thanks to" / "shoutout" → `KUDOS`
- "we decided" / "changing" → `CHANGE`
- "need approval" / "sign off" → `DECISION`
- "need access" / "can I get" → `REQUEST`
- "sync with" / "align on" → `COORD`

---

## Channel Directory

**Do not search for channels at runtime.** Use this directory. Channels are stable — this list is current as of April 2026. Skip `ext-*`, `feed-*`, and `com-*` prefixes (external/automated).

### Team channels
| Channel | Purpose |
|---|---|
| #general | Company-wide announcements only. No work discussions. |
| #random | Non-work chat, jokes, GIFs. No work topics. |
| #kudos | Recognizing someone's work — KUDOS messages only |
| #team-engineering | Engineering team — broad eng topics |
| #team-backend | Backend-specific discussions |
| #team-frontend | Frontend-specific discussions |
| #team-engineering-standup | Engineering standups |
| #team-engineering-til | "Today I learned" — eng knowledge sharing |
| #team-product | Product discussions and feedback on existing features |
| #team-product-design | Product design topics |
| #team-product-insights | Customer insights, feature requests |
| #team-marketing | Marketing team — general |
| #team-marketing-data | Data and analytics for marketing |
| #team-marketing-social | Social media |
| #team-marketing-webflow | Webflow / web topics |
| #marketing-content-review | Content review |
| #marketing-performance | Marketing performance |
| #marketing-signals | Marketing signals |
| #marketing-strategy | Marketing strategy |
| #team-operations | Operations & HR |
| #team-partnerships | Partnerships team |
| #team-partnerships-events | Events planning |
| #team-partnerships-support | Partner support |
| #team-legal | Legal matters |
| #team-revops | Revenue operations |
| #team-customer-support | Customer support |

### Project channels
| Channel | Purpose |
|---|---|
| #project-apy-boost | APY Boost project |
| #project-rewards-history | Reporting and Staking Rewards feature |
| #project-policies-review | Policies review project |
| #project-msol-upgrade | mSOL upgrade project |
| #project-recipes-repay | Recipes repay project |
| #project-knowledge-vault | Knowledge vault project |
| #project-mobile-app | Mobile app project |
| #project-platform-bootstrap | Platform bootstrap |

### Admin channels
| Channel | Purpose |
|---|---|
| #admin-intel | Intelligence / strategic info sharing |
| #admin-access-requests | Access, license upgrades, budget approvals — use forms in tabs |
| #admin-accounting | Accounting |
| #admin-dao-governance | DAO governance |
| #admin-dao-info | DAO info |

**Channel selection logic:**
1. If the topic is project-specific → use the `#project-*` channel
2. If the topic is team-specific → use the `#team-*` channel
3. If cross-team or strategic → use `#admin-intel` or relevant team channels
4. KUDOS always go to `#kudos`
5. Never post work discussions in `#general` or `#random`
6. Never post to `ext-*` channels (Slack Connect — API cannot post there)

---

## RACI Tagging

Map people to roles:
- **@responsible** — the person who must execute. Mentioned directly, no `cc:` prefix.
- **cc: @consulted** — people providing input.
- **cc: @informed** — people who should be aware.

**Critical:** Always resolve names to Slack user IDs using `slack_search_users`. In the composed message, always use `<@USER_ID>` — never plain text names, never `#name`.

**Keep cc: minimal.** Only tag people with a direct, concrete connection to the topic — someone who owns a dependency, needs to act on the outcome, or would be blocked without knowing. Do not tag leadership (CEO, heads of teams) by default just because they're senior or loosely related. If in doubt, leave them out and let the user add cc's manually.

---

## Quick Status Emojis

These are the standard reaction emojis used across Marinade (including Slack Connect channels):

| Emoji | Meaning |
|---|---|
| ✅ | Reviewed or Complete |
| 👀 | Being Reviewed / In Progress |
| ❌ | No / Blocked |

When composing messages that invite a status update, mention these reactions as the expected response mechanism (e.g., "React ✅ when done or ❌ if blocked").

---

## Urgency and Escalation

When a message is time-sensitive, include a short urgency note in the thread body:

> "Urgent — decision required to avoid delaying launch"

For escalations: the correct channel is a **DM forward** (Hover → *Forward message* → Select recipient), not re-posting in multiple channels.

Deadlines should always include timezone: **"EOD CET"** or **"EOD EST"**. When posting meeting times, include both: e.g., *"15:00 CET / 9:00 EST"*.

---

## Team @-Groups

Instead of `@channel` or `@here`, use team group mentions:

- `@frontend-team`, `@backend-team`, `@marketing-team`, etc.
- Format: `@{name}-team`

These are managed by team leaders and should be preferred for team-wide pings. Never use `@everyone`.

---

## Workflow — Step by Step

### Step 1: Gather intent

From the user's request, determine:
1. **Topic & purpose** — what is this message about?
2. **Prefix** — infer from the table above
3. **Channel** — select from the Channel Directory above; if genuinely ambiguous, pick the best fit and note your reasoning
4. **People** — who is responsible, who should be cc'd?

### Step 2: Resolve user IDs and channel owner

For every person mentioned, use `slack_search_users` to get their `<@USER_ID>` **and display name**. Store both — you'll need them for the preview. Do this **before** composing any message. Never guess user IDs. Never use `#` instead of `@`.

If the user hasn't specified who to tag as @responsible, check the target channel's topic — it lists the channel owner (e.g., *"Q4 2025 project - owned by @vu"*). Use `slack_read_channel` with `limit=1` to fetch the topic, then propose the owner as the default @responsible. Confirm with the user if unsure.

### Step 3: Compose the initial message

Format:
```
`PREFIX` - Short actionable summary <@U_RESPONSIBLE> cc: <@U_CONSULTED> <@U_INFORMED>
```

Keep the headline to ~10 words. The detail goes in the thread (Step 4).

### Step 4: Compose the thread body

**Always prepare a thread reply** unless the user's message is trivially simple (e.g., a one-line KUDOS). The thread is where context lives — the headline just routes attention.

Thread body should include:
- Full explanation of the situation or ask
- Relevant links (Notion pages, Google Docs, GitHub PRs, dashboards)
- Deadline or urgency if applicable — always specify **"EOD CET"** or **"EOD EST"**, never just "EOD"
- Any necessary background for the @responsible person
- Next steps or expected output
- If the message is time-sensitive, add: *"Urgent — [reason]"* at the top of the thread

Format the thread body in clean Slack markdown (bullet points, bold for emphasis, links as `<URL|label>`).

**Long thread rule:** If the user is summarizing a concluded discussion or huddle, the thread body should be a clean summary posted back to the channel. Flag this to the user if it seems like the message is a wrap-up of a longer conversation.

### Step 5: Present for review — text first

**Never call `slack_send_message_draft` before showing the full message in text.** The draft tool interrupts the flow and prevents the thread body from being composed properly.

Instead, present both parts as a formatted preview in chat. Show **two versions** of the initial message — one for copy-pasting, one for sending via API:

---
**Channel:** #channel-name

**📋 Copy-paste version** (works when pasting directly into Slack):
> `` `PREFIX` - Short actionable summary @DisplayName cc: @DisplayName2 ``

**🤖 API version** (used when sending as draft via Claude):
> `` `PREFIX` - Short actionable summary <@USER_ID> cc: <@USER_ID2> ``

**Thread reply:**
> Full thread body here, with links, context, deadlines, next steps.
---

The copy-paste version uses `@DisplayName` (the Slack display name resolved via `slack_search_users`). The API version uses `<@USER_ID>`. Both tag the same people — just different formats for different use cases.

After showing the preview, ask: *"Looks good? I'll prepare it as a draft for you to send, or you can copy-paste the text version directly into Slack."*

### Step 6: Prepare draft on confirmation

Only after the user confirms (e.g., "yes", "looks good", "send it") — call `slack_send_message_draft` with the initial message.

Then offer to send the thread reply once the main message is live: use `slack_send_message` with `thread_ts`.

---

## Real Examples from the Workspace

### ACTION — assigning a task
```
`ACTION` - Finalize project plan for Growth Engine Pebble Project by EOD <@U088ZAKP7NE> cc: <@U076P380PLY> <@U094L8Z3L13>
```
*Thread:* Context on what "finalize" means, link to the doc, expected output format, deadline.

### COORD — cross-team alignment
```
`COORD` - Wallet management (on/off ramp, social login, extension UX) <@U08D49URAKD> cc: <@U0AADCTHTAL>
```
*Thread:* Background on why this needs coordination, what decisions are open, what input is needed from each person.

### INFO — sharing without action required
```
`INFO` - Select APY endpoint understates staker returns by ~30bps — fix PR linked <@U0844V6V7RT> cc: <@U076P380PLY>
```
*Thread:* Link to the PR, brief explanation of the bug, impact, timeline for fix.

### QUESTION — seeking a clear answer
```
`QUESTION` - How do I request new deployment key for marinade-notifications? <@U084LFDP9GR>
```
*Thread:* More context on why the key is needed, what was already tried, any urgency.

### KUDOS — recognizing work
```
`KUDOS` - Great work getting the Zodia migration ready ahead of deadline <@U084LFDP9GR> cc: <@U08131G4UCV>
```
*Thread* (optional): More detail on what specifically was impressive, impact on the team/project.

### DECISION — requesting approval
```
`DECISION` - Approve new vendor contract for infra tooling by Friday <@U076P380PLY> cc: <@U08SMNFPPHT> <@U09D7ASR3T6>
```
*Thread:* Link to contract, summary of key terms, why this deadline, alternatives considered.

### COORD + ACTION — combined (use sparingly)
```
`COORD` & `ACTION` - Status Check & Next Steps - Rain Partnership <@U076P37LJJU> <@U09D7ASR3T6> <@U08SMNFPPHT> cc: <@U076P380PLY>
```
*Thread:* Detailed status, what decisions are needed, who owns what next.

---

## Edge Cases

- **Multiple channels**: Post to each separately. Never cross-post by tagging @channel.
- **@here / @channel**: Only for: network/staking/validator incidents, compliance/security matters, urgent institutional communications. Never without explicit user request.
- **ext- channels**: Refuse. API cannot post to Slack Connect channels.
- **#general**: Announcements only. If not an announcement, redirect to appropriate channel.
- **#random**: Non-work only. Redirect work topics.
- **Scheduling**: If the user wants to post at a specific time (e.g., during CET business hours), use `slack_schedule_message`. Convert to Unix timestamp. Always confirm the time in **both CET and EST** (e.g., "Scheduled for 15:00 CET / 9:00 EST").
- **No channel match found**: If none of the channels in the directory fit, note this to the user and suggest `#admin-intel` or `#team-operations` as fallbacks, or ask the user.

---

## Quick Reference — Tools

| Need | Tool |
|---|---|
| Resolve a person's user ID | `slack_search_users` |
| Send draft for review | `slack_send_message_draft` |
| Send message directly | `slack_send_message` |
| Reply in thread | `slack_send_message` with `thread_ts` |
| Schedule for later | `slack_schedule_message` |

**Do NOT use `slack_search_channels` at runtime** — the Channel Directory above is authoritative and saves unnecessary API calls.
