# Database Access and Audit

Planned access-control and audit model for Peak's controlled engagement database.
**Planning only — no database, access-control code, or stored data is created.** AgentNet
grounding is **intended future architecture, not implemented**.

## Access-control assumptions

- The database is **private and internal** to Peak; there is **no client data in Git** and
  no public access. It holds live client data only for **authorized engagement work**.
- Access is **scoped by identity fields**: `owner_id`, `client_id`, `engagement_id`. A
  principal sees only the clients/engagements it is authorized for.
- Every record carries an `authorization_scope` that gates use and disclosure (see
  [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md)); `revoked` blocks access.
- Least privilege by default; elevation (e.g. client-facing approval, capsule publication)
  is an explicit governed action, not a default.

## Roles

| Role | Can | Cannot |
| --- | --- | --- |
| **Peak admin** | Manage clients/engagements, roles, authorization scopes | Bypass human-review gates |
| **Peak consultant** | Create/edit engagement records; run prompt contracts by hand; advance review up to `consultant_reviewed` | Set `qa_reviewed`/`approved_internal` alone where separation is required; approve client-facing without the gate |
| **QA reviewer** | Set `qa_reviewed`/`approved_internal`; record `ReviewRecord`s | Author the work they review (separation of duties) |
| **Client approver** *(future)* | Provide client-side approvals within their engagement | Access other engagements/clients |
| **Agent worker** *(future)* | Draft records defaulting to `draft`/`needs_review` under `agent_run_id` | Approve, verify, or publish anything (see limits below) |
| **Resolver publisher** *(future)* | Execute governed capsule publication after approval | Publish without an approved `CapsulePublicationCandidate` |

## Audit fields (every record)

- `created_at`, `created_by`
- `updated_at`, `updated_by`
- `source_reference_ids` — `SourceSystemReference` ids the record derives from
- `evidence_ids` — `EvidenceReference` ids grounding the record
- `review_status` — governance review state
- `lifecycle_status` — lifecycle state
- `authorization_scope` — how the record may be used
- `agent_run_id` — set where an agent/worker produced or edited the record

These make every record **traceable**: who created/changed it, from what sources and
evidence, under what authorization, in what review/lifecycle state, and (if applicable)
which agent run produced it. As of Phase 11 these audit and governance fields are **real
columns** on the SQLAlchemy models ([`../peak/db/base.py`](../peak/db/base.py)),
never hidden inside `details_json`.

## Human review gates

- No record becomes client-facing without an explicit human `client_facing_approved`
  (see [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md)).
- Financial impact reaches `verified`/`client_facing_approved` only after finance/human
  review.
- Resolver capsules are activated/promoted/published only through governance approval.
- Separation of duties: reviewers should not approve their own authored work where the
  process requires independence.

## Agent permission limits

For any future agent worker:

- **No agent may mark a record `client_facing_approved`.**
- **No agent may publish capsules** (or approve a `CapsulePublicationCandidate`) **without
  human/governance approval.**
- **No agent may verify financial impact without human review** (agents may reach at most
  `calculated`/`finance_review_needed`).
- **No agent may promote a capsule to methodology** — it may only *propose* a
  `methodology_candidate`.
- Agent-generated records **default to `draft` or `needs_review`** and carry an
  `agent_run_id` for provenance; advancement happens only through the human gates above.

These limits are **contract-level** and human-enforced; no agent runtime exists yet. The
Phase 13 scaffold in [`../peak/agents/`](../peak/agents/) encodes them as deterministic
pre-execution checks around a no-op mock executor (no live call, output defaults to
`draft`/`needs_review`); the provenance record it would eventually write is described in
[`AGENT_RUN_RECORDS.md`](AGENT_RUN_RECORDS.md). See
[`AGENT_EXECUTION_HARNESS.md`](AGENT_EXECUTION_HARNESS.md).

