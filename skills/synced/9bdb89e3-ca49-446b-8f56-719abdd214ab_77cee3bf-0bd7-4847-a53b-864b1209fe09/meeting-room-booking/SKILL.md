---
name: meeting-room-booking
description: Book meeting rooms at the Corso-1 office for Marinade team meetings. Use this skill whenever the user asks to book a room, find a room, reserve a meeting room, or when checking calendar events that might need a physical room. Also trigger when the user mentions room names like Netherlands, Brazil, Mexico, Japan, Sweden, Greenland, Finland, Greece, Tech-Talk, or any Corso-1 room. Trigger even if the user just says "book a room" or "which room should I use" without specifying details.
---

# Meeting Room Booking — Corso-1 Office

This skill helps book the right meeting room at the Corso-1 office (Prague) for Marinade team meetings. The goal is to be efficient with room sizing — always match room capacity to actual number of attendees. Don't book a 12-person room for a 3-person meeting.

## Room Inventory

All rooms are at Corso-1, Prague. Calendar IDs are Google resource calendars.

### Favorite Rooms (in preference order)

1. **Netherlands (2 people)** — Closest room. Has whiteboard. Compact, ideal for 1-on-1s and 2-person meetings.
   - Calendar ID: `miton.cz_34393433353937393433@resource.calendar.google.com`

2. **Brazil (8 people)** — Very close. Screen + speakers (good quality), whiteboard. Airy and spacious. Great all-around room.
   - Calendar ID: `miton.cz_3636323935383234363938@resource.calendar.google.com`

3. **Mexico (6 people)** — Close. Screen + speakers (bad quality). Airy. Good mid-size room despite mediocre AV.
   - Calendar ID: `c_188bnkod74hlkha1jasbjnpbdp4a6@resource.calendar.google.com`

### Other Available Rooms

4. **Japan (12 people)** — Best overall room. Screen + speakers, whiteboard. Airy. However, because it seats 12, only use it when the meeting genuinely needs the capacity (roughly 7+ people). Don't waste it on small meetings.
   - Calendar ID: `miton.cz_3338393230333636343935@resource.calendar.google.com`

5. **Sweden (14 people)** — Screen + speakers. Airy. Large room. Between Sweden and Japan, Japan wins easily — prefer Japan when capacity fits. Same rule: only use for larger meetings.
   - Calendar ID: `miton.cz_3831333238383739373830@resource.calendar.google.com`

6. **Greece (6 people)** — Screen + speakers, whiteboard. Airy. Decent option.
   - Calendar ID: `miton.cz_3131373138363133333534@resource.calendar.google.com`

7. **Finland (6 people)** — Screen + speakers (bad quality), whiteboard. Not airy. AV equipment is poor.
   - Calendar ID: `miton.cz_38303431343633353834@resource.calendar.google.com`

8. **Greenland (6 people)** — Screen + speakers. Not airy. Not a good meeting room overall — use only when better options are unavailable.
   - Calendar ID: `miton.cz_188a9lpmvroicj86ksiivquss9qo6@resource.calendar.google.com`

### Rooms to Avoid

9. **Czech Republic (2 people)** — Far from the Marinade office, but acceptable for private 1-on-1 conversations when privacy matters more than convenience.
   - Calendar ID: `miton.cz_36333637363436383231@resource.calendar.google.com`

10. **Slovakia (2 people)** — Far from the Marinade office, but acceptable for private 1-on-1 conversations.
    - Calendar ID: `miton.cz_3536383437373932323232@resource.calendar.google.com`

11. **Turkey (4 people)** — Really far from the Marinade office. Avoid.
    - Calendar ID: `miton.cz_3436303830333833363934@resource.calendar.google.com`

12. **Ukraine (2 people)** — Really far from the Marinade office. Avoid.
    - Calendar ID: `c_18875nmilnbc4gl7hb8gahhpk98ru@resource.calendar.google.com`

13. **France (4 people)** — Really far from the Marinade office. Avoid.
    - Calendar ID: `c_223eeeedbdd0ac1eb7e5c1a6201897b1af10d9a99497af775c3d9d029f6ed34d@group.calendar.google.com`

