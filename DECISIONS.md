# Ready Room Design Decicions

## 1. Understanding the problem before choosing the solution

- Reviewed the product scenario and Maverick’s challenges managing flying-related responsibilities, maintenance, logistics, and administrative work.
- Identified that information was scattered across email, sticky notes, a whiteboard, and memory.
- Recognized that the missed maintenance sign-off illustrated a visibility and capture problem, not simply a task-management problem.
- Focused on the need to see what matters now, what is coming next, and what might sneak up unexpectedly.
- Interpreted the dashboard as the primary product experience rather than building another conventional task list.
- Organized the operational view around TODAY, 3-DAY WATCH, and UP NEXT.
- Kept the experience intentionally quiet, avoiding unnecessary notifications and overwhelming task lists.
- Designed around a single user initially, while leaving room for future squadron delegation.

## 2. Establishing engineering guardrails and development approach

- Used ChatGPT to help translate the discovery material into functional requirements and an implementation plan for OpenHands.
- Established architectural constraints before delegating implementation.
- Chose Domain-Driven Design and Hexagonal Architecture to keep business logic independent of infrastructure.
- Applied KISS and pragmatic scope control to avoid overengineering a take-home assignment.
- Defined the expected technology stack: React, TypeScript, Vite, Python, FastAPI, Pydantic, SQLAlchemy, and SQLite.
- Required authentication and authorization to be first-class architectural concerns, even though the demonstration would use a single-user provider.
- Reviewed and adjusted the implementation plan before providing it to OpenHands.
- Used OpenHands as an autonomous implementation agent, while retaining responsibility for product direction, architecture, and acceptance.

## 3, Delivering the core prototype first

- Prioritized the essential operational workflow before adding external integrations.
- Focused the first implementation on the dashboard, task management, recurring responsibilities, and quick capture.
- Used OpenHands to implement the frontend, backend, persistence, tests, and Docker configuration.
- Kept the initial application self-contained and runnable locally.
- Used Docker Compose to simplify startup and make the demonstration reproducible.
- Established automated backend and frontend tests as part of the implementation.
- Reached a working initial prototype in approximately an hour.
- Evaluated the application against the original problem rather than adding features simply because they were technically interesting.

## 4. Testing and refining the core experience

- Ran the application and exercised the workflows rather than relying solely on generated code or passing unit tests.
- Refined the timezone configuration to support the operator's local timezone.
- Added visual urgency cues to make important responsibilities easier to recognize.
- Improved quick capture to include the information needed to create a useful responsibility.
- Reviewed recurring-task completion and history behavior.
- Refined demo reset behavior so the application could be reliably demonstrated more than once.
- Generated regression tests where defects exposed gaps in the original implementation.

## 5. Expanding scope to real calendar and email integrations

- Once the initial prototype was working and time remained, considered integrating mail and calendar.
- Decided that actual calendar and email connectivity would be more meaningful than mocked integrations.
- Added a provider abstraction for calendar access.
- Implemented CalDAV connectivity using Radicale as the local calendar server.
- Added an email integration behind an isolated service boundary using IMAP.
- Used GreenMail as the local email server for the demonstration.
- Kept both integrations optional and best-effort so the core application could operate without them.

## 6. Connecting external information to operational workflows

- Added a local calendar-event cache so external calendar data could be presented consistently in the application.
- Integrated upcoming calendar events into the dashboard and daily briefing.
- Implemented calendar event creation, deletion, and .ics import.
- Added a read-only mailbox experience for reviewing recent email.
- Allowed an email message to be captured as a responsibility.
- Introduced EmailSource records to preserve the relationship between captured responsibilities and their source messages.
- Used message identifiers to prevent duplicate captures.
- Added calendar-event capture into tasks while preserving event identity and avoiding duplicate task creation.
- Kept the frontend independent of the underlying calendar and email providers.

## 7. Validating integrations against real protocols

- Tested the integrations against actual Radicale and GreenMail instances rather than relying exclusively on in-memory test doubles.
- Discovered differences between the behavior of real protocol implementations and the assumptions made during initial development.
- Corrected calendar parsing behavior involving VEVENT data and timezone information.
- Fixed CalDAV calendar discovery and relative URL handling.
- Addressed calendar deletion issues involving provider-relative resource URLs.
- Corrected mailbox seeding and reconciliation behavior in GreenMail.
- Added safeguards to keep integration seeding idempotent and non-blocking.
- Verified that restarting the application did not create duplicate tasks or email captures.
- Added regression coverage for defects found during live integration testing.

## 8. Preparing a reproducible demonstration

- Configured calendar and email integrations to be enabled by default in the local demonstration environment.
- Added the ability to opt out of individual integrations when needed.
- Added demonstration arrivals to introduce sample calendar events and email messages.
- Verified that the application could start from a clean Docker environment.
- Confirmed that all four containers became healthy and that schema creation and integration seeding completed.
- Tested the application through the frontend proxy rather than relying only on direct backend requests.
- Verified persistence across restarts and checked that seed data was not duplicated.
- Ran the end-to-end acceptance checks and confirmed all 15 checks passed.
- Prepared a concise demonstration flow covering the dashboard, recurring tasks, calendar, mailbox, briefing, and settings.

## 9. Closing reflection

- AI played a substantial role in implementation, but it did not replace engineering ownership.
- ChatGPT helped with product definition, architectural planning, and development direction.
- OpenHands performed much of the implementation work across the frontend, backend, infrastructure, tests, and documentation.
- I remained responsible for deciding what to build, how the architecture should be structured, which tradeoffs were acceptable, and when to change scope.
- I validated the results through code review, automated tests, real integration testing, and end-to-end execution.
- The most important decisions came from balancing the original user problem, the assignment's time constraints, and the value of a credible working demonstration.
