# ADR-009: Jev AI provider, context assembly, and failure strategy

- **Status:** Accepted 2026-11-24
- **Ticket:** [#11](https://github.com/anotherhale/str-ready-room/issues/11) (`P0-09`)
- **Requirements:** R-JEV-01, R-JEV-02, R-JEV-03, R-JEV-04, R-AUTHZ-08, R-ARCH-06
- **Depends on:** ADR-001 (no-egress default, unclassified data), ADR-004 (roles,
  scopes, ordered authorization), ADR-006 (§8 single visibility policy and
  repository filter keys), ADR-007 (what a series/occurrence context item is)
- **Constrains:** `P4-01` (provider port and fake), `P4-02` (context assembly),
  `P4-03` (tool catalog and gateway), `P4-04` (conversation), `P5-*` (agent
  runtime and approvals)

## Context

There is no AI dependency in READY ROOM today. The product must gain Jev, a
*bounded coordinator* that reads authorised context, answers grounded questions
about operational state, and drafts reviewable changes — never an unrestricted
chatbot that decides its own authority.

Four constraints shape every decision below:

1. **The product must stay runnable offline.** ADR-001 sets a no-egress default,
   an unclassified/synthetic ceiling, and no external services at runtime. A demo
   or test run cannot depend on a model endpoint or an API key.
2. **Authorization is server-side and computed once.** ADR-006 §8 requires a
   single visibility policy that also emits the repository filter keys, with
   filtering in SQL. Context assembly is a read path, so it must reuse that
   policy; a second visibility implementation would drift and leak.
3. **The model is not a security boundary.** The spec forbids relying on UI
   visibility or LLM tool descriptions as enforcement, and acceptance scenario 10
   requires that an agent cannot reach data outside its delegated scope *even
   when prompted to do so*.
4. **Failure must be boring.** An unavailable provider may degrade the assistant
   and must never break the rest of the application or change task state. This is
   the same stance the calendar and mailbox integrations already take.

The ticket deliberately excludes model calls, SDKs, API keys, RAG/vector search,
and autonomous execution. This ADR therefore decides the **seams and contracts**
those later tickets fill in.

## Decision

### 1. One narrow provider port, no SDK in the application

`backend/app/application/ports/ai.py` defines the port. It speaks only in
application-owned types and never imports a vendor SDK, an HTTP client, or a
settings object.

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, Any]      # JSON Schema, catalog-owned

@dataclass(frozen=True)
class ToolCall:
    call_id: str                          # provider-scoped, echoed back on results
    name: str
    arguments: Mapping[str, Any]

@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None       # set on role="tool"

@dataclass(frozen=True)
class ChatRequest:
    messages: tuple[ChatMessage, ...]
    tools: tuple[ToolSpec, ...] = ()
    max_output_tokens: int = 1024
    timeout_seconds: float = 20.0

@dataclass(frozen=True)
class ChatResponse:
    message: ChatMessage                  # assistant turn, may carry tool_calls
    finish_reason: Literal["stop", "tool_calls", "length", "error"]
    usage: Mapping[str, int] = field(default_factory=dict)

class JevProvider(Protocol):
    name: str
    def complete(self, request: ChatRequest) -> ChatResponse: ...
