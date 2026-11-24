# Squadron Platform Expansion

## Purpose

Evolve READY ROOM from a single-user operational-awareness demo into a lightweight squadron readiness and coordination application. Preserve the existing product focus: one operational scan that helps a user see what needs attention now, what is approaching, and what could otherwise be overlooked.

This expansion is intentionally smaller and more focused than Bluestaq Notes' enterprise agentic architecture. Retain the current DDD/Hexagonal boundaries and extend them only as needed.

## Product principles

1. **Operationally useful, not administratively heavy:** optimize for a clear operational scan and fast task coordination.
2. **Responsibility is explicit:** distinguish an individual task from a responsibility the team or squadron must ensure is completed.
3. **Shared work has accountable ownership:** shared tasks have an accountable owner even when collaborators contribute.
4. **Duty positions outlive personnel:** recurring responsibilities can belong to a duty position and route to its current holder.
5. **Agents assist, humans remain accountable:** Jev may prepare and recommend; trusted application services enforce permissions and execute.
6. **Progress means complete capability:** prioritize integrated, verifiable user journeys over disconnected layers.
7. **Least privilege:** people and agents receive only the permissions necessary for their scope.
8. **Traceability:** important changes, approvals, assignments, handoffs, and agent actions have inspectable history.
9. **Classification and hosting constraints come first:** do not store real sensitive operational/personnel data until deployment authorization and information-handling requirements are established.

## Product areas

### 1. Operations
The operational scan supports personal, team, and squadron scope where the actor is authorized. Surface actionable information such as:
- overdue tasks and responsibilities
- upcoming due items
- tasks without an owner
- handoffs awaiting acceptance
- assignments awaiting acknowledgment
- recurring responsibilities at risk
- recent changes relevant to the user

Avoid opaque readiness scores. Display source facts and explain indicators.

### 2. Tasks and collaboration
Task visibility scopes:
- **Personal:** owner-only by default
- **Shared:** explicitly shared with selected members
- **Team:** available to authorized members of a team
- **Squadron:** available to authorized squadron members

Task capabilities, as needed for the first release:
- title, description, status, priority, due date
- accountable owner
- assignee (individual, team, or duty position where supported)
- collaborators and watchers
- comments/activity
- reference links and attachments only after storage and security controls are established
- acknowledgment separate from completion
- reassignment and handoff
- completion notes/evidence
- audit/history

Shared tasks should not imply that every member is individually responsible. Model accountable ownership, assignee, collaborators, and watchers distinctly.

### 3. Squadron, teams, and duty positions
Start with a single squadron organizational boundary. Support:
- squadron membership and lifecycle
- teams/departments
- simple role assignments
- duty positions
- current duty-position holder
- user profile/timezone/preferences

Do not implement enterprise multi-tenant administration unless the product requires multiple independent squadrons or installations. Treat squadron scope as a security boundary in data access and queries.

Suggested initial roles (adjust to actual squadron requirements):
- Squadron Administrator
- Officer/Coordinator
- Team Lead
- Member
- Read-only

Roles should be complemented by scoped permissions; avoid role-only checks where team/squadron scope matters. Duty-position assignments are time-bounded and separate from permanent user roles.

Membership lifecycle: INVITED, ACTIVE, SUSPENDED, REMOVED. Removal/revocation must invalidate access and relevant caches/sessions.

### 4. Shared recurring responsibilities
Extend existing recurrence rather than replacing it without evidence. Support:
- personal, team, and squadron scope
- series owner and responsible duty position
- default assignee and collaborators
- due-time/timezone semantics
- start/end, pause/resume
- occurrence generation and idempotency
- per-occurrence exceptions (due-date change, reassignment, skip/cancel)
- series revision history
- acknowledgment and completion requirements
- optional escalation/follow-up rules

A series edit must clearly distinguish changes to future occurrences from edits to a single occurrence. Preserve historical occurrences and their responsible parties. If duty-position holder changes, route future occurrences to the new holder; do not rewrite historical accountability.

### 5. Handoffs and continuity
Make duty turnover a first-class workflow. A turnover package can contain:
- open tasks
- overdue responsibilities
- upcoming recurring requirements
- pending decisions
- unresolved handoffs
- recent changes
- relevant operational notes/references

