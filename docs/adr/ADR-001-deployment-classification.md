# ADR-001: Deployment, classification, and data-handling constraints

- **Status:** Accepted (engineering defaults), with organizational questions unresolved
- **Date:** 2026-11-24
- **Ticket:** [#3](https://github.com/anotherhale/str-ready-room/issues/3) (`P0-01`)
- **Deciders:** READY ROOM engineering; see [Unresolved questions](#unresolved-questions-requiring-organizational-input) for the stakeholder each open item belongs to
- **Supersedes:** none
- **Constrains:** ADR-002 (authentication provider, session storage, cookies), ADR-009 (Jev provider and egress), and the data model

## Context

READY ROOM began as a single-user operational-awareness demo. It currently runs as
a modular monolith started by `docker compose up --build`:

| Component | Current implementation | Notes |
|---|---|---|
| Frontend | React/TypeScript SPA built by Vite, served by nginx | nginx proxies `/api/*` to the backend |
| Backend | Python 3.12 / FastAPI, DDD + hexagonal boundaries | `/api/health` is the health gate |
| Persistence | SQLite at `sqlite:////data/ready_room.db` on a named volume | PostgreSQL supported by configuration through the same adapter |
| Calendar | Self-hosted Radicale (CalDAV) | Optional; `READY_ROOM_CALENDAR_PROVIDER=none` opts out |
| Mail | Self-hosted GreenMail (IMAP/SMTP) | Optional; `READY_ROOM_EMAIL_PROVIDER=none` opts out |

All stored content is synthetic demo data (fictional detachment, invented names).
Identity is the `single_user` demo provider: there is no login, no session, and no
token flow. Backend configuration is read from `READY_ROOM_*` environment
variables, and the runtime is designed to need no internet access.

The expansion adds real authentication, squadron membership, shared tasks, Jev,
and agent execution. Each of those changes what data the system may hold and
where it may run, so deployment and classification must be settled before
implementation. The expansion spec states the rule directly: do not store real
sensitive operational or personnel data until deployment authorization and
information-handling requirements are established.

This ADR records the engineering position the code may rely on now, and names the
organizational decisions engineering cannot make on its own.

## Decision

### 1. Deployment models

**Supported models**, in the order they become available:

| Model | Description | Status |
|---|---|---|
| Local demo | Single workstation, Docker Compose, synthetic data only | **Supported today** |
| Self-hosted single host | One controlled-network host running the Compose stack, on-premises storage | **Chosen first target** |
| Air-gapped single host | Same as above with no network egress and offline image delivery | **Supported design target**; not yet verified |
| Cloud / managed hosting | Any environment reached over the public internet | **Not authorized** until the organizational questions below are answered |

**Chosen first deployment target: self-hosted, single-host, controlled network.**
The local Docker Compose demo remains the development and demonstration profile.
It is the same artifact set with different configuration, not a separate product.

Rationale:

- The current stack is already a single-host Compose deployment with local
  storage; nothing in the design requires a cloud provider.
- A controlled-network single host is the smallest step that can plausibly hold
  operational data, and it keeps the modular monolith intact.
- Air-gapped operation is reachable from the same design if egress-dependent
  features (Jev, external notifications) stay behind explicit configuration.

**Architectural consequences of this choice:**

- The application must remain runnable with **no runtime internet access**.
  Every external dependency (AI provider, notification channel, identity
  provider) is optional and selected by configuration, and its absence must
  degrade gracefully rather than break the operational scan.
- Container images and dependencies must be deliverable offline (image archive
  plus lockfiles). No build step may require fetching from the internet at
  deploy time.
- Persistence must stay portable between SQLite (demo) and PostgreSQL
  (single-host production) through the existing adapter and
  `READY_ROOM_DATABASE_URL`, with no dialect-specific business logic.

### 2. Maximum data classification

**Maximum classification this build may hold: UNCLASSIFIED — synthetic,
non-sensitive data only.**

The current build, including the demo seed, **must not** hold:

- real operational, mission, or readiness data;
- real personnel data (names, duty rosters, contact details, performance or
  medical information);
- classified information of any level, including CUI or any equivalent
  controlled marking;
- credentials or secrets belonging to real systems.

"Synthetic" means invented values that do not describe a real unit, person, or
operation. The demo detachment, its members, and its mail are fictional by
design, and `AGENTS.md` already requires seed data to stay synthetic.

**Conditions required before holding higher classification** (all must hold):

1. An authorizing official has approved the deployment environment for that
   classification, in writing.
2. The information-handling requirements for that classification — storage,
   transmission, encryption, access control, retention, and audit — have been
   documented and accepted.
3. The engineering controls those requirements demand are implemented and
   verified; a documented requirement without a verified control is not enough.
4. The classification ceiling is recorded in this ADR and in deployment
   configuration, so a build cannot be silently promoted by configuration alone.

Until then, "higher classification" is out of scope, and any ticket that would
introduce real data is blocked on this ADR's open questions.

### 3. Hosting, backup, retention, and residency constraints affecting design

- **Data residency:** all persisted data lives on the host's local volume (or the
  configured PostgreSQL instance) inside the controlled network. No component may
  replicate data off-host by default, and no telemetry, crash reporting, or
  analytics may leave the host.
- **Egress:** the default configuration performs no outbound internet calls.
  Features that would require egress (a hosted AI provider, outbound
  notifications) are disabled by default and must be individually justified and
  approved. This is the binding constraint on ADR-009.
- **Backup:** the unit of backup is the database volume plus configuration, not
  application containers. Backup is an operator action on the host; the
  application does not implement a backup service. Restore must be testable
  against the demo profile.
- **Retention:** no retention schedule is approved yet, so the application must
  not silently discard records. Deletion is explicit and authorized, never
  time-based by default. Audit and notification retention is decided in ADR-011,
  which depends on this ADR's retention question.
- **Secrets:** secrets come from environment configuration today. That is
  acceptable for the demo profile only. A real deployment requires an
  operator-managed secret source; secrets must never be committed, logged,
  returned by an API, or written into audit records.
- **Transport:** the single-host deployment terminates TLS at the front door or
  on an approved reverse proxy. Plain HTTP is acceptable only for the loopback
  demo profile.
- **Time:** datetimes persist as naive UTC and "today" is derived from the
  operator's effective timezone; hosting must provide a correct system clock.
  This is unchanged by deployment choice and remains a durable invariant.

### 4. Constraints this ADR places on ADR-002 (authentication and sessions)

- **No identity provider may be assumed reachable.** Because the chosen target is
  a controlled-network (possibly air-gapped) host, ADR-002 must define a local,
  self-contained authentication path — credential store, password hashing, and
  server-side sessions — that works with zero external services. An OIDC
  integration may be added later only if the environment permits the required
  egress or an internal IdP exists.
- **Sessions must be server-side and revocable.** Membership suspension or
  removal must be able to invalidate access immediately; a self-contained token
  that cannot be revoked on the server does not satisfy this.
- **Cookies must be `HttpOnly`, `SameSite`-scoped, and `Secure` whenever the
  deployment is not loopback HTTP.**
- **The demo identity provider must never be selectable in a deployment that
  holds real data.** Configuration must make the demo profile explicit, and
  startup must refuse a demo identity provider when the environment is not
  `demo`.
- **No login, session, or token material may be stored in the repository or in
  logs.**

### 5. Constraints this ADR places on the data model

- Store only the data a workflow needs. Do not add free-text fields whose purpose
  is to hold arbitrary operational content.
- Do not store secrets, tokens, or credentials in domain tables or audit records;
  store references or hashes only.
- Audit and activity records capture actor, action, target, and outcome — not
  sensitive payloads (see ADR-011).
- Any future field that would hold personnel data (for example a user profile
  timezone or display name) must be justified as necessary for a workflow and
  remains subject to this ADR's classification ceiling.
- Classification is a deployment property, not a per-row column. The schema does
  not label individual records as classified; the environment is either
  authorized for the data or it is not.

## Consequences

**Positive**

- Engineering can proceed on authentication, persistence, and Jev with a stable,
  conservative assumption: no egress, no real data, no cloud.
- The demo profile and the production-shaped profile share one artifact set, so
  verification work carries forward.
- The classification ceiling is explicit, so no ticket can quietly introduce real
  operational data.

**Negative / accepted trade-offs**

- A hosted AI provider is not available under the default deployment, which
  constrains Jev to a local model or an explicitly approved egress path.
- Offline image delivery adds operational work for real deployments.
- Backups remain an operator responsibility rather than an application feature.

**Risks**

- If the eventual authorized environment requires cloud hosting, some constraints
  (particularly egress and secret management) will need revisiting. They are
  written so that change is a deliberate ADR amendment, not silent configuration
  drift.
- An unapproved retention default means data accumulates. That is intentional:
  accumulating is recoverable, silently deleting operational records is not.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Cloud-first managed deployment | Not authorized; conflicts with the controlled-network requirement and with no-egress operation |
| Multi-tenant SaaS architecture | Explicit non-goal for the first expansion; adds isolation complexity before single-squadron semantics are proven |
| Microservices split by domain | Unnecessary for a single-host deployment; the modular monolith keeps transactions and deployment simple |
| Store real data in the demo to "prove" the product | Violates the classification ceiling and the synthetic-data invariant in `AGENTS.md` |
| Defer this decision and start implementation | The spec makes classification and hosting a hard prerequisite; deferral would force ADR-002 and the data model to guess |

## Unresolved questions requiring organizational input

These are **not** engineering decisions. Each one blocks work while it stays open.

| # | Question | Owner | Impact while unresolved |
|---|---|---|---|
| Q1 | Which environment is authorized to hold operational data, and what is its accreditation path? | Authorizing Official / Security Officer | Real-data use blocked; cloud stays unauthorized; ADR-002 must stay self-contained |
| Q2 | What is the maximum classification this product is permitted to hold? | Authorizing Official | Ceiling stays "synthetic only"; encryption and retention requirements cannot be finalized |
| Q3 | Is any internet egress permitted, and for which components? | Authorizing Official / Network owner | Jev is limited to a local provider; hosted AI, email, and webhook delivery stay out of scope (ADR-009) |
| Q4 | May the system store personnel data (names, duty rosters, contact details)? | Privacy / HR owner | User profile fields ([#104](https://github.com/anotherhale/str-ready-room/issues/104)) and membership records stay minimal and synthetic |
| Q5 | What retention schedule applies to tasks, briefings, notifications, and audit records? | Records Manager | No time-based deletion is implemented; ADR-011 cannot close |
| Q6 | What backup, restore, and disaster-recovery objectives apply? | Operations owner | Backup stays a manual host procedure; recovery testing stays demo-scoped |
| Q7 | Which secret-management mechanism is approved for a real deployment? | Security Officer / Operations | Environment-variable secrets remain demo-only |

## Validation

Documentation-only change. No application code, configuration, or dependency was
modified; `git diff --stat` confirms only files under `docs/adr/` were added. The
backend and frontend baseline suites were run before and after the change and
remained green; the commands and results are recorded on issue #3.