```

Rules:

- **Non-streaming in Phase 4.** One request, one response. Streaming buys
  perceived latency and costs cancellation, partial-failure, and backpressure
  handling that a small operational UI does not need yet. The port is narrow
  enough that a later `stream()` can be added without touching use cases; the UI
  renders a completed turn today.
- **The port carries no authority.** It receives message text, tool *specs*, and
  a timeout. It never receives a `Principal`, a session, a permission, a
  repository, a session token, or a connection string. It cannot widen scope
  because it is never given the means to query.
- **Tool calls are requests, not actions.** `complete()` returns the calls the
  model *wants*; the application decides whether to run them (§6). A provider
  implementation has no path to a use case.
- **Errors are typed and closed.** `JevProviderError` with
  `ProviderUnavailableError` (connection/refusal), `ProviderTimeoutError`,
  `MalformedResponseError` (unparseable output or a tool call that does not match
  its schema). Anything else a vendor adapter raises is wrapped as
  `ProviderUnavailableError`; a vendor exception type never escapes the adapter.

### 2. Provider selection is registry-only, and the default is offline

`backend/app/ai/providers/` mirrors the existing integration layout
(`app/calendar/providers/`, `app/mailbox/providers/`: `base.py`, one adapter per
file, `registry.py`). `build_jev_provider(settings) -> JevProvider | None` is the
single place a concrete adapter is chosen.

| `READY_ROOM_JEV_PROVIDER` | Result |
|---|---|
| `fake` (**default**) | `FakeJevProvider` — deterministic, offline, no credentials |
| `none` / `off` / empty | `None`; Jev routes report "unavailable", the app is unaffected |
| any other name | configuration error at startup (`ValueError`), never a silent fallback |

- A **network** provider is a deliberate opt-in: it requires its own provider
  name **and** its own credential environment variables. A network provider whose
  credentials are absent or blank **fails closed at construction** — it refuses
  to start rather than serving requests with an empty key. This mirrors the
  ADR-002 guard that refuses `SingleUserAuthProvider` outside `demo`/`test`.
- Choosing a network provider is an explicit operator act that changes the
  no-egress posture of ADR-001. It is not enabled by a default, and the demo
  stack ships `fake`.
- Unknown provider names are configuration errors (same rule as D-033 for
  calendar/mailbox). There is exactly one registry; no module instantiates a
  concrete AI adapter.

### 3. The fake provider is a real second adapter with a grounding contract

`FakeJevProvider` is not a mock. It is the adapter the demo, the tests, and any
unattended WINGMAN run use, so it must be a genuine implementation of the port.

- **Deterministic.** The same `ChatRequest` yields a byte-identical
  `ChatResponse`: no randomness, no clock reads, no set-iteration order, no
  hidden global state. Tests assert exact text and exact citation ids.
- **Grounded or silent.** It answers **only** from the context envelope it is
  given (§4). If the question cannot be answered from that envelope it returns a
  "cannot answer from the authorised context I was given" turn with
  `finish_reason="stop"` and no citations — it never guesses, invents a record,
  or fills gaps from world knowledge. This is the same contract a real provider
  must honour, which is why the fake is the reference behaviour.
- **Tool calls only from the supplied catalog.** It may emit a `ToolCall` only
  for a `ToolSpec` present in `request.tools`, with arguments copied verbatim
  from the envelope. It never invents an argument value.
- **Covers the Phase 4 scenarios.** The eight read/draft interactions named in
  spec area 9 that Phase 4 requires (attention today, due this week, tasks with
  no accountable owner, daily briefing, draft a recurring responsibility,
  assignments awaiting acknowledgment, turnover package, what changed since
  yesterday) each have a deterministic answer shape, so `P4-04` can build the
  conversation flow and its tests against it.
- **Lives under `tests/unit/adapters/ai/`** for adapter-shape regressions, next to
  the existing adapter tests. The lesson recorded in `AGENTS.md` applies: a double
  that is never exercised as an adapter hides real defects (three real bugs came
  from exactly that in the calendar integration).

### 4. Context assembly is a scoped read path, and the envelope is bounded

`JevContextAssembler` (application layer, `P4-02`) turns
`(principal, question)` into a `JevContext`. It is an ordinary read path, not a
privileged one.

**Authorization first, in SQL.** The assembler builds one `ScopeCriteria` from the
resolved principal (never from a request field) and calls the **same** scoped
repository methods the API uses. There is no unscoped query available to it, so
"answer outside my scope" is not reachable by prompt. Denied records are never
fetched and therefore never post-filtered; counts and "N more" summaries come
from scoped repository methods too, so a count cannot leak a hidden record
(ADR-006 §8, acceptance scenario 15).

**Bounded, deterministic selection.**

| Kind | Cap | Ordering |
|---|---|---|
| `task` (open, then recently closed) | 25 | derived urgency, due date, id |
| `recurrence_series` | 10 | next due date, id |
| `briefing` | 1 (latest) | date |
| `notification` | 10 (unread first) | created-at, id |
| `note` / `reference` | 10 | updated-at, id |
| `member` / `team` / `duty_position` | as required by the question | name |

- A total character budget (default 12 000) is enforced **after** per-kind caps
  by dropping whole items from the end of the deterministic order, never by
  truncating an item mid-field. The envelope records what was dropped
  (`omitted: {kind: n}`) so an answer can say "there are 12 more".
- The assembler is pure with respect to the clock: `today` comes from the clock
  port (ADR-006 time rules), so the same data and the same `today` yield the same
  envelope.
- Ordering is total and stable. Prompt content must not depend on dictionary or
  database row order, or answers become untestable.

**Minimisation and redaction.** Only the fields a citation needs are included:
id, scope, title, status, due date, accountable-owner display name and id,
assignee kind, and the derived urgency. Excluded always: credentials, session
tokens, email bodies (subject/sender/date only), calendar event bodies, other
members' personal-scope records, free text beyond a bounded excerpt, and any
`demo:*` or operator-settings material. Personal-scope items are assembled only
for their accountable owner or a holder of a write share.

**Citation contract.** Every item carries a stable `citation_id` of the form
`<kind>:<id>` (`task:<uuid>`, `series:<series_id>`, `briefing:<date>`,
`note:<id>`, `member:<user_id>`, …). The envelope is the only source of
citation ids, and the id resolves to a real record the caller may read.

- The system prompt states that answers must cite the items they rely on.
- After generation the answer is **checked**: every citation id in the answer must
  exist in the assembled set, and an answer with factual claims but no citation
  is marked `ungrounded`.
- Ungrounded answers are returned with a visible warning, not silently accepted,
  and are never the basis of a draft. A citation id that is not in the envelope is
  stripped before display — the model cannot manufacture provenance.

### 5. Failure behaviour is a bounded, visible degradation ladder

| Failure | Behaviour |
|---|---|
| Provider disabled (`none`) or unreachable | Jev routes report `unavailable`; every other view works. No retry loop, no startup failure. |
| Timeout | Per-request `timeout_seconds` (default 20, configurable). **One** retry, only for a read-only turn with no tool calls; then `unavailable`. A timeout never yields a partial answer presented as complete. |
| Malformed response / tool call outside the catalog or failing its schema | The gateway rejects the call, returns a typed error to the model once, and ends the turn on a second offence with `finish_reason="error"`. **Nothing is executed.** |
| `finish_reason="length"` | Returned with `truncated: true`; the UI must show it and **no draft is created** from a truncated turn. |
| Partial/internal error mid-turn | The turn fails as a whole. There is no "half answer with half citations" state. |

Every failure is logged with the run id and, when a workflow run exists, audited
(ADR-010, `P5-*`). **No provider failure may change task, series, approval, or
notification state** — the same isolation rule notifications must satisfy.

### 6. Prompt injection: model output is untrusted data

The model is an untrusted component operating on untrusted content (task titles,
note text, email subjects can all carry instructions).

- **Context is delimited data.** Items are delivered inside an explicit envelope
  with per-item citation ids, and the system prompt states that everything inside
  is data to be described, never instructions to follow.
- **Output is never a command.** Model output is not parsed as a tool name, a
  filter, SQL, a file path, or a URL. The only structured thing accepted from it
  is a tool call, and a tool call is validated against the catalog's JSON Schema
  before it means anything.
- **Every tool call is re-authorised server-side.** The gateway runs the ADR-004
  ordered evaluation (active membership → permission → scope → relationship →
  approval gate) on the *trusted* actor context, not on anything the model said.
  A tool call carries no principal; the gateway supplies it. This is why prompt
  injection cannot escalate: the worst a malicious payload can do is ask for a
  call that the actor was always allowed to make, or one that is denied.
- **No ambient capability.** No shell, filesystem, SQL, generic HTTP, or generic
  CRUD tool exists (spec: agent/tool execution contract). The catalog is explicit
  and versioned, and Jev's read path uses the same scoped repositories as the UI.
- **Nothing secret is in scope.** Because assembly excludes credentials, session
  tokens, and other users' personal records, they cannot be exfiltrated by a
  prompt that asks for them; the refusal is structural, not a matter of the model
  behaving well.
- **Agents never gain human accountability.** Consistent with ADR-004 and
  ADR-008, no Jev or agent path may acknowledge a task, acknowledge a turnover, or
  decide an approval.

### 7. Lane boundaries for the implementing tickets

| Ticket | Implements | Must not do |
|---|---|---|
| `P4-01` (#64) | `application/ports/ai.py`, `app/ai/providers/{base,fake,registry}.py`, `Settings.jev_provider`, unit tests for the fake's determinism and grounding | Any context assembly or tool execution |
| `P4-02` (#65) | `JevContextAssembler`, `JevContext`/`ContextItem`, budget and citation rules, scoped-repository use | Any provider call or draft |
| `P4-03` (#66) | Read-only tool catalog and gateway skeleton reusing the authorization port | Mutating tools, approvals |
| `P4-04` (#67) | Conversation service, prompt/envelope construction, post-generation citation check | Autonomous execution |

`P5-*` adds agent identity, delegation, workflow runs, and the approval gate on
top of these seams (ADR-008, ADR-010). Nothing in this ADR pre-empts them.

## Consequences

**Positive**

- The demo and every test run stay offline, credential-free, and reproducible.
- Scope safety is inherited rather than re-implemented: there is one visibility
  policy and one set of scoped repository methods, so Jev cannot become the leak
  path that search, briefings, and notifications are warned about.
- Citation ids give grounded, checkable answers and make "the model made it up"
  detectable rather than a matter of trust.
- A vendor can be swapped by adding one adapter file, because no use case imports
  a provider.

**Negative / costs**

- Non-streaming means the first token arrives only when the turn completes; a slow
  provider feels slow. Accepted for Phase 4; streaming is an additive change.
- The character budget and per-kind caps are policy numbers that will need tuning
  once real questions exist; too tight produces "12 more" answers, too loose
  wastes tokens and dilutes grounding.
- The fake provider is a maintained artifact: new answer shapes and new tool
  catalog entries must be added to it, or the demo silently answers less.
- Post-generation citation checking cannot catch an answer that is *wrong but
  cited*; it proves provenance, not truth. The UI must not imply otherwise.

## Alternatives considered

1. **A vendor SDK called directly from the service layer.** Rejected: it makes the
   application depend on a network vendor, breaks offline demo/tests, and puts
   authority next to the model call.
2. **Let the model query the database through generated SQL or a generic query
   tool.** Rejected: it re-implements authorization inside a prompt, which is
   exactly the boundary the spec forbids and the way cross-scope leaks happen.
3. **Filter context after fetching and then hand it to the model.** Rejected by
   ADR-006 §8: post-filtering leaks through counts, pagination, and timing, and
   would put unauthorised text in the process that builds the prompt.
4. **RAG/embeddings over all records.** Rejected as out of scope and unsafe: a
   vector index is a second, unscoped copy of the data with its own retention and
   leak surface. Bounded, scoped reads answer the Phase 4 questions.
5. **Stream tokens straight to the UI in Phase 4.** Rejected: it forces
   cancellation, partial-answer, and citation-validation semantics before there is
   a product reason for them.
6. **A "smart" fake provider with random or varied phrasing.** Rejected: it makes
   tests flaky and hides nondeterminism that would otherwise surface in the real
   adapter.
7. **Fail open when the provider is unconfigured (answer from the app directly).**
   Rejected: it invents a second answer path with no citations and no review
   boundary.

## Open questions (confirmable defaults, non-blocking)

| # | Question | Default until decided | Owner |
|---|---|---|---|
| J1 | Should the retry budget ever exceed one attempt for a read-only turn? | No. One retry, then degrade; a second slow call is worse than an honest "unavailable" | Engineering |
| J2 | Is the character budget 12 000 or token-based once a real provider is chosen? | Characters until a provider exists; then the adapter maps the budget to its own token accounting | Engineering |
| J3 | Should Jev ever see a note's full body, or only its excerpt? | Excerpt only in Phase 4; full body requires an explicit per-item expansion the user asks for | Product owner |
| J4 | Are `ungrounded` answers shown to the user or suppressed? | Shown with a warning. Suppressing hides a grounding defect the operator should see | Product owner |
| J5 | Does an operator-settings change to `READY_ROOM_JEV_PROVIDER` require a restart? | Yes. Provider choice is startup configuration, like the calendar/mailbox registries | Engineering |
| J6 | May a network provider be enabled while `environment=demo`? | No default. The demo ships `fake`; enabling egress is an explicit deployment decision under ADR-001 | Authorizing Official |

## Validation

Documentation-only change: this ADR adds
`docs/adr/ADR-009-jev-provider-context.md`, flips its row in
`docs/adr/README.md` to Accepted, and records the durable AI invariants in
`AGENTS.md`. No application code, dependency, configuration default, test, or
migration was modified.

| Acceptance criterion | Section |
|---|---|
| Provider port and fake-provider contract are specified | §1, §2, §3 |
| Context assembly rules and citation contract are specified | §4 |
| Failure/degradation behaviour is specified | §5 |
| The model is explicitly untrusted and cannot widen scope | §4, §6 |
| `P4-01`..`P4-04` can implement directly | §7 (lane table) plus §1–§6 |

Checked against spec area 9 (Jev levels and the "must not decide its own
authority" constraint) and acceptance scenarios 8, 9, 10, and 15.

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` §9 (Jev assistant), §10 (agent identity),
  §12 (authorization, "do not rely on UI visibility or LLM tool descriptions"),
  the agent/tool execution contract, and acceptance scenarios 8–10 and 15
- `docs/adr/ADR-001-deployment-classification.md` (no-egress default,
  unclassified/synthetic ceiling)
- `docs/adr/ADR-004-role-permission-matrix.md` §3 (ordered evaluation, agent
  limits), §5 (scope ceilings)
- `docs/adr/ADR-006-task-scope-sharing.md` §8 (single visibility policy, filter
  keys, no post-filtering)
- `docs/adr/ADR-007-shared-recurrence.md` §1–§3 (series and occurrence fields a
  context item projects)
- `backend/app/application/ports/identity.py` (`AuthProvider`,
  `AuthorizationPort`), `backend/app/application/ports/clock.py` (`today`)
- `backend/app/mailbox/providers/registry.py`,
  `backend/app/calendar/providers/registry.py` (the registry pattern and the
  unknown-name-is-a-configuration-error rule, D-033)
- `backend/app/config.py` (`Settings`, the single environment reader)