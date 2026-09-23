---
name: perform-security-system-compliance-control
description: Guide a user through performing a security, system, or compliance control — from identifying the control, creating a log entry in Notion, walking through the checklist, documenting results, and marking the control as done.
---

# Skill: Performing a Security/System/Compliance Control via Notion MCP

## System Architecture

The control system lives under the page **🚓 Security/System/Compliance controls** (`158e465715a480cc812fc56fa8f1da90`) and consists of three interconnected databases:

| Database | Data Source ID | Purpose |
|---|---|---|
| **Security/System/Compliance controls** | `e3f3940a-2e41-4c63-b768-a9b2c8f6a3a9` | Defines each control activity (what to do, how often, who owns it) |
| **Control Logs** | `1b066ddc-068e-4f9a-86b0-185250911860` | Individual execution records — one row per control performed |
| **Controls List** | `1a8e4657-15a4-80a8-8f69-000b2c905ed4` | Reference catalog of formal control IDs and categories |

### Relationships

```
Controls List (formal IDs)
  ↕ "Covered Controls" / "Covered By"
Security/System/Compliance controls (activities)
  ↕ "Security&Compliance controls log" / "Security&Compliance controls"
Control Logs (execution records)
```

## Control Log Schema

When creating a Control Log entry in the **Control Logs** database (`collection://1b066ddc-068e-4f9a-86b0-185250911860`):

| Property | Type | Description |
|---|---|---|
| `Name` | title | Format: `@ControlPage @DateTime` (use mention-page + mention-date) |
| `Author` | person | **Required.** The user performing the control. Look up via `notion-get-users` (use `user_id: "self"` to get the current user). |
| `Status` | select | `In Progress` initially, `Done` when complete |
| `Security&Compliance controls` | relation (limit 1) | URL of the parent control page |

## Step-by-Step Procedure

### Step 1: Identify the control to perform

Fetch the controls database or ask the user which control needs to be performed. Each control has:
- **Name** — what the control is
- **Frequency [days]** — how often it must be performed
- **Owner** — who is responsible
- **Next Control Date** — when it's next due (formula)
- **Area ID** — the compliance area

### Step 2: Read the control page for its template

Fetch the specific control page (e.g., `158e465715a480498dcadcd5ab91e28a` for "Patch management - Review CVEs in ECR images"). The page body contains:
1. **Control Description** — what to review and where
2. A **template section** below the `---` dividers that contains:
   - A **Control check-list** with the steps to follow
   - A **Control results** section for documenting findings

Extract the template content (everything below "Control log template follows 👇").

### Step 3: Look up the current user

Use `notion-get-users` with `user_id: "self"` to get the current user's ID. This is needed for the `Author` field.

### Step 4: Create a new Control Log entry

Use `notion-create-pages` with:
- **parent**: `{ "data_source_id": "1b066ddc-068e-4f9a-86b0-185250911860" }`
- **properties**:
  - `"Name"`: A descriptive title (the UI button uses `@ControlPage @Date` format, but a plain text title works too)
  - `"Status"`: `"In Progress"`
  - `"Security&Compliance controls"`: `"https://www.notion.so/<control_page_id>"`
  - `"Author"`: The current user's Notion user ID (from Step 3)
- **content**: The template copied from the control page (the checklist + results sections)

**Note:** Do NOT include a date heading in the content — the `Created time` property on the log entry already captures when the control was performed.

### Step 5: Perform the control

Walk through each checklist item with the user:
- Help them review the relevant systems/reports
- Document findings in the "Control results" section
- Update checklist items to `[x]` as they're completed

### Step 6: Update the log with results

Use `notion-update-page` to:
1. Replace the content with completed checklist and documented results
2. Set `"Status"` to `"Done"` once all items are checked off

## Example: Performing "Patch management - Review CVEs in ECR images"

```
Control page: 158e465715a480498dcadcd5ab91e28a
Frequency: 90 days
Area: 09 - Security
Owner: user://6acee21b-da5f-4543-ba60-858d10b8318e

Template content to copy into new log:
---
## Control check-list
- [ ] Review AWS Inspector's reports
- [ ] Prepare tasks for fixes (if applicable)
- [ ] Review AWS inspector reports after issues are fixed (if applicable)

## Control results
- …
---

Steps:
1. Review https://eu-central-1.console.aws.amazon.com/inspector/v2/home?region=eu-central-1#/findings/repository
2. Identify critical/high CVEs in ECR images
3. Create tasks for fixes if needed
4. After fixes, re-check Inspector
5. Document findings with screenshots in "Control results"
6. Mark status as Done
```

## Important Notes

- Always check the specific control's template — each control has its own checklist and procedure.
- The `Name` property in the UI is auto-generated with mentions, but for MCP creation a plain-text title is acceptable.
- Evidence (screenshots) cannot be uploaded via MCP — instruct the user to attach them manually in Notion.
- The `Status` and `Next Control Date` on the parent control are **formulas** that auto-compute from the linked logs — no need to update them manually.
