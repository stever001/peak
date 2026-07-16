# Database Record Model

Planned record groups for Peak's controlled engagement database. **No stored data —
records live in controlled MySQL storage, never in Git, and no actual records exist.**
Shapes reuse the architecture contracts in [`../schemas/`](../schemas/) and the governance
states in [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md). As of **Phase 11**, the core
groups are realized as **SQLAlchemy models** ([`../peak/db/models.py`](../peak/db/models.py))
with an Alembic migration that defines **schema only** — see
[`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md). AgentNet grounding is **intended future
architecture, not implemented**.

Legend for each group:
- **Governance states** — which state families a record carries (see
  [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md)).
- **Capsule-ready?** — whether the record may become a resolver-capsule candidate (see
  [`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md)).
- **Client-facing?** — whether it may reach a client, and only after human approval.

## Identity & engagement

### Client
- **Purpose:** the client organization.
- **Key fields:** `client_id`, organization label, sensitivity defaults.
- **Relationships:** parent of Engagements.
- **Governance states:** authorization, lifecycle.
- **Capsule-ready?** No (identity, not knowledge). **Client-facing?** N/A.

### Engagement
- **Purpose:** a unit of authorized work for a client.
- **Key fields:** `engagement_id`, `client_id`, authorization scope, status.
- **Relationships:** parent of EngagementRecords/packets and most other records.
- **Governance states:** authorization, review, lifecycle.
- **Capsule-ready?** No. **Client-facing?** N/A.

### EngagementRecord
- **Purpose:** the top-level engagement metadata record
  ([`engagement-record.schema.json`](../schemas/engagement-record.schema.json)).
- **Key fields:** `engagement_id`, `client_id`, `data_class`, `review_status`,
  `authorization_scope`, packet/source ids.
- **Governance states:** authorization, review, lifecycle.
- **Capsule-ready?** No. **Client-facing?** Only summaries, after approval.

### EngagementPacket
- **Purpose:** the first-thread assessment bundle
  ([`engagement-packet.schema.json`](../schemas/engagement-packet.schema.json)).
- **Key fields:** `packet_id`, `client_intake`, nested evidence/interviews/observations.
- **Relationships:** aggregates the discovery records below.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** Indirectly (its verified parts). **Client-facing?** After QA + approval.

## Discovery & evidence

### EvidenceReference
- **Purpose:** traceability primitive
  ([`evidence-reference.schema.json`](../schemas/evidence-reference.schema.json)).
- **Key fields:** `evidence_id`, type, source, `summary`, reliability,
  `sensitive_data_flag`, evidence status.
- **Governance states:** authorization, review, lifecycle, **EvidenceStatus**.
- **Phase 21 columns:** `output_status` (governance-relevant review-gate status, a real
  column), `idempotency_key`, and `payload_fingerprint`, with a unique index
  `uq_evidence_references_idem` over `(owner_id, client_id, engagement_id, idempotency_key)`
  (migration `003_evidence_idempotency`). Normalized detail (title, areas, source location,
  confidence) lives in `details_json`.
- **Capsule-ready?** **Yes, when `verified`** and source-labeled. **Client-facing?** As cited support, after approval.
- **Produced by (future):** the Evidence Normalization Worker drafts these as review-gated
  `NormalizedEvidenceRecord`s (`draft`/`needs_review`, non-authoritative) — see
  [`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md) and
  [`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md).
