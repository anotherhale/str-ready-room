# READY ROOM — Demonstration Script

A spoken walkthrough for the Maverick demo. Roughly **15 minutes** at a
comfortable pace; timings are a guide, not a rule. Every step below has been
exercised against the running application.

> **Prep (do this before the meeting).**
> 1. `docker compose up --build` and wait for all four containers to report
>    `healthy` (`docker compose ps`).
> 2. Open <http://localhost:8080>. The first load seeds the demo scenario.
> 3. Optional clean slate: click **Settings → Reset demo data** so the numbers
>    match this script exactly.
> 4. Have a browser zoom you are comfortable with; the briefing step uses
>    **Ctrl/Cmd-P**.

Everything shown is synthetic demonstration data. No real unit, person, or
operation is represented.

---

## 0. The one-sentence frame (before you click anything)

> "You told us you are not looking for another task list. You want the feeling
> you get scanning the instruments — what is now, what is next, and what might
> sneak up. READY ROOM is that scan. Everything else is a drill-down."

Then open the app.

---

## 1. Dashboard — the operational scan (≈4 min)

**Do:** Land on **Dashboard** (the default view).

**Point at, top to bottom:**

- **"Good morning/afternoon/evening, Maverick."** — *"The greeting and the date
  come from your timezone, not a hardcoded string. Change your timezone in
  Settings and this follows."*
- **The readiness line** — *"Operational picture: 1 overdue, 1 due today, 3 on
  watch, 4 on the horizon. One sentence, the whole day."*
- **The five count tiles** — Overdue · Due today · Watch · Horizon · Done this
  week. *"These are the buckets. Nothing else competes for your attention up
  here."*
- **TODAY** — the overdue training records (marked ▲ Overdue) and the
  maintenance sign-off (◆ Due today).
- **3-DAY WATCH** — *"Notice the section names itself after your warning window.
  Today it says 3-Day Watch; widen the window to 7 days and the label and the
  contents change with it."*
- **ON THE HORIZON** — the quarterly currency paperwork, next week's admin, and
  the logistics count ~3 weeks out.

**Say:** *"Overdue work never falls off. It stays at the top until you deal with
it — the failure mode you described is important things going invisible, and we
deliberately did not build that."*

**Point at one card's meta line:** urgency badge **and** the words, a category
pill, a priority pill, the due date, "in N days", and a **↻** for recurrence.

**Say:** *"Every urgency state has a glyph and a word, never colour alone — so it
reads the same for everyone."*

---

## 2. Fast capture — recording it before it is forgotten (≈2 min)

**Do:** In the **quick-capture bar** under the header, type a real one — e.g.
`Call the squadron about the Friday roll-up` — then hit **Enter**.

**Say:** *"This bar is on every page. A responsibility goes in as fast as you can
type it; category, due date, and priority are pre-filled so you can accept the
defaults and move on."*

**Then:** Press **+ New** (or **Open full inventory → + New**). Show the **full
dialog** — Title, Category, Priority, Due date, Notes, and the **Recurrence**
block (frequency, interval, weekday, ends never/after/on a date).

**Say:** *"Same dialog for creating and editing. Anything you can set on day one
— notes, priority, recurrence — you can change later."*

Close without saving (Cancel) unless you want the extra item.

---

## 3. Making urgency move — it is derived, not typed (≈1.5 min)

**Do:** Edit the quick-captured task (or any task): click **Edit**, set the
**due date to today**, save.

**Say:** *"I did not set a priority to 'urgent'. Urgency is computed on read from
the due date and today's date. Move the date and the badge moves — it can never
drift out of sync with the calendar."*

**Do (optional flourish):** Set the due date to **yesterday**, save, and show it
promote into **TODAY** as ▲ Overdue. Then set it back or complete it.

---

## 4. Completing a recurring responsibility — history kept, next one born (≈3 min)

**Do:** Find **"Publish Friday status roll-up"** (weekly, in the Watch section).
Click **Complete**.

**Say:** *"That is the recurring obligation you named. Watch what happens: the
completed occurrence is kept as history, and exactly one successor is created —
next Friday — automatically."*