Jev may draft a turnover summary from authorized records. The outgoing holder reviews it; the incoming holder acknowledges receipt. Acknowledgment does not imply acceptance of every task—explicit handoff acceptance is a separate state where applicable.

### 6. Briefings and reports
Support a focused initial set:
- personal daily briefing
- team/department status
- squadron weekly summary
- recurring responsibility status
- turnover briefing

Briefings should be based on application data and optionally retain a snapshot of the inputs and generated narrative for later review. Counts and task facts must be computed deterministically, not invented by the LLM.

### 7. Notifications and acknowledgment
Begin with in-app notifications. Add email or other channels only when configured and tested.

Event examples:
- assignment or reassignment
- shared-task update
- acknowledgment requested
- handoff awaiting acceptance
- deadline approaching
- recurring occurrence generated
- workflow/approval requires attention

Use preferences and aggregation to prevent notification overload. Notification failure must not silently change task/workflow state. Acknowledgment is not completion.

### 8. Operational notes and reference material
A deliberately small knowledge feature may support notes, checklists, references, links, lessons learned, and turnover notes. Each item should have scope, owner, visibility, and revision information. Distinguish approved/authoritative material from informal user notes.

Do not build a full enterprise document-management system as part of this expansion.

### 9. Jev assistant
Jev is the conversational interface and bounded workflow coordinator—not an unrestricted chatbot.

Example interactions:
- What needs my attention today?
- What is coming due for my team this week?
- Which shared tasks have no accountable owner?
- Prepare the daily briefing.
- Draft a recurring responsibility for every Friday.
- Show assignments awaiting acknowledgment.
- Prepare a turnover package for this duty position.
- What changed since yesterday?
- Recommend a task distribution based on workload.

Jev capabilities should progress through these levels:
- **Read:** retrieve authorized context and answer grounded questions.
- **Draft:** propose tasks, assignments, recurrence changes, briefings, and handoffs.
- **Execute low-risk:** perform explicitly granted actions after deterministic policy checks.
- **Approval-gated:** request human approval for consequential changes.
- **Restricted:** prohibit actions by policy (for example, unauthorized external communications or access to restricted information).

The AI must not decide its own authority. It may suggest; the application authorization and workflow services decide.

### 10. Agent identity, authentication, and delegation
Humans, agents, and delegated authority are distinct.

- Human authentication establishes a human principal and session.
- Agent identity represents a registered agent/workflow, with a stable identifier and version.
- Delegation grants limited capabilities to an agent for a specific purpose, scope, and duration.
- Delegation is revocable and expires.
- Agent actions are audited with initiating human (when applicable), agent identity/version, run/workflow, granted capability, target resource, and result.
- Agents never reuse or impersonate human session credentials.
- Agent permission is not automatically equivalent to the initiating user's permission; it is an explicit attenuated grant.
- Agents cannot approve their own work or satisfy human approval requirements.

### 11. Agentic workflows
Start with a small set of durable, inspectable workflow types:
- daily briefing preparation
- task capture/classification from an approved source
- recurring responsibility preparation
- deadline follow-up draft
- task-owner recommendation
- duty turnover package
- readiness/attention scan

A workflow execution should have an ID, initiating actor, agent identity/version, status, timestamps, inputs/source references, proposed actions, tool invocations, approvals, outputs, errors, and retry history. Persist execution state and support bounded retries, cancellation, and recovery.

Avoid creating a generic workflow designer or large multi-agent hierarchy initially. Jev can coordinate specialized task profiles within one runtime and central execution policy.

### 12. Authentication and authorization
Implement real authentication behind the existing identity provider abstraction. Prefer standards-based OIDC where appropriate to the deployment, with secure server-side session handling. Do not make an IdP choice until the target environment and operational constraints are confirmed.

Authorization should remain intentionally simple:
- roles for broad functions
- squadron/team scope for resource access
- explicit resource shares for shared/personal tasks where required
- duty-position access as an additional scope
- trusted actor context propagated through use cases
- server-side checks on every access and mutation
- explicit deny for revoked/suspended membership
- authorization-aware retrieval for Jev
- task-bound agent capabilities and expiration

