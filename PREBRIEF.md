# STR MISSION APPLICATIONS - READY ROOM

## 1. What we heard

- Maverick is overwhelmed with trying to track tasks
- Trying to track them with sticky notes, email, whiteboard, and memory
- Tasks are forgotten or overlooked when not captured
- He dislikes notifications but doesn't want important things to fall off the page
- Want to know what is due now, what is next, and what is on the horizon
- Suggested index card or daily brief of the day
- Start with single operator with plans for squadron
- Wants to feel in control over having something shiny and sleek.

## 2. What we built and why

- Dashboard that is easily scannable (like an instrument panel)
  - One line readiness summary
  - Compact count of 'Overdue', 'Due today', 'Watch', 'On the Horizon', 'Done this week' buckets
  - Tasks organized by bucket with category, priority and due date visible
- Fast capture available on every page
- Support for recurring tasks (Monday morning detachment brief)
- Daily Briefing
- Complete inventory of all tasks with support for filter, search, sort (Not the default view)
- Settings - modify warning window, timezone, categories, recurrence overview, demo reset

## 3. What we are guessing about

- The default categories (Flight Adminstration, Maintenance, Detachment Operations, etc)
- 3-Day default watch window
- The buckets for urgency (Overdue, Due today, Watch, On the Horizon) match his priorities
- That printed daily briefing is useful versus a nice to have
- That he wants no notifications at all

## 4. What we want to validate with Maverick

- Does the operational scan match the instrument panel in his head?
- How far ahead does he actually want "Watch" to reach?
  - Should it differ by category?
  - Are some categories more important?
- For the Quick Capture feature which category and priority should be defaul?
- Do the prepopulated reccurence match his everyday obligations?
- Does completing reccuring task match his work flow?
- Does this workflow match his reality? Would you move off sticky notes and whiteboard?
- Does the Briefing bring value? Would you print it?
- Would you use the calendar and email integration?

## 5. Where AI tooling helped

I used AI extensively throughout the development of READY ROOM, primarily through OpenHands
as an autonomous software engineering agent, with ChatGPT assisting in product definition,
architectural planning, and development direction.

Rather than using AI simply to generate isolated code snippets, I used an agent-driven
development workflow. I established the product objectives, translated the discovery notes
into functional requirements, defined architectural constraints, and delegated implementation
tasks to OpenHands.

Development was iterative. I asked ChatGPT to create an implementation plan for OpenHands,
incorporating my requirements, constraints, and engineering guardrails, including Hexagonal
Architecture, Domain-Driven Design (DDD), and KISS principles. I reviewed the plan, made
adjustments, and then provided OpenHands with the implementation instructions.

I used ChatGPT as a thought partner to explore design alternatives, challenge assumptions,
refine requirements, and evaluate architectural tradeoffs. OpenHands served as the primary
implementation agent, working across the frontend, backend, persistence, integrations,
automated testing, Docker configuration, and documentation.

I gave OpenHands implementation objectives and milestones, allowing it to work autonomously
while reviewing its progress and results. The workflow involved having the agent inspect the
codebase, implement functionality, execute tests, diagnose failures, and make corrections.
I provided additional direction when implementation decisions, scope, or complexity needed
adjustment.

I treated AI-generated implementation as work that required engineering review and independent
verification. I used automated tests, clean-slate Docker deployment, persistence checks, and
end-to-end acceptance testing to validate the results rather than relying on successful code
generation as evidence of correctness.

## 6. Where engineering judgment overrode AI

AI was an implementation accelerator, not the authority on architectural or product decisions.
I retained ownership of the architecture, technical tradeoffs, scope, and acceptance criteria.

I established Hexagonal Architecture, Domain-Driven Design, and KISS as implementation
guardrails. Rather than hardcoding a single-user shortcut, I required authentication and
authorization boundaries that would allow a real identity provider to be attached without
restructuring the application domain.

Similarly, I required persistence to be isolated behind an abstraction, with SQLite as the
initial adapter. This kept the domain independent of the database implementation and provided
a path to introduce PostgreSQL without rewriting the application.

Scope management was another deliberate engineering decision. I initially directed OpenHands
to focus on the core READY ROOM experience rather than expand the assignment into an over-
engineered production system. I deliberately deferred email and calendar integrations during
the initial prototype, which I completed in approximately one hour.

After testing the prototype, working through defects, and evaluating the remaining time, I
decided to expand the demonstration. I wanted to show that the architecture could support
genuine integrations, not just theoretical extension points or mocked services.

I directed OpenHands to implement actual CalDAV and IMAP integrations, using ports and
adapters to isolate protocol-specific implementation details. I also required the calendar
service and demonstration mailbox to be deployed as part of the Docker Compose project so
the experience would be self-contained and reproducible.

The distinction was intentional: deliver the essential product first, then use the remaining
time to demonstrate extensibility and real-world integration capabilities without sacrificing
simplicity.

Ultimately, AI performed a substantial portion of the implementation, but I remained responsible
for deciding what to build, how to structure it, where to simplify, and how to verify that the
result met the requirements.