**Do:** Go to **Inventory**, set **Status = All**, and search `roll-up`.

**Point at:** the completed occurrence **and** the new open occurrence, each
showing **Occurrence 1 / Occurrence 2**.

**Say:** *"No manual re-entry, no duplicate successors. Completing an
already-completed task changes nothing — it is idempotent — so a double-click or
a flaky connection cannot spawn a second one."*

**Do:** On the completed occurrence, click **Reopen** to show it returns to the
active set.

**Say:** *"And it is always the same series — editing the rule later updates the
existing series instead of quietly starting a new one."*

---

## 5. Work arriving — email and calendar (≈3 min)

**Say:** *"Most of your work does not start in this app. It arrives — an email, a
meeting on the calendar. So we connected both, on by default."*

**Do:** Click **Demo arrivals** in the header.

**Point at:** the confirmation toast — *"Demo arrivals — 1 new message, 1 new
event."*

**Do:** Open the **Mailbox** tab.

- *"Read-only on purpose: list, read, capture. No send, no delete — we are not
  trying to replace your mail client."*
- Click the newest message (**"Urgent: discrepancy write-up needs a
  signature"**) to read it.
- Click **Capture**.

**Say:** *"That turns the message into a responsibility. It keeps a link back to
the message and marks it so it cannot be captured twice."*

**Do:** Open the **Calendar** tab. Show today's events and the new
**"Unscheduled maintenance stand-up"** event that just arrived. Click **Capture**
on one event.

**Say:** *"Same idea — the meeting becomes a responsibility with the date carried
over. There is a Sync button too, and the app keeps its own cache so the calendar
view is fast and does not depend on the external server being up."*

---

## 6. The inventory — completeness on demand, not by default (≈1.5 min)

**Do:** Open **Inventory**.

**Point at:** **Search**, **Status** (All / Open / Completed), **Category**
filter, the **Active** and **Completed** sections, and the **+ New** button.

**Say:** *"This is every responsibility, with search and filters. It is a
secondary view on purpose — the dashboard is the product. You come here when you
want to reconcile, not to start your day."*

**Do:** Delete a throwaway task to show **Delete** is explicit and separate from
completing.

**Say:** *"Delete is a deliberate act. You never delete something to get it off
the board — you complete it, and the history stays."*

---

## 7. The daily briefing — the index card you asked for (≈2 min)

**Do:** Open **Briefing**.

**Point at:** the date, the **look-ahead sentence**, then **Overdue**, **Today**,
**Upcoming deadlines**, and **Recurring obligations**.

**Say:** *"This is generated from the same data — not a second list you maintain.
It is the printed index card you described."*

**Do:** Click **Print briefing**. Show the print preview — chrome, navigation,
and buttons drop away; only the briefing prints.

**Say:** *"Browser print, so it works anywhere. We deliberately did not build a
server-side PDF generator for this first cut."*

Cancel the print dialog.

---

## 8. Settings — it adapts to your detachment (≈1.5 min)

**Do:** Open **Settings**.

- **Warning window (days)** — *"This is the Watch window. Change 3 → 7, save, and
  the dashboard's 'Watch' section relabels and re-buckets."* (Change it, then
  change it back, or leave it and note the dashboard change.)
- **Operator timezone** — *"Everything — today, the greeting, overdue — is
  resolved in your zone, and it handles the UTC-midnight edge correctly."*
- **Categories** — show the six defaults (Flight Administration, Maintenance,
  Detachment Operations, Personnel, Logistics, General). *"These are our guess
  at your vocabulary — rename, add, or remove them; it is your list."* Add one
  (e.g. `Safety`) to show it is operator-editable and persisted.
- **Recurrence overview** — the table of rules: name, cadence, occurrences
  generated, next occurrence, active state.
- **Demonstration data** — **Simulate arrival** and **Reset demo data**.

**Say:** *"Reset clears everything and puts the demo scenario back, so you can
show this to the next person without a clean database."*

---

## 9. Close (≈1 min)

**Say:**