14. **Tech-Talk (50 people)** — Part of the open space. Requires preparation (enclosing the area, setting up). Avoid unless the meeting truly needs the capacity (12+ people where Japan/Sweden won't cut it). Not a ready-to-use meeting room.
    - Calendar ID: `miton.cz_35373734373239373631@resource.calendar.google.com`

## Room Features Quick Reference

| Feature | Rooms |
|---------|-------|
| Screen + speakers (good) | Brazil, Greenland, Japan, Sweden, Greece |
| Screen + speakers (bad) | Mexico, Finland |
| Whiteboard | Brazil, Greece, Japan, Finland, Netherlands |
| Airy / spacious | Brazil, Mexico, Greece, Japan, Sweden, Tech-Talk |
| Close to office | Netherlands, Brazil, Mexico |
| Good for private 1-on-1s (far) | Czech Republic, Slovakia |

## Booking Process

Follow this process every time:

### 1. Understand the meeting
- How many attendees?
- Does it need AV (screen/speakers)? E.g., for video calls or presentations.
- Does it need a whiteboard?
- Is privacy important?
- What time slot?

### 2. Check room availability FIRST — STRICT ZERO OVERLAP
Always check availability before recommending or booking. Query the room's resource calendar using `gcal_list_events` for the meeting time window. Never assume a room is free.

**Critical: There must be absolutely ZERO overlap between the requested time slot and any existing event on the room's calendar.** Even a 1-minute overlap means the room is unavailable. For example, if you want to book 9:00–10:00 and the room has an event from 9:55–10:15, that room is **not available** — do not attempt to book it.

**Back-to-back is OK.** If an existing event ends exactly when the requested slot starts (or vice versa), that is NOT an overlap. Example: existing event ends at 13:00, new meeting starts at 13:00 → the room IS available. The rule is strictly: a room is unavailable only when an existing event's start is **before** (strictly `<`) the requested end AND the existing event's end is **after** (strictly `>`) the requested start.

When checking availability, query for events that overlap with the full requested window. Widen the query window slightly (e.g., ±15 minutes) to catch edge cases, but when evaluating results, apply the strict overlap rule above — boundary-touching events do not conflict.

### 3. Present at least 2 options when possible
When there are multiple available rooms, always present at least two choices:
- One **minimal / right-sized** option (capacity close to attendee count)
- One **airy / spacious** option (for a more comfortable experience)

Include a brief note on why each fits (or doesn't perfectly fit) the meeting.

### 4. Identify the user ("me")
Before creating or updating any event, always determine the user's email address. Use the user's profile information available in the Claude conversation context (e.g., their account email). This email is needed to:
- Add the user as an attendee
- Set the user's RSVP status to "accepted"

Never ask the user for their email if it can be resolved from their profile. If it truly cannot be found, then ask.

### 5. Book the chosen room
Update or create the event with ALL of the following:
- Add the room as an attendee (using the resource calendar email) and set the location.
- **Always invite the user ("me")** as an attendee. The user who is scheduling the meeting must always be included as an attendee on the event, even if they didn't explicitly say so.
- **Always accept on behalf of the user.** Set the user's response status to "accepted" so the event shows as confirmed on their calendar. Use `responseStatus: "accepted"` for the user's attendee entry.
- **Always add a Google Meet conference link.** When creating or updating the event, set `conferenceData` with `createRequest` (type `hangoutsMeet`) and use `conferenceDataVersion: 1`. This reliably generates a Google Meet link on the event. Every meeting gets a Meet link, no exceptions.

## Room Selection Logic

Given the number of attendees, here's the recommended search order:

**2 people:** Netherlands → Czech Republic/Slovakia (if private) → Mexico or Brazil (if others taken)

**3-4 people:** Mexico → Greece → Finland → Greenland (as fallback)

**5-6 people:** Mexico → Greece → Brazil → Finland → Greenland

**7-8 people:** Brazil → Japan (if nothing smaller available)

**9-12 people:** Japan → Sweden

**13-14 people:** Sweden → Japan (as backup)

**15+ people:** Tech-Talk (with advance notice about setup needed)

Always be efficient: if a 2-person meeting needs a room and Netherlands is taken, prefer Czech Republic or Slovakia over grabbing an 8-person room. Only "size up" when right-sized rooms are all booked.

## Important Notes

- Always use `Europe/Prague` timezone for queries
- When updating events to add rooms, preserve existing attendees and add the room resource email
- Use `sendUpdates: "none"` by default when adding rooms to avoid spamming attendees, unless the user asks otherwise
- **Always resolve the user's email from their profile** at the start of any booking flow. Do not skip this step.
- **Always add the user as an attendee** and set their `responseStatus` to `"accepted"` — they are the organizer/scheduler and should always appear as attending.
- **Always include `conferenceDataVersion: 1`** and a `createRequest` in `conferenceData` to generate a Google Meet link on every event. Never create a meeting without a conference link.
