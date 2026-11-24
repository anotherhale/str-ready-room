# ADR-002: Authentication provider, session storage, and cookie strategy

- **Status:** Accepted — 2026-11-24
- **Date:** 2026-11-24
- **Ticket:** [#4](https://github.com/anotherhale/str-ready-room/issues/4) (`P0-02`)
- **Deciders:** READY ROOM engineering
- **Supersedes:** none
- **Constrained by:** [ADR-001](ADR-001-deployment-classification.md) — deployment target, classification ceiling, no-egress default
- **Constrains:** #24 (P1-09 credential store), #25 (P1-10 session lifecycle), #26 (P1-11 `SessionAuthProvider`), #27 (P1-12 auth endpoints), #30 (P1-15 login UI), ADR-003 (membership states), ADR-011 (audit retention)
- **Requirements:** R-AUTHN-02, R-AUTHN-03, R-AUTHN-04, R-DEPLOY-02, R-ARCH-06

## Context

`AuthProvider` (`application/ports/identity.py`) and `Principal`
(`domain/identity/principal.py`) are the existing identity seam.
`SingleUserAuthProvider` is the only adapter: it returns one configured operator
and never inspects a credential, so there is no login, no session, and no token
flow. `RequestContext` deliberately carries primitives only — headers, client,
path — so an adapter never leaks an HTTP request object into the application
layer.

Three facts from ADR-001 shape this decision:

1. **The chosen deployment is a self-hosted, possibly air-gapped, single host.**
   No identity provider may be assumed reachable. ADR-001 §4 therefore requires a
   local, self-contained authentication path that works with zero external
   services, with OIDC as a later extension seam only.
2. **Sessions must be server-side and revocable**, because membership suspension
   or removal has to invalidate access immediately.
3. **The demo identity provider must never be selectable where real data could
   be held**, and configuration must not be able to promote a demo build by
   accident.

The classification ceiling is unclassified synthetic data only, so no decision
here depends on a compliance regime. The goal is a correct, conservative design
that does not need to be rewritten when the ceiling is raised.

## Decision

### 1. Selected approach: local credentials + server-side sessions

**The first authentication implementation is a local credential store plus
opaque, server-side sessions carried in an `HttpOnly` cookie.**

An OIDC authorization-code adapter is a **documented extension seam**, not built
now. It is added only when the authorized environment provides a reachable
internal IdP or approved egress, and it must reuse the same server-side session
store so that revocation semantics do not change with the provider.

| Approach | Verdict | Rationale |
|---|---|---|
| Local credential + server-side session | **Selected** | Works with zero external services, satisfies the air-gap target, is revocable in the database, and adds no vendor SDK |
| OIDC authorization code + server-side session | Deferred seam | Requires a reachable IdP; ADR-001 forbids assuming one. The session half is identical, so the later adapter is additive |
| Signed self-contained token (JWT) as the session | Rejected | Not revocable before expiry without a server-side denylist, which reintroduces the session store it was meant to avoid |
| HTTP Basic auth on every request | Rejected | Re-sends the password, has no logout, and cannot express idle expiry or rotation |
| In-process session dictionary | Rejected | Lost on restart, not shared across processes, and cannot revoke from the database |

Consequences for the ports: `AuthProvider` keeps its single method. Session
resolution happens inside the adapter, reading the cookie from
`RequestContext.headers` and returning a `Principal` or raising the existing
authentication error. No new HTTP-aware port is introduced.

### 2. Credential storage and password hashing

A credential record is separate from the user/profile record so that the profile
can be read without touching secret material.

| Column | Type | Notes |
|---|---|---|
| `user_id` | text, PK, FK → `users.id` | One credential per human |
| `password_hash` | text | Self-describing encoded hash (below) |
| `password_changed_at` | datetime (naive UTC) | Drives session revocation and audit |
| `failed_attempts` | integer | Consecutive failures; reset on success |
| `locked_until` | datetime, nullable | Temporary lockout window |
| `created_at`, `updated_at` | datetime (naive UTC) | Standard columns |

**Hashing: `scrypt` from the Python standard library (`hashlib.scrypt`).**

- Parameters: `n=2**14` (16384), `r=8`, `p=1`, `dklen=32`, 16-byte random salt
  from `secrets.token_bytes(16)`.
- Encoded form: `scrypt$n=16384,r=8,p=1$<salt-b64>$<derived-key-b64>`. The
  algorithm and parameters travel with the hash, so a future Argon2id upgrade is
  a verification-time branch plus a rehash-on-login, not a migration.
- Verification uses `hmac.compare_digest`. An unknown user id still performs a
  dummy hash of the same cost, so response time does not reveal whether an
  account exists.
- **No external crypto dependency is added.** `hashlib.scrypt` is backed by
  OpenSSL in the runtime image and is available offline. Argon2id is preferred in
  general, but adopting it means adding a dependency, which this ticket forbids;
  the encoded-hash format makes that a later, non-breaking change.

**Password policy (initial):** minimum 12 characters, maximum 128, no
composition rules, no periodic forced rotation. Reject a small embedded list of
obvious weak values (the product name, `password`, the demo operator name).
Credentials are never logged, returned by an API, or written to audit records.

**Login throttling:** consecutive failures increment `failed_attempts`; at 10
failures within 15 minutes the account is locked for 15 minutes
(`locked_until`). A successful login resets the counter. Lockout is per account;
a coarse per-client delay is applied by the API layer, not the domain.

### 3. Session storage

Sessions live in the database, in a `sessions` table owned by the persistence
adapter. The domain sees a session entity through a repository port; the
repository never commits.

| Column | Type | Notes |
|---|---|---|
| `id` | text, PK | Opaque random id, distinct from the token |
| `user_id` | text, FK → `users.id` | Session subject |
| `token_hash` | text, unique, indexed | SHA-256 of the raw token — the raw token is never stored |
| `created_at` | datetime (naive UTC) | Issuance time |
| `last_used_at` | datetime (naive UTC) | Throttled activity marker |
| `idle_expires_at` | datetime (naive UTC) | `last_used_at + idle window` |
| `absolute_expires_at` | datetime (naive UTC) | Fixed at issuance, never extended |
| `revoked_at` | datetime, nullable | Set on any revocation trigger |
| `revoked_reason` | text, nullable | Enumerated reason for audit |
| `user_agent_hash` | text, nullable | SHA-256 of the `User-Agent`; used only to detect a changed client, never to identify |

A database-backed store is chosen because persistence is already port-based and
dialect-portable (SQLite demo, PostgreSQL single host), because it survives a
restart, and because revocation is a single row update that every request reads.
Storing only the hash means a database read cannot yield a usable session token.

**Sessions are looked up by `token_hash`.** Because the value is a hash of a
256-bit random token, an indexed equality lookup is sufficient; no constant-time
comparison is required on this path, and the lookup does not leak which part of a
token was wrong.

### 4. Token format, entropy, and rotation

- **Format:** opaque. 256 bits from `secrets.token_urlsafe(32)` (43 URL-safe
  characters). No structure, no embedded claims, no JWT.
- **Entropy source:** the OS CSPRNG through `secrets` only. Never `random`.
- **Storage:** only `sha256(token)` is persisted. The raw token exists in the
  cookie and in memory for the duration of a request.
- **Rotation triggers:**
  - **Every successful login** issues a brand-new session id and token.
  - **Privilege change** — a membership role change or squadron move — revokes
    the existing session and issues a new one, so an old cookie cannot carry
    stale authority.
  - **Password change** revokes every other session for that user.
  - Ordinary requests do **not** rotate the token. Rotation on every request
    breaks concurrent tabs and provides no additional protection over an
    `HttpOnly` cookie on a controlled network.

`last_used_at` and `idle_expires_at` are refreshed at most once every 5 minutes
per session to avoid a database write on every request.

### 5. Expiry

| Window | Value | Behaviour |
|---|---|---|
| Idle timeout | **30 minutes** | Sliding, refreshed on activity (throttled to 5-minute granularity) |
| Absolute lifetime | **12 hours** | Fixed at issuance; never extended by activity |
| Lockout | 15 minutes after 10 failed logins in 15 minutes | Blocks credential verification only |

Rationale: 30 minutes idle is short enough that an unattended terminal on a
shared watch floor does not stay authenticated, and long enough for normal work
between interactions. 12 hours absolute bounds a session to roughly one watch
period and forces a fresh credential check once a day. Both are configuration
values with these defaults; changing them is a configuration change, not an ADR
amendment, but the defaults are what the implementation tickets build and test.

Expiry is enforced **on read**: a session whose `idle_expires_at` or
`absolute_expires_at` has passed is treated as invalid and marked revoked with
reason `expired`. Cleanup of old rows is a maintenance task, not part of the
request path.

### 6. Cookie strategy

| Attribute | Value |
|---|---|
| Name | `ready_room_session`; `__Host-ready_room_session` when `Secure` is on |
| `HttpOnly` | Always |
| `Secure` | Always, except the loopback demo profile over plain HTTP |
| `SameSite` | `Lax` |
| `Path` | `/` |
| `Domain` | Omitted (host-only cookie) |
| `Max-Age` | Matches `absolute_expires_at` |

- **`__Host-` prefix in secure deployments.** It forces `Secure`, `Path=/`, and
  the absence of `Domain`, which prevents a subdomain from overwriting the
  cookie.
- **`SameSite=Lax`, not `Strict`.** The SPA is same-origin behind nginx, so Lax
  is sufficient, and it keeps a top-level navigation after login working. The
  cost is that a top-level cross-site `GET` still carries the cookie, which is
  why no state-changing operation is allowed on `GET`.
- **`Secure` decision source.** The application does not guess from the request
  host. `cookie_secure` is derived from configuration (`environment`), with the
  loopback demo profile as the only case where it is off. If a reverse proxy
  terminates TLS, the deployment configuration sets `cookie_secure=true`; the
  application does not trust `X-Forwarded-Proto` from an arbitrary client.
- **The cookie value is the raw token.** Nothing else is stored client-side: no
  role, no user id, no expiry, no squadron. All of that is read server-side, so a
  client cannot assert its own authority.

### 7. CSRF strategy

Two independent checks on every state-changing request (`POST`, `PUT`, `PATCH`,
`DELETE`):

1. **A required custom header** — `X-Ready-Room-Request: 1`. A cross-origin
   HTML form cannot set a custom header, and a cross-origin `fetch` that sets one
   triggers a CORS preflight, which the deployment does not answer. A missing or
   wrong header is a `403` before any state is read or changed.
2. **An `Origin` check** — when an `Origin` header is present it must match the
   configured application origin; a mismatched origin is a `403`. `SameSite=Lax`
   remains the primary defence; these checks are defence in depth for the
   loopback demo profile where `Secure` is off.

No double-submit token is used: it adds a second cookie and a rotation problem
without adding protection over a required custom header plus `SameSite=Lax` on a
same-origin SPA. CORS is not enabled; the SPA reaches the API same-origin through
nginx, and the Vite dev proxy preserves that.

`GET` requests are read-only by contract. A `GET` that would change state is a
defect, not a CSRF exception.

### 8. Revocation and logout semantics

Revocation is a row update (`revoked_at`, `revoked_reason`) checked on every
principal resolution. The reasons are enumerated so audit can distinguish them:

| Trigger | Scope | Reason |
|---|---|---|
| Logout | Current session | `logout` |
| Logout everywhere / admin revoke | All sessions for the user | `logout_all` |
| Password change | All sessions except the one performing the change | `password_change` |
| Membership suspended or removed | All sessions for the user | `membership_inactive` |
| Role or squadron change | Current session (then reissue) | `privilege_change` |
| Account deactivated | All sessions for the user | `account_inactive` |
| Idle timeout | That session | `expired_idle` |
| Absolute timeout | That session | `expired_absolute` |
| Suspected compromise | All sessions for the user | `compromised` |

Logout clears the cookie and revokes the row. Logout is idempotent: revoking an
already-revoked session succeeds without error. A revoked session resolves to an
anonymous result and the API returns `401`, never a downgraded or demo identity.

**Membership coupling.** A session is valid only while its user's membership is
`active`. ADR-003 defines the membership states; this ADR fixes the rule that
every state other than `active` — including a suspended, removed, or not-yet-
accepted membership — denies access. The `SessionAuthProvider` checks membership
on resolution so suspension takes effect on the next request, not at the next
login.

### 9. Production guard for the demo identity provider

`SingleUserAuthProvider` must be impossible to select where real data could be
held. Three enforcement points, all failing closed:

1. **Environment is explicit.** `READY_ROOM_ENVIRONMENT` must be one of `demo`,
   `test`, or `production`. There is no silent default that promotes a build:
   startup fails if the value is missing in a non-development launch, and the
   accepted set is validated.
2. **Startup validation.** Configuration validation raises a startup error when
   `auth_provider == "single_user"` and `environment not in {"demo", "test"}`.
   The application does not start; it does not start and warn.
3. **Registry guard.** `build_auth_provider` repeats the check and refuses to
   construct `SingleUserAuthProvider` outside `demo`/`test`, so a direct call
   cannot bypass the config layer.

In addition:

- The demo profile logs a prominent startup warning that identity is unverified.
- `single_user` is documented in `config.py` as demo/test-only.
- A production deployment must set `READY_ROOM_AUTH_PROVIDER=session`
  explicitly. There is no fallback from a missing value to `single_user` in
  production.

This satisfies R-DEPLOY-02: the demo adapter cannot leak into production by
configuration accident.

### 10. Authentication outcomes and error contract

- **Unauthenticated** (no cookie, unknown token, expired, revoked, inactive
  membership) → `401` with the existing typed error payload and no detail that
  distinguishes the cases to an unauthenticated caller.
- **Authenticated but not permitted** → `403`, unchanged from the current
  authorization behaviour. Authentication never implies authorization.
- **Login failure** → one uniform `401` message for unknown user, wrong
  password, and locked account, with a `Retry-After` on lockout. No response
  reveals whether an account exists.
- **Login success** → `204` or a `UserRead` body, with `Set-Cookie` carrying the
  new session. The password is never echoed.
- **Validation errors** on request shape remain `422`, per the API conventions in
  `AGENTS.md`.

### 11. Audit coverage

Authentication events are appended to the audit/activity history defined by
ADR-011: `login_succeeded`, `login_failed`, `logout`, `session_revoked`,
`password_changed`, `account_locked`. Each records actor (user id when known),
action, outcome, client address, and a timestamp. **No token, cookie value,
password, or hash is ever recorded.** Failed logins for unknown users record the
attempted identifier only if it is needed for lockout, never the submitted
password.

## Consequences

**Positive**

- Authentication works with zero external services, which is the only design
  that satisfies the air-gap target in ADR-001.
- Server-side sessions make membership suspension effective on the next request,
  which Phase 1's exit criteria require.
- Opaque tokens with hashed storage mean a database read cannot mint a session,
  and there is no token format to keep compatible.
- The OIDC seam is additive: it changes how a session is created, not how it is
  validated or revoked.
- No new dependency is added; `hashlib.scrypt` and `secrets` are stdlib.

**Negative / accepted trade-offs**

- Every authenticated request costs one indexed session lookup and, on the
  throttled path, one update. Acceptable for a single-host deployment; a read
  cache would be premature.
- `scrypt` at `n=2**14` is deliberately slow at login. That is the point, but it
  caps login throughput; the throttling rules assume a low login rate.
- 30-minute idle expiry will occasionally interrupt a long, uninterrupted
  briefing review. The alternative — a long idle window — is worse on a shared
  watch floor.
- There is no self-service password reset in the first cut; an administrator
  resets a password. That is a deliberate scope limit, tracked as an open
  question.

**Risks**

- If the authorized environment later mandates MFA or an enterprise IdP, the
  credential path is replaced while the session store and revocation semantics
  carry over unchanged.
- Running more than one backend replica would require the session store to be
  shared; it already is, because it is the database, but the throttled
  `last_used_at` update would then contend. Not a concern on the chosen
  single-host target.
- A compromised database yields password hashes and session hashes, not usable
  tokens or passwords. `scrypt` raises the offline cracking cost; Argon2id would
  raise it further, which is why the encoded format anticipates it.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| OIDC-first authentication | Requires a reachable IdP; ADR-001 forbids assuming one on a controlled or air-gapped host |
| JWT or signed cookie as the session | Cannot be revoked before expiry without a server-side store, which defeats the purpose |
| Session data in an in-memory store | Lost on restart, not revocable across processes, and invisible to the persistence port |
| Argon2id password hashing now | Stronger, but needs a new dependency, which this ticket's scope forbids; the encoded hash format makes it a later drop-in |
| `SameSite=Strict` | Breaks the first top-level navigation after login for no meaningful gain over `Lax` plus a required custom header |
| Stateless CSRF tokens | Adds a cookie and a rotation problem on a same-origin SPA that a required custom header already protects |
| Long-lived "remember me" tokens | Extends the compromise window on a shared terminal with no requirement asking for it |

## Open questions

These do not block the Phase 1 implementation tickets; each is deferred with a
named owner and an explicit default.

| # | Question | Default until decided | Owner |
|---|---|---|---|
| A1 | Is self-service password reset required, or is administrator reset sufficient? | Administrator reset only; no email path, since outbound email is disabled by ADR-001 | Product owner |
| A2 | Is MFA required before the classification ceiling is raised? | Not implemented; the credential record has room for a second factor | Authorizing Official |
| A3 | Should the idle timeout differ for administrative roles? | One window for all roles | Product owner |
| A4 | How long are revoked session rows retained? | 30 days, then purged; audit entries follow ADR-011 retention | Records Manager |
| A5 | Is a service-account or API-token path needed for automation? | No; agent delegation is ADR-008's problem, not a human session | Engineering |

**Confirmation status (2026-11-24):** the product owner accepted A1–A5 as
written. Named-owner confirmations remain non-blocking and can amend these
defaults later.

## Validation

Documentation-only change: this ADR adds `docs/adr/ADR-002-authentication-session.md`
and updates the ADR index. No application code, configuration default,
dependency, or test was modified. `git diff --stat` confirms only files under
`docs/adr/` changed. The backend and frontend baselines were run before and after
the change and remained green; the commands and results are recorded on issue #4.

Each acceptance criterion maps to a section:

| Acceptance criterion | Section |
|---|---|
| One approach selected with rationale tied to ADR-001 | §1 |
| Session storage, expiry, rotation, revocation specified | §3, §4, §5, §8 |
| Cookie and CSRF strategy specified | §6, §7 |
| Production guard for the demo provider specified | §9 |
| P1-09..P1-12 can proceed without further design questions | §2, §3, §8, §10, plus the open-question defaults |
