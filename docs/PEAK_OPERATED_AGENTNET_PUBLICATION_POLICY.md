# Peak-Operated AgentNet Publication Policy (Phase 34)

This document records Peak's AgentNet publication authority model. **It is policy only — Phase 34
implements no publication.** AgentNet publication remains future/deferred.

## Peak is the authorized publisher; clients do not publish

- **The client authorizes Peak, in the consulting agreement, to act as the authorized capsule/node
  publisher** on the client's behalf.
- **Clients do not operate any AgentNet publishing tools.** Publishing is part of Peak's managed
  consulting service.
- **Peak operates all publishing workflows as a managed service**: capsule/node publication
  preparation, validation, approval routing, publishing, updating, supersession, revocation, and
  audit logging — all through controlled internal publication gates, stored authorization checks,
  and audit receipts.

## Hard prohibitions

- **No client-facing AgentNet publisher UI.**
- **No client-held publishing credentials.**
- **No client-operated resolver publication tools.**
- **No direct client publication path.**

## Publication remains disabled in Phase 34

- **Publication remains disabled until future controlled publication gates are built.** No AgentNet
  publish operation, resolver publication call, or capsule publication path exists in the code.
- The existing narrow controlled writers (through Phase 34's intake-note writer) persist
  **review-gated, non-final** records only. Every record's `publication_allowed`,
  `capsule_candidate_ready`, and `client_facing_approved` flags are stored **false**; no writer
  approves, publishes, or executes anything.

## Requirements for future publication gates (not built here)

When a future phase implements Peak-operated publication, each publication gate must:

- verify **stored** Client/Engagement publication authority and `authorization_scope` (the stored
  Engagement remains the authorization anchor; caller-supplied scope alone is never sufficient);
- verify the resolver target, review status, and explicit **Peak** approval before any publish;
- distinguish publish / update / supersede / revoke as separate controlled actions on an explicit
  allowlist (no generic publish action);
- emit **auditable, leak-free receipts** (no credentials, DSNs, raw SQL, raw client content, or
  stack traces) — consistent with the existing controlled-writer receipt discipline;
- never expose a client-facing publisher path and never hold publishing credentials on the client
  side.

Until those gates exist and pass their own governance validation, **AgentNet publication is not
available** and no code path performs it.
