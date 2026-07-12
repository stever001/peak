# Governance States

The allowed **state families** for live engagement records, evidence, financial impact
estimates, resolver capsules, source systems, and client-facing approval. These states
let future Peak agents/AI create drafts, label evidence correctly, distinguish reported
vs. verified information, prevent unsupported financial claims, prevent premature
client-facing output, keep resolver capsules governed, and preserve human review gates.

**Contracts, not data.** These are enum contracts defined in
[`../schemas/governance-state.schema.json`](../schemas/governance-state.schema.json)
(master), plus [`authorization-scope`](../schemas/authorization-scope.schema.json),
[`review-status`](../schemas/review-status.schema.json), and
[`lifecycle-status`](../schemas/lifecycle-status.schema.json). **No instances are stored
in the repo.** Transitions and gates are in
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md). AgentNet grounding of governed records is
**intended future architecture, not implemented**.

## A. AuthorizationScope

- **Purpose:** how a record may be used and by whom.
- **Values:** `engagement_authorized`, `internal_peak_only`, `client_private`,
  `client_facing_candidate`, `client_facing_approved`, `methodology_candidate`,
  `peak_methodology`, `fixture_test`, `revoked`.
- **Allowed usage:** gates reuse and disclosure. `client_facing_approved` and
  `peak_methodology` are reached only by human/governance decision; `revoked` blocks use.
- **Applies to:** `EngagementRecord`, `EvidenceReference`, `FinancialImpactEstimate`,
  `ResolverCapsuleRecord`, `SourceSystemReference`.
- **Agents must respect:** intake/discovery/evidence/reporting/proposal/qa/learning
  agents may only *propose* candidate scopes; they may not set `client_facing_approved`
  or `peak_methodology`.

## B. ReviewStatus

- **Purpose:** governance review state of any record.
- **Values:** `draft`, `needs_review`, `consultant_reviewed`, `qa_reviewed`,
  `approved_internal`, `client_facing_approved`, `rejected`, `superseded`, `archived`.
- **Allowed usage:** the universal review axis; drives the general review transition.
- **Applies to:** every controlled-storage record.
- **Agents must respect:** agent output defaults to `draft` or `needs_review`; only humans
  reach `consultant_reviewed` and beyond, and only humans set `client_facing_approved`.

## C. LifecycleStatus

- **Purpose:** lifecycle state of a record.
- **Values:** `active`, `pending`, `draft`, `superseded`, `revoked`, `archived`,
  `deleted_reference_only`.
- **Allowed usage:** tracks whether a record is live, retired, or reduced to a governance
  reference. `deleted_reference_only` means the payload is gone; only a reference remains.
- **Applies to:** every controlled-storage record.
- **Agents must respect:** agents create `draft`/`pending`; supersede/revoke/delete are
  governed actions.

## D. EvidenceStatus

- **Purpose:** the state of an `EvidenceReference`, incl. reported-vs-verified labeling.
- **Values:** `collected`, `source_labeled`, `needs_verification`, `verified`,
  `disputed`, `superseded`, `excluded`, `archived`.
- **Allowed usage:** enforces the evidence-first discipline — evidence is `collected`,
  then `source_labeled`, and only reaches `verified` after checking against data.
- **Applies to:** `EvidenceReference`.
- **Agents must respect:** evidence agents may set up to `needs_verification`; humans (or
  a verification step) reach `verified`; `disputed`/`excluded` require a reason.

## E. FinancialImpactStatus

- **Purpose:** the state of a `FinancialImpactEstimate`; prevents unsupported financial
  claims.
- **Values:** `not_assessed`, `reported`, `estimated`, `calculated`,
  `finance_review_needed`, `finance_reviewed`, `verified`, `rejected`,
  `client_facing_approved`.
- **Allowed usage:** distinguishes a *reported* figure from an *estimated/calculated* one,
  and gates `verified`/`client_facing_approved` behind finance/human review.
- **Applies to:** `FinancialImpactEstimate`.
- **Agents must respect:** agents may reach up to `calculated`/`finance_review_needed`;
  they may **not** set `verified` or `client_facing_approved`. No invented ROI.

## F. ResolverCapsuleStatus

- **Purpose:** the state of a `ResolverCapsuleRecord`; keeps resolver capsules governed.
- **Values:** `draft_capsule`, `private_client_capsule`, `reviewed_private`,
  `active_private`, `methodology_candidate`, `approved_methodology`, `superseded`,
  `revoked`, `archived`.
- **Allowed usage:** private client capsules stay private; promotion to reusable
  methodology requires abstraction + governance approval.
- **Applies to:** `ResolverCapsuleRecord`.
- **Agents must respect:** agents may create `draft_capsule` and *propose*
  `methodology_candidate`; they may **not** activate, approve, publish, or promote
  capsules.

## G. SourceSystemAccessStatus

- **Purpose:** access state for a client source system.
- **Values:** `not_requested`, `requested`, `granted`, `partial`, `denied`, `expired`,
  `revoked`.
- **Allowed usage:** tracks whether Peak is authorized to read a source; `expired`/
  `revoked` block further use.
- **Applies to:** `SourceSystemReference`.
- **Agents must respect:** agents may record `requested`; granting/denying/revoking is a
  client/governance action.

## H. ClientFacingApprovalStatus

- **Purpose:** whether a deliverable may go to a client; prevents premature client-facing
  output.
- **Values:** `not_client_facing`, `client_facing_candidate`, `requires_review`,
  `approved_for_client`, `rejected_for_client`, `withdrawn`.
- **Allowed usage:** the explicit gate for client disclosure.
- **Applies to:** reports, proposals, financial estimates, and any candidate deliverable.
- **Agents must respect:** agents may mark `client_facing_candidate` / `requires_review`
  only; **only humans** set `approved_for_client`.

## Cross-cutting rule

Every governed record carries at least the three universal axes — `authorization_scope`,
`review_status`, `lifecycle_status` — plus its domain-specific family where applicable.
Agent-generated output defaults to the safest state (`draft` / `needs_review` /
`not_client_facing`) and advances only through the gates in
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md).