The Phase 14 **Evidence Normalization Worker** ([`../peak/workers/`](../peak/workers/))
applies the same posture to a production-shaped worker: its output is review-gated
(`draft`/`needs_review`, non-authoritative, non-client-facing) and it performs **no
database write** — a future governed writer persists reviewed records under these access
and audit rules. See [`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md).

The Phase 15 **QA / Review Gate** ([`../peak/review/`](../peak/review/)) is where a QA
reviewer's decision on such output is computed — production-shaped but **no-side-effect**.
`approve_internal` means internal reliance only; a review decision may never create
client-facing approval, verify financial impact, or publish a capsule. It writes nothing —
there are **no stored review records** in this phase — and a future governed writer would
persist the decision as the `ReviewRecord` above under these same access and audit rules.
See [`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md) and [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md).

The Phase 16 **Review Persistence Boundary** ([`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md))
prepares that future `ReviewRecord` write — **DB-aware but not DB-writing**. It maps a
permitted `ReviewGateResult` into a `ReviewRecordDraft` and a no-op `ReviewWritePlan`
targeting `review_records`, but opens no DB connection and performs **no live database
read/write**; a future controlled-DB writer executes the plan under these rules. A
**critical access rule** lives here: a DB-backed review must load the subject record's
**stored** `authorization_scope` from the controlled DB and require
`request.authorization_scope == subject.stored_authorization_scope` — owner/client/engagement
matching is necessary but not sufficient. The persisted `ReviewRecord` should record both
the stored scope matched and the request scope presented, so the scope check is auditable.
See [`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md).

The Phase 17 **Controlled DB Writer Boundary** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md),
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)) is the generic front door
every future controlled write passes through — **DB-aware but not DB-writing**. Before any
plan is built it enforces a **table/action allowlist** (only `evidence_references`,
`engagement_records`, `review_records`, `agent_run_records`, `source_ingestion_records`, and
`capsule_publication_candidates` — never `clients` / `engagements` / `financial_impact_estimates` /
`resolver_capsule_records`), requires an `idempotency_key` for write safety, and re-runs the
stored-scope check (`request.authorization_scope == subject.stored_authorization_scope`;
identity matching necessary but not sufficient). Publish / client-facing-approve /
verify-financial / delete / migrate / seed / raw_sql actions are rejected, so the future
writer maps only allowlisted actions to parameterized operations under these audit rules —
it opens no connection and runs no SQL in this phase. A future writer would persist a
`ControlledWriteAuditDraft` (recording table, action, requester/role, idempotency key,
decision, and reasons) for each attempt.

The Phase 18 **Evidence Persistence Mapping** ([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
[`EVIDENCE_WRITE_PLAN_POLICY.md`](EVIDENCE_WRITE_PLAN_POLICY.md)) is the first domain to use
that front door: it maps a Phase 14 normalized evidence record to a `ControlledWriteRequest`
for `evidence_references` / `create_draft`. Because the new evidence has **no stored row
yet**, its write authority is anchored to the **stored parent/source/engagement subject** —
the future writer loads that subject's `stored_authorization_scope` and requires
`request.authorization_scope == subject.stored_authorization_scope` (identity matching
necessary but not sufficient). Evidence workers still do not write directly to the DB, and
the review gate (`draft` / `needs_review`, non-authoritative, non-client-facing) is preserved
into the draft the writer would persist.

The Phase 19 **Agent Run Persistence Mapping** ([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md),
[`AGENT_RUN_WRITE_PLAN_POLICY.md`](AGENT_RUN_WRITE_PLAN_POLICY.md)) is the second domain to
use that front door: it maps a Phase 13 agent run output (`AgentTaskResult` +
`AgentRunDraft`) to a `ControlledWriteRequest` for `agent_run_records` /
`create_agent_run_record`. As with evidence, the new agent run record has **no stored row
yet**, so its write authority is anchored to the **stored engagement/client/subject** — the
future writer loads that subject's `stored_authorization_scope` and requires
`request.authorization_scope == subject.stored_authorization_scope` (identity matching
necessary but not sufficient). Agent execution still does not write directly to the DB, and
the no-side-effect posture (`draft` / `needs_review`, all call/write flags false) is preserved
into the draft the writer would persist as provenance.