> "Three questions, answered in one glance: what needs me now, what is next, and
> what might sneak up. Fast capture so nothing is lost. Recurrence that keeps its
> history and refills itself. Email and calendar feeding it instead of competing
> with it. And a printed briefing for the ready room wall.
>
> What we are *guessing* at — and want your reaction to — is the buckets and the
> warning window. If three days is wrong for your detachment, that is a setting,
> not a rebuild."

---

## Appendix A — Feature checklist (every feature, with where to see it)

| # | Feature | Where | What proves it |
|---|---|---|---|
| 1 | Operational dashboard (scan) | Dashboard | Readiness line + five counts |
| 2 | Local-time greeting + date | Dashboard header | Follows the operator timezone |
| 3 | Derived urgency (6 states) | Any task card | Badge moves when the due date moves |
| 4 | Text + glyph, never colour alone | Any task card | ▲ Overdue, ◆ Due today, ◐ Watch, ◇ On the Horizon, ○ Normal, ✔ Completed |
| 5 | Today / Watch / Horizon sections | Dashboard | Watch label shows the window ("3-Day Watch") |
| 6 | Overdue never disappears | Dashboard TODAY | The overdue item stays until completed |
| 7 | Quick capture on every view | Bar under the header | Type + Enter |
| 8 | Shared create/edit dialog | + New / Edit | Same dialog for create and edit |
| 9 | Notes, priority, due date | Full dialog | All editable after creation |
| 10 | Categories (configurable) | Settings → Categories | Add/rename/remove, persisted |
| 11 | Complete (idempotent) | Task card → Complete | Completing twice changes nothing |
| 12 | Reopen | Inventory → Reopen | Clears completion, returns to active |
| 13 | Explicit delete | Inventory → Delete | Separate from completion |
| 14 | Recurrence (daily→yearly) | Full dialog | Frequency, interval, weekday |
| 15 | Recurrence end conditions | Full dialog | Never / after N / on a date |
| 16 | Recurrence preview | Full dialog | Upcoming dates before saving |
| 17 | Successor generation | Complete a recurring task | Exactly one successor, occurrence +1 |
| 18 | Series history preserved | Inventory (Status = All) | Completed occurrence kept |
| 19 | Recurrence overview | Settings | Cadence, generated, next, state |
| 20 | Complete inventory | Inventory | Search + status + category filters |
| 21 | Daily briefing | Briefing | From persisted data |
| 22 | Print stylesheet + Print action | Briefing → Print briefing | Chrome hidden in print |
| 23 | Warning window (configurable) | Settings | Relabels and re-buckets Watch |
| 24 | Operator timezone | Settings | Drives today/greeting/overdue |
| 25 | Demo reset | Settings / `POST /api/demo/reset` | Restores the scenario |
| 26 | Incoming email (capture) | Mailbox | Read-only list/read/capture |
| 27 | Calendar (cache + capture) | Calendar | Sync, capture, create event |
| 28 | Live arrival injection | Header **Demo arrivals** | One email + one event on demand |
| 29 | No login, single operator | Whole app | Opens straight to the dashboard |

## Appendix B — Under the hood (only if asked)

- **Architecture:** domain-driven, ports-and-adapters. Business rules (urgency,
  recurrence, authorization) live in a pure domain core; the API, database, and
  frontend are replaceable adapters.
- **Identity vs. authorization:** they are separate. A single-user provider
  answers *who is acting*; a permission policy answers *what they may do*. No
  login is shown because the demo has one operator — the seams for a real
  provider are already there.
- **Persistence:** a port with a SQLAlchemy adapter on SQLite. PostgreSQL is a
  configuration change, not a rewrite.
- **Timezone:** datetimes stored in UTC; "today" resolved in the operator's zone.

## Appendix C — Recovery / troubleshooting

- **Empty or odd numbers:** Settings → **Reset demo data**.
- **Calendar or Mailbox says "unavailable":** the demo servers are still
  starting — wait ~15s and press **Sync**. They start automatically with the
  stack.
- **Full reset from scratch:** `docker compose down -v && docker compose up --build`.
- **Demo arrivals delivered nothing:** an integration is off or unreachable; the
  toast says which one. The rest of the app is unaffected by design.
