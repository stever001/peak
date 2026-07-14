# Database Record Model

Planned record groups for Peak's controlled engagement database. **Planning only — no
database, schema migration, or stored data is created, and no actual records exist.**
Records live in controlled storage, **never in Git**. Shapes reuse the architecture
contracts in [`../schemas/`](../schemas/) and the governance states in
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md). AgentNet grounding is **intended future
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
- **Capsule-ready?** **Yes, when `verified`** and source-labeled. **Client-facing?** As cited support, after approval.

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

### ReviewRecord
- **Purpose:** an audit record of a governance review action.
- **Key fields:** `review_id`, target record id, previous/new `review_status`, reviewer, reason, timestamp.
- **Governance states:** review, lifecycle.
- **Capsule-ready?** No (governance trail). **Client-facing?** No.

### AgentRunRecord
- **Purpose:** provenance of an agent/worker run (future harness).
- **Key fields:** `agent_run_id`, prompt-contract ref, inputs (record ids), outputs (record ids), model/tool label, timestamps, actor.
- **Relationships:** referenced by records an agent drafted (`agent_run_id`).
- **Governance states:** lifecycle. Agent outputs default to `draft`/`needs_review`.
- **Capsule-ready?** No. **Client-facing?** No.

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

## Cross-cutting

Every record carries the universal governance axes (`authorization_scope`,
`review_status`, `lifecycle_status`) plus its domain family, and the audit fields in
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md). No record is client-facing
until a human sets the client-facing approval; no record is capsule-published without
governance approval. **These are planned shapes — no actual records are created.**