- **Persistence planned by:** the **Phase 18 Evidence Persistence Mapping**
  ([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
  [`../peak/evidence/`](../peak/evidence/)) maps a normalized record into an
  `EvidencePersistenceDraft` and a Phase 17 `ControlledWriteRequest` targeting this
  `evidence_references` table (`create_draft`) — DB-free.
- **Persistence executed by:** the **Phase 21 Evidence Controlled Writer**
  ([`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md),
  [`../peak/db/evidence_writer.py`](../peak/db/evidence_writer.py)) creates exactly one
  review-gated row. Write authority is anchored to the stored `Engagement` row, re-loaded
  from the DB at write-time (`request.authorization_scope == engagement.authorization_scope`;
  identity matching necessary but not sufficient — the mapping snapshot is not trusted). A
  required `idempotency_key` is DB-enforced (replay returns the existing row; a conflicting
  key is denied). The writer stamps server-controlled `id` / `created_at`, never updates or
  deletes, and has no LLM/AgentNet/connector/network/client-facing/financial/capsule side
  effect.

### SourceSystemReference
- **Purpose:** pointer to a client source system/location
  ([`source-system-reference.schema.json`](../schemas/source-system-reference.schema.json)).
- **Key fields:** `source_reference_id`, `engagement_id`, `source_type`,
  `authorization_scope`, `sensitivity_class`, `access_status`.
- **Governance states:** authorization, review, lifecycle, **SourceSystemAccessStatus**.
- **Capsule-ready?** **Yes** (as grounding references). **Client-facing?** Rarely; internal.

### StakeholderInterview
- **Purpose:** structured interview
  ([`stakeholder-interview.schema.json`](../schemas/stakeholder-interview.schema.json)).
- **Key fields:** `interview_id`, `related_intake_id`, claims (as claims), quantified impacts (as reported).
- **Governance states:** review, lifecycle.
- **Capsule-ready?** Only abstracted/verified derivatives. **Client-facing?** After approval.

### VisualObservation
- **Purpose:** walk-around observation
  ([`visual-observation.schema.json`](../schemas/visual-observation.schema.json)).
- **Key fields:** `observation_id`, `related_intake_id`, severity, evidence refs.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** As verified operational facts. **Client-facing?** After approval.

### WorkflowObservation
- **Purpose:** how a process actually runs
  ([`workflow-observation.schema.json`](../schemas/workflow-observation.schema.json)).
- **Key fields:** `observation_id`, `workflow_area`, current state, gap, control risk.
- **Relationships:** basis for **workflow maps** used in capsulization.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** **Yes** (workflow maps), when approved. **Client-facing?** After approval.

### InventorySystemProfile
- **Purpose:** the client's inventory systems/data environment
  ([`inventory-system-profile.schema.json`](../schemas/inventory-system-profile.schema.json)).
- **Key fields:** systems, source of truth, integrations, data-quality concerns, access status.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** **Yes** (system/inventory policy facts), when approved. **Client-facing?** After approval.

## Findings & impact (candidate shapes)

### ControlGap
- **Purpose:** a missing/weak internal control.
- **Key fields:** `control_gap_id`, description, control type, exposure, evidence refs.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** **Yes**, when approved. **Client-facing?** After approval.

### OperationalRisk
- **Purpose:** a risk to inventory operations.
- **Key fields:** `risk_id`, category, likelihood/impact indicators, evidence refs.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** When approved. **Client-facing?** After approval.

### QuickWin
- **Purpose:** low-effort, high-value improvement.
- **Key fields:** `quick_win_id`, effort/value indicators, related findings, evidence refs.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** When approved. **Client-facing?** After approval.

### Recommendation
- **Purpose:** a recommended action.
- **Key fields:** `recommendation_id`, rationale, related findings, priority, evidence refs.
- **Governance states:** review, lifecycle, client-facing approval.
- **Capsule-ready?** **Approved recommendations** only. **Client-facing?** After approval.

### FinancialImpactEstimate
- **Purpose:** quantified financial impact
  ([`financial-impact-estimate.schema.json`](../schemas/financial-impact-estimate.schema.json)).
- **Key fields:** `impact_id`, amounts, currency, `source_evidence_ids`,
  `verification_status`, `impact_status`, `client_facing_approved`.
- **Governance states:** review, lifecycle, **FinancialImpactStatus**, client-facing approval.
- **Capsule-ready?** **Only when approved and appropriately scoped.** **Client-facing?** Only after finance/human review + approval. No invented ROI; no figures in Git.

## Governance & process records

> **Writer boundary (future):** every write into these tables — and into the evidence /
> engagement / ingestion / capsule-candidate tables below — passes through the **Phase 17
> Controlled DB Writer Boundary** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md),
> [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md), [`../peak/persistence/`](../peak/persistence/)).
> It enforces a **table/action allowlist**, an `idempotency_key`, and the subject stored-scope
> check (`request.authorization_scope == subject.stored_authorization_scope`; identity
> matching necessary but not sufficient) before producing a no-op `ControlledWritePlan`. It
> is **DB-aware but not DB-writing** — no connection, no SQL, no stored records. `clients`,
> `engagements`, `financial_impact_estimates`, and `resolver_capsule_records` are **not**
> writable through this early boundary (the latter two await financial-verification /
> capsule-publication gates).

### ReviewRecord
- **Purpose:** an audit record of a governance review action.
- **Key fields:** `review_id`, target record id, previous/new `review_status`, reviewer, reason, timestamp.
- **Phase 22 columns:** `decision` + `authoritative` (governance-relevant, real columns),
  `subject_record_type` (type of the reviewed target, whose id is `target_id`),
  `output_status`, `idempotency_key`, and `payload_fingerprint`, with a unique index
  `uq_review_records_idem` over `(owner_id, client_id, engagement_id, idempotency_key)`
  (migration `004_review_idempotency`). Reviewer role, reasons, warnings, and flags live in
  `details_json`.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** No (governance trail). **Client-facing?** No.
- **Produced by (future):** the **QA / Review Gate** ([`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md),
  [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md), [`../peak/review/`](../peak/review/),
  Phase 15) computes the review decision (`approve_internal` = internal reliance only;
  `reject` / `return_for_revision` / `supersede` / `keep_needs_review`) as a
  production-shaped but **no-side-effect** result. In Phase 15 there are **no stored review
  records**; a future governed writer persists the decision here. A review decision never
  creates client-facing approval, verifies financial impact, or publishes a capsule.
- **Prepared by (future):** the **Phase 16 Review Persistence Boundary**
  ([`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md),
  [`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md)) maps a permitted
  `ReviewGateResult` into a `ReviewRecordDraft` and a no-op `ReviewWritePlan` targeting this
  `review_records` table — **DB-aware but not DB-writing** (`review_record_id` / `created_at`
  left `None`; no DB connection or write; no stored review records). A future controlled-DB
  writer executes the plan. **Scope rule:** a DB-backed review compares
  `request.authorization_scope` against the subject's stored `authorization_scope`
  (identity matching is necessary but not sufficient). Persisting a `ReviewRecord` should
  capture both the stored scope matched and the request scope presented, for audit.
- **Persistence executed by:** the **Phase 22 Review Record Controlled Writer**
  ([`REVIEW_CONTROLLED_WRITER.md`](REVIEW_CONTROLLED_WRITER.md),
  [`../peak/db/review_writer.py`](../peak/db/review_writer.py)) creates exactly one row from a
  Phase 16 `ReviewRecordDraft`. Write authority is anchored to the stored `Engagement` row,
  re-loaded from the DB at write-time (`request.authorization_scope ==
  engagement.authorization_scope`; identity matching necessary but not sufficient — the
  snapshot is not trusted). The reviewed target is stored as `target_id` + `subject_record_type`
  (distinct from the engagement authorization anchor). `approve_internal` may be
  `authoritative=true` (internal reliance only, never client-facing); other decisions are
  non-authoritative; a required `idempotency_key` is DB-enforced (replay returns the existing
  row; a conflicting key is denied). The writer stamps server-controlled `id` / `created_at`,
  never updates or deletes, and has no LLM/AgentNet/connector/network/client-facing/financial/
  capsule side effect.

### AgentRunRecord
- **Purpose:** provenance of an agent/worker run (Phase 13 scaffold
  [`AGENT_RUN_RECORDS.md`](AGENT_RUN_RECORDS.md); the **Phase 20** writer now persists these).
- **Key fields:** `agent_run_id`, prompt-contract ref, inputs (record ids), outputs (record ids), model/tool label, timestamps, actor.
- **Phase 20 columns:** `output_status` (governance-relevant review-gate status, a real
  column), `idempotency_key`, and `payload_fingerprint`, with a unique index
  `uq_agent_run_records_idem` over `(owner_id, client_id, engagement_id, idempotency_key)`
  (migration `002_agent_run_idempotency`). Non-governance detail (agent name, workflow, input
  ids, resolver flags) lives in `details_json`.
- **Relationships:** referenced by records an agent drafted (`agent_run_id`).
- **Governance states:** lifecycle + review. Rows are created review-gated
  (`output_status=draft`, `review_status=needs_review`).
- **Capsule-ready?** No. **Client-facing?** No.
- **Persistence planned by:** the **Phase 19 Agent Run Persistence Mapping**
  ([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md),
  [`../peak/agents/`](../peak/agents/)) maps a Phase 13 `AgentTaskResult` + `AgentRunDraft`
  into an `AgentRunPersistenceDraft` and a Phase 17 `ControlledWriteRequest` targeting this
  `agent_run_records` table (`create_agent_run_record`) — DB-free.
- **Persistence executed by:** the **Phase 20 Agent Run Controlled Writer**
  ([`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md),
  [`../peak/db/agent_run_writer.py`](../peak/db/agent_run_writer.py)) creates exactly one
  review-gated row. Write authority is anchored to the stored `Engagement` row, re-loaded
  from the DB at write-time (`request.authorization_scope == engagement.authorization_scope`;
  identity matching necessary but not sufficient — the mapping snapshot is not trusted). A
  required `idempotency_key` is DB-enforced (replay returns the existing row; a conflicting
  key is denied). The writer stamps server-controlled `id` / `created_at`, never updates or
  deletes, and has no LLM/AgentNet/connector/network/client-facing/capsule side effect.

### ResolverCapsuleRecord
- **Purpose:** a private resolver capsule
  ([`resolver-capsule-record.schema.json`](../schemas/resolver-capsule-record.schema.json)).
- **Key fields:** `capsule_id`, `owner_id`, scope, `source_reference_ids`, `evidence_ids`,
  `sensitivity_class`, `authorization_scope`, `review_status`, `lifecycle_status`, `capsule_status`.
- **Governance states:** authorization, review, lifecycle, **ResolverCapsuleStatus**.
- **Capsule-ready?** It *is* the capsule. **Client-facing?** No; governed grounding only.

### CapsulePublicationCandidate
- **Purpose:** a staged proposal to publish a capsule to a resolver, pending governance.
- **Key fields:** `candidate_id`, target `capsule_id`, proposed resolver target
  (private vs. public-but-segregated), readiness checklist, `authorization_scope`, approval decision.
- **Relationships:** references a `ResolverCapsuleRecord`.
- **Governance states:** authorization, review, lifecycle; approval gate.
- **Capsule-ready?** It gates capsule readiness. **Client-facing?** No. **No publication implementation exists.**

### SourceIngestionRecord
- **Purpose:** provenance of a controlled ingestion from a client source system (future).
- **Key fields:** `ingestion_id`, `source_reference_id`, captured-at, authorization scope, review status, resulting evidence/record ids.
- **Governance states:** authorization, review, lifecycle.
- **Capsule-ready?** Indirectly. **Client-facing?** No.
- **Prepared by:** the **Phase 23 Engagement Packet Ingestion Boundary**
  ([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md),
  [`../peak/ingestion/`](../peak/ingestion/)) derives a review-gated `SourceIngestionDraft`
  from a validated `EngagementPacket` and (optionally) a no-op Phase 17 `ControlledWriteRequest`
  targeting this table (`create_source_ingestion_record`). Ingestion is a **boundary, not a
  writer** — no direct DB write, no stored packet; `source_ingestion_record_id` / `created_at`
  stay `None`. **Persistence executed by (future):** a narrow **source ingestion writer**
  (mirroring the Phase 20–22 pattern) is still required before any row is stored — it would
  re-load the authoritative stored `Engagement` scope at write-time and enforce DB-level
  idempotency.

## Cross-cutting

Every record carries the universal governance axes (`authorization_scope`,
`review_status`, `lifecycle_status`) plus its domain family, and the audit fields in
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md). No record is client-facing
until a human sets the client-facing approval; no record is capsule-published without
governance approval. **These are planned shapes — no actual records are created.**
