# Review Decision Model (Phase 15)

The decisions a Peak reviewer may request in the QA / Review Gate, the checks each
requires, and the governance state each produces. This is a **production-shaped but
no-side-effect** contract: it defines vocabulary and state effects; it **persists nothing
and confers no final authority**. See [`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md).

## Allowed decisions

| Decision | Meaning | Next `review_status` | Next `lifecycle_status` | `authoritative` |
| --- | --- | --- | --- | --- |
| `approve_internal` | Rely on the output **internally only** | `approved_internal` | unchanged (`active`) | `true` *(internal use only)* |
| `reject` | Do not rely on the output | `rejected` | `active` unless the subject says otherwise | `false` |
| `return_for_revision` | Send back to the author to fix | `needs_review` | unchanged | `false` |
| `supersede` | Replace with a better record | `superseded` | `superseded` | `false` |
| `keep_needs_review` | Leave under review | `needs_review` | unchanged | `false` |

State names use the existing Phase 9 governance vocabulary
([`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md), `peak/db/enums.py`). There is no dedicated
`needs_revision` state, so `return_for_revision` maps to `needs_review` and records the
revision intent in the decision reasons/warnings. `superseded` exists in both the
`ReviewStatus` and `LifecycleStatus` families and is used for both on `supersede`.

## Prohibited decisions

These are **out of scope for Phase 15** and are rejected outright by governance:

- `client_facing_approve` — client-facing approval remains separate and future.
- `publish_capsule` — capsule publication remains separate and future.
- `verify_financial_impact` — financial impact verification remains separate and future.
- `approve_authoritative_external` — external authoritative approval remains separate and
  future.

No allowed decision can produce any of these effects: no review decision may create
client-facing approval, publish a capsule, or verify financial impact. `client_facing_approved`
and `capsule_candidate_ready` stay `false` in **every** case.

## Required checklist for `approve_internal`

`approve_internal` is the only decision with a full pre-condition. All of the following
must be `true` (governance rejects the request otherwise):

- `source_traceable`
- `scope_valid`
- `evidence_complete`
- `confidence_acceptable`
- `no_contradiction_flags`
- `no_client_facing_claims`
- `no_financial_verification_claim`
- `no_capsule_publication_request`
- `required_human_review_completed`

`reject` and `return_for_revision` **may** proceed with an incomplete checklist — but any
missing items or checklist warnings are surfaced in the result's reasons/warnings, never
silently dropped.

## State effects for each decision

- **`approve_internal`** — `review_status = approved_internal`, `output_status = reviewed`,
  `authoritative = true` (**internal reliance only**). Not client-facing; not a capsule
  candidate.
- **`reject`** — `review_status = rejected`; lifecycle stays `active` unless the subject's
  current lifecycle already indicates otherwise.
- **`return_for_revision`** — `review_status = needs_review` (no `needs_revision` state
  exists); a follow-up revision is expected.
- **`supersede`** — `lifecycle_status = superseded` and `review_status = superseded`; the
  original is not deleted.
- **`keep_needs_review`** — `review_status = needs_review` is preserved; no advancement.

## Authority boundaries

- `approve_internal` grants **internal reliance only**. It is never client-facing.
- **No automatic client-facing authority** — client-facing approval is a separate future
  human gate; a review decision cannot create it.
- Financial-impact verification and capsule publication are separate future gates; the
  review gate touches neither.

## Human reviewer role

A named human reviewer (`requested_by`, `reviewer_role`, `authorization_scope`) is required
on every request. The gate computes a **candidate** decision deterministically; the human
reviewer owns it. Separation of duties from [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)
still applies — e.g. a reviewer should not approve their own authored work — and is enforced
by the future controlled-DB writer, not by this scaffold.

## Audit expectations for a future DB write

When the controlled database integration lands, a governed writer will persist each decision
as a **`ReviewRecord`** ([`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md),
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)) carrying the subject
reference, the decision, reviewer identity, authorization scope, reasons/warnings, and
timestamps for audit. **No such write happens in Phase 15** — there are **no stored review
records** in this phase.
