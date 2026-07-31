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

---

## Phase 35 — policy unchanged, publication still deferred

The Phase 35 managed-record workflow integration layer **does not alter this policy** and adds no
publishing code, no resolver call, and no capsule publication path. AgentNet publication remains
Peak-operated and deferred behind future controlled publication gates. See
[`WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md`](WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md).

---

## Phase 36 — policy unchanged, publication still deferred

The Phase 36 internal assessment report planning boundary **does not alter this policy** and adds no
publishing code, no resolver call, and no capsule publication path. It may *name* items that might
later become capsule candidates (`future_capsule_candidate_items`), but `capsule_candidate_ready`
and `publication_allowed` remain false and no capsule candidate is created or published. See
[`INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md`](INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md).

---

## Phase 37 — policy unchanged, publication still deferred

The Phase 37 internal-assessment-report-draft writer **does not alter this policy** and adds no
publishing code, no resolver call, and no capsule publication path. It may persist
`future_capsule_candidate_items` as forward-looking placeholders, but `capsule_candidate_ready` and
`publication_allowed` remain false on every stored row and no capsule candidate is created or
published. See
[`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).

---

## Phase 38 — policy unchanged, publication still deferred

The Phase 38 internal-report-review-packet writer **does not alter this policy** and adds no
publishing code, no resolver call, and no capsule publication path. It may persist
`future_capsule_candidate_items` as forward-looking placeholders, but `capsule_candidate_ready` and
`publication_allowed` remain false on every stored row and no capsule candidate is created or
published. See
[`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md).
