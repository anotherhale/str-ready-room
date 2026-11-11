# PREBRIEF — READY ROOM customer conversation

> **Status: DRAFT — human-owned.** This one-pager is a starting point for the
> Maverick conversation, not a finished artifact. It was drafted by an AI
> engineering agent (OpenHands) from the discovery notes and the built product.
> The reflection and framing below are **AI-generated** and must be reviewed,
> corrected, and re-voiced by a human before the meeting. Anything in
> *[square brackets]* is a prompt for that human author.

**Meeting:** STR Mission Applications — first-cut demonstration
**Product:** READY ROOM
**Audience:** Maverick, Navy aviation detachment officer

---

## 1. What we heard

- Responsibilities live across sticky notes, email flags, a whiteboard, and
  memory — there is no single place to look.
- He wants one place covering flying, administration, maintenance, logistics,
  and reminders. *Not* an aircraft-control system.
- Recurring obligations he named: a **Monday morning brief**, a **Friday status
  roll-up**, and **quarterly currency paperwork**.
- New work arrives through email and hallway conversations and is easily lost
  before it is written down.
- A flat list of hundreds of tasks is overwhelming; he dislikes notifications
  but does not want important work to go invisible.
- He framed the desired experience as *scanning aircraft instruments*: know what
  is now, what is next, and what might sneak up.
- He floated a printed daily index card or briefing.
- Day one is one operator; squadron collaboration and delegation come later.
- Visual polish is secondary to feeling in control.

## 2. What we built and why

**READY ROOM** is a single-operator operational scan, not a task dump.

- A **dashboard** ordered for the way he described scanning: greeting and date,
  a one-line readiness summary, compact counts, then **TODAY**, **WATCH**
  (labelled with the current window, e.g. *3-Day Watch*), and **ON THE HORIZON**.
- **Urgency is derived on read** — Overdue / Due today / Watch / On the Horizon —
  so overdue work never falls off the radar and completed work leaves the active
  sections. Every state carries a text label and a glyph, never colour alone.
- **Fast capture** on every view: type a title and press Enter; a full dialog
  (category, priority, due date, notes, recurrence) is one click away and is the
  *same* dialog used for editing.
- **Recurrence** preserves history: completing an occurrence keeps the completed
  record and generates exactly one successor, with no backfill of missed work.
- A **daily briefing** generated from real data, with a print stylesheet for the
  printed index card he described.
- A complete **inventory** (search / filter / sort) exists for completeness, but
  it is deliberately *not* the default view.
- **Settings** expose the warning window, timezone, categories, a recurrence
  overview, and a demo reset.

Why this shape: the customer's pain is *situational awareness under low
attention*, so the product optimises for a fast, glanceable scan and quiet
urgency rather than completeness or notification volume.

## 3. What we are guessing about

These are **assumptions to validate**, not confirmed requirements:

- The **default category set** (Flight Administration, Maintenance, Detachment
  Operations, Personnel, Logistics, General) is our invention and may not match
  how he actually files work.
- A **3-day default warning window** is a guess; the real answer depends on his
  planning rhythm.
- That a **single "urgency" ladder** (Overdue → Due → Watch → Horizon) matches
  how he prioritises, rather than, say, separating flying from admin.
- That the **"Monday brief / Friday roll-up / quarterly paperwork"** set is
  representative of his recurring load.
- That a **printed daily briefing** is genuinely useful versus a nice-to-have.
- That **categories** (not free-form tags or projects) are the right
  organisational axis.
- That **he wants no notifications at all**, versus a single daily digest.

## 4. What we want to validate with Maverick

1. **Does the scan match the instrument panel in his head?** Walk the dashboard
   and ask what is missing, mis-ordered, or noise.
2. **Category set** — do these six match his world? What would he rename, add,
   or delete?
3. **Warning window** — how far ahead does he actually want "Watch" to reach,
   and should it differ by category?
4. **Capture friction** — is title-only quick capture fast enough, and what does
   he wish were captured automatically?
5. **Recurrence realism** — do the seeded recurring items reflect his real
   obligations, and does "complete generates the next one" match his mental
   model?
6. **Briefing value** — would he print it, and what belongs on it?
7. **First real workflow** he would move off sticky notes on day one.

## 5. Where AI tooling helped

- Scaffolding the hexagonal backend (domain / application / adapters / API) and
  the React SPA quickly and consistently.
- Generating breadth of **tests** — urgency boundaries, month-end/leap-year
  recurrence arithmetic, idempotent completion, owner scoping, API contracts,
  and architecture boundary checks.
- Producing and keeping current the **documentation set** (README, DECISIONS,
  BUILD_STATUS) and the Docker runtime wiring.

## 6. Where engineering judgment overrode AI

- **Derived urgency in the domain, not the UI.** We kept urgency calculation
  pure and server-authoritative so the frontend cannot drift from the rules.
- **Recurrence as a chain of ordinary tasks** (shared `series_id`, no separate
  occurrence table) with **no backfill** and exactly-one-successor semantics —
  chosen deliberately over a more "complete" but heavier scheduler.
- **AuthN/AuthZ as real ports with a demo adapter**, rather than hardcoding a
  single-user shortcut, so a real identity provider attaches without touching
  the domain.
- **Persistence as a port** with SQLite as the first adapter — PostgreSQL is a
  configuration change, not a rewrite.
- **Scope discipline**: we did *not* build notifications, integrations, AI
  extraction, or server-side PDF, even though the architecture could host them.

---

*Reminder: this document is a draft for human review. Do not present the
reflection above as independently human-authored.*