Do not rely on UI visibility or LLM tool descriptions as security enforcement. Personal resources must not leak through search, summaries, notifications, caches, exports, or AI context.

### 13. Audit and activity history
For important actions, record who/what initiated the action and what changed. Minimum audit/activity coverage:
- membership and role changes
- task creation, updates, sharing, assignment, acknowledgment, completion, and handoff
- recurring-series changes and occurrence exceptions
- duty-position holder changes
- approvals and rejections
- agent delegation grants/revocation
- workflow execution and consequential tool actions

Use append-oriented history and avoid storing secrets or unnecessary sensitive payloads. The initial implementation need not have Bluestaq-level cryptographic integrity controls, but the records must be trustworthy and access-controlled.

## Suggested lightweight architecture

Keep the current architecture and extend existing contexts/areas rather than creating many services:

- **Identity & Squadron:** users, sessions, membership, teams, duty positions
- **Tasks & Recurrence:** tasks, sharing, assignment, acknowledgment, recurrence rules/occurrences, handoffs
- **Operations & Briefings:** operational scan, filters, snapshots, reports
- **Jev & Agent Runtime:** AI provider boundary, context assembly, agent identity, tool catalog, workflow runs
- **Workflow & Approvals:** durable workflows, human approval gates, resumption
- **Notifications:** in-app notification and delivery preferences
- **Knowledge (optional later):** scoped notes and references
- **Audit:** activity history

These are logical groupings, not a mandate to create independent deployable services. Keep the application a modular monolith.

## Agent/tool execution contract

Every Jev/agent tool follows a central path:

1. Validate tool name, version, and typed input.
2. Resolve trusted actor context and agent identity.
3. Check active membership, scope, and delegated capability.
4. Evaluate deterministic authorization.
5. Determine risk and approval requirement.
6. Validate budgets, rate limits, and idempotency.
7. Invoke the application use case (never bypass it).
8. Validate/minimize result.
9. Record activity/audit and workflow outcome.
10. Return bounded, useful output to the model.

No unrestricted shell, arbitrary filesystem, direct SQL, generic HTTP, or generic CRUD tool access.

## Approval model

Approval is required for actions defined as consequential by policy, such as squadron-wide assignment, changes to shared recurrence rules, sensitive sharing changes, or external communication if later supported.

An approval must bind to the exact proposed action and parameters. If the proposal changes, approval is invalidated or revalidated. Approval and execution are distinct. No response, timeout, or notification failure may result in implicit approval.

## Data migration and compatibility

- Preserve current single-user/demo behavior during development.
- Identify existing owner-scoped records and migrate or map them to a personal workspace or initial squadron context without losing ownership.
- Make migrations reversible where practical and test them against fixtures.
- Do not assume existing data can be discarded.
- Keep a feature flag or isolated demo mode for local development if it helps, but never let demo authentication leak into production.
- Document migration assumptions and recovery steps.

## Phased roadmap

### Phase 0 — Discovery and decisions
Inspect current implementation, tests, persistence, recurrence, identity/authorization ports, integrations, and UX. Confirm deployment assumptions and classification constraints. Produce a capability map and dependency-aware plan.

### Phase 1 — Authentication and squadron foundation
- Real authentication/session flow behind existing abstraction.
- User and squadron membership.
- Initial roles and team scopes.
- Squadron bootstrap/admin invitation.
- Tenant/squadron-aware persistence and query boundaries.
- Secure user/session lifecycle.
- Migration from current single-user ownership.
- Tests for isolation and access denial.

**Exit:** two or more users can authenticate into the same squadron and are isolated from unauthorized data.

### Phase 2 — Shared tasks and accountability
- Task scope and sharing.
- Owner/assignee/collaborator/watcher semantics.
- Assignment and acknowledgment.
- Comments/activity.
- Reassignment and handoff.
- Authorization and audit.
- UI for shared work.

**Exit:** a user can create a shared task, assign responsibility, notify collaborators, track acknowledgment, and complete it with history.

### Phase 3 — Shared recurrence and duty positions
- Team/squadron recurrence.
- Duty-position assignment.
- Occurrence generation.
- Idempotency.
- Per-occurrence exceptions.
- Series revisions.
- Future routing after duty-position changes.
- Recurrence UI and operational scan.

**Exit:** shared recurring responsibilities generate predictable occurrences, are correctly assigned, and preserve historical ownership.

### Phase 4 — Jev read and draft workflows
- Jev conversational interface.
- Authorization-aware context assembly.
- Read-only task/recurrence/team tools.
- Briefing generation.
- Draft task/assignment/recurrence changes.
- Review/confirm interaction.
- Provider-neutral AI abstraction and failure handling.

**Exit:** Jev can answer grounded operational questions and create reviewable drafts without unauthorized data access.

### Phase 5 — Authenticated agent runtime and approvals
- Agent identity and versioning.
- Capability catalog.
- Task-scoped, expiring delegation.
- Durable workflow/run records.
- Approval gate.
- Tool gateway.
- Idempotency, budgets, cancellation, recovery.
- Audit and observability.

**Exit:** Jev can execute explicitly permitted actions, request approval for restricted actions, and produce inspectable execution history.

### Phase 6 — Squadron operations and continuity
- Team/squadron briefings.
- Duty turnover packages.
- Notifications and preferences.
- Workload and overdue indicators.
- Recent change awareness.
- Optional scoped notes/references.

**Exit:** the squadron can use READY ROOM to coordinate work and maintain continuity across personnel/duty transitions.

## Priority order and dependency notes

1. Confirm hosting, authentication, classification, and data-handling constraints.
2. Define squadron/membership/permission contracts before shared features.
3. Establish shared task semantics before shared recurrence.
4. Establish task/agent authorization before Jev mutations.
5. Implement Jev read-only workflows before agent execution.
6. Establish durable workflow and approval state before autonomous execution.
7. Build duty turnover on top of task, recurrence, history, and scoped context.

Do not start parallel implementation across dependent phases until shared contracts are stable. Parallelize independent test, UX, documentation, and security review tasks only with clear ownership.

## Initial acceptance scenarios

1. Two authenticated squadron members can view authorized squadron-shared tasks but not each other's private tasks.
2. A team lead can create a shared task, assign an accountable owner, and add collaborators.
3. An assignee can acknowledge an assignment without marking it complete.
4. A task can be handed off and accepted, preserving the history and original responsibility.
5. A shared recurring responsibility generates occurrences idempotently.
6. Editing one occurrence does not unintentionally change the recurrence series.
7. Changing a duty-position holder routes future occurrences to the new holder while preserving historical ownership.
8. Jev can answer an operational scan using authorized application data and cite/identify the underlying records.
9. Jev can draft a task or recurrence change; the user can review before execution.
10. An agent cannot access data outside its delegated scope, even if prompted to do so.
11. A revoked delegation cannot be used for subsequent actions.
12. A consequential action requires approval and is not executed before approval.
13. Agent/workflow execution history accurately records actor, agent, tool, action, and result without leaking sensitive payloads.
14. Notification failure does not silently mark a task acknowledged, approved, or complete.
15. Squadron and team boundaries are enforced in API, query, search, notification, and AI-context paths.

## Explicit non-goals for the first expansion

- Enterprise multi-tenant administration.
- General-purpose workflow builder.
- Complex policy language.
- Unlimited agent-to-agent delegation.
- Unrestricted autonomous agents.
- Enterprise-grade cryptographic audit ledger.
- Predictive or opaque readiness scoring.
- Full document-management platform.
- Automated outbound email/message execution without a separately reviewed requirement.
- Broad integrations before core shared-work journeys are proven.

## Architecture decision log to maintain

During discovery/implementation, document decisions on:
- authentication provider and deployment model
- session storage and cookie/security strategy
- squadron bootstrap and invitation flow
- initial role/permission matrix
- data isolation approach and migration
- recurrence/timezone and occurrence-generation semantics
- duty-position history
- approval thresholds and who can approve
- agent identity and delegation representation
- Jev provider and context strategy
- workflow persistence, retries, and idempotency
- notification channels
- audit retention and information-handling constraints

These decisions should be made based on the existing code and target deployment. Do not invent constraints or adopt enterprise patterns without a clear need.
