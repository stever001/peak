# Data Objects

This document lists the **initial data object candidates** for Peak's internal AI
operating system. These are candidates, not final schemas — they define the shared
vocabulary before any schema, database, or code is committed.

Design notes:

- Objects are described in **portable, vendor-neutral** terms. No storage engine or
  serialization format is assumed. Field types are conceptual.
- Every substantive finding links to one or more `EvidenceReference`s. This is the
  backbone of Peak's evidence-first approach.
- **Status (Phase 1):** the six first-thread assessment objects are now formalized
  as JSON Schema (draft 2020-12) under [`schemas/`](../schemas/), with worked
  examples under [`examples/`](../examples/). For those objects, **the schema is the
  authoritative field-level definition**; the summaries below track it. The
  remaining objects are still candidates awaiting later phases (see
  [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)).

Formalized in Phase 1: `ClientIntake`, `EvidenceReference`, `StakeholderInterview`,
`VisualObservation`, `WorkflowObservation`, `InventorySystemProfile`.

Formalized in Phase 2: `EngagementPacket` — a composite that bundles the Phase 1
objects for a single engagement (see the [EngagementPacket](#engagementpacket-formalized-schemasengagement-packetschemajson)
section below).

## Object relationship overview

```
ClientIntake
   └── seeds → InventorySystemProfile
                    │
   Discovery ───────┤
     ├── StakeholderInterview ─┐
     ├── VisualObservation ────┤
     └── WorkflowObservation ──┘
                    │  normalized into
                    ▼
             EvidenceReference  ◄─── every finding cites these
                    │  supports derivation of
        ┌───────────┼───────────┬───────────────┐
        ▼           ▼           ▼               ▼
 DataQualityIssue ControlGap OperationalRisk  (findings)
        │           │           │
        └───────────┴───────────┴──► QuickWin, Recommendation
                                            │
                                     ClientReportSection
                                            │
                                     PhaseTwoOpportunity
```

## Composite object

### EngagementPacket  *(formalized: [`schemas/engagement-packet.schema.json`](../schemas/engagement-packet.schema.json))*
The first practical **operating unit**: one self-contained bundle of an engagement's
first-thread assessment, which future internal Peak agents will read from and write
to. It **composes** the Phase 1 objects by local relative `$ref` rather than
redefining them. Id prefix `pkt_`.
- `packet_id`, `packet_version`, `created_at`, `updated_at`
- `engagement_label`, `assessment_stage` (intake … discovery … proposal … complete)
- `client_intake` (the anchor — its `intake_id` is what nested objects reference)
- `inventory_system_profile`
- `evidence_references[]` — the packet's authoritative evidence store
- `stakeholder_interviews[]`, `visual_observations[]`, `workflow_observations[]`
- `packet_metadata` (prepared_by, team, confidentiality, provenance)
- `validation_notes` (human/agent notes about packet state)

**Packet invariants** (enforced as blocking checks by
[`tests/validate_phase2.py`](../tests/validate_phase2.py)):
- every `evidence_references` id used by a nested object resolves to an
  `EvidenceReference` declared in `evidence_references[]`;
- `inventory_system_profile.related_intake_id` and every interview/observation
  `related_intake_id` equals `client_intake.intake_id`.

## Core objects

### ClientIntake  *(formalized: [`schemas/client-intake.schema.json`](../schemas/client-intake.schema.json))*
Structured capture of a new client and engagement context. Id prefix `intake_`.
- `intake_id`; `created_by`, `created_at`
- `client_profile` (`organization_label`, `organization_type`, `size_indicator`,
  `locations_count_indicator`, `geographies`)
- `industry`, `operating_model`
- `inventory_environment` (product categories, storage types, SKU/throughput/value
  indicators)
- `known_systems` (generic name/category/role/notes)
- `stated_pain_points` (each with `impact_indicator` and `evidence_references`)
- `stakeholders` (role + `anonymized_label` + involvement)
- `urgency` (`level`, `business_trigger`)
- `available_data_sources`, `initial_scope_hypothesis`
- `first_billing_tranche_objective`, `assessment_readiness`
- `evidence_references`, `consultant_notes`

### InventorySystemProfile  *(formalized: [`schemas/inventory-system-profile.schema.json`](../schemas/inventory-system-profile.schema.json))*
A profile of the client's inventory systems, records, and data environment. Id
prefix `isp_`.
- `system_profile_id`, `related_intake_id`
- `known_systems` (described generically)
- `records_source_of_truth` (system + `confidence` + notes)
- `integrations` (`integration_type`, `reliability`)
- `manual_workarounds` (per `workflow_area`)
- `reporting_outputs`
- `data_quality_concerns` (early concerns; formal `DataQualityIssue`s derived later)
- `access_status`
- `evidence_references`, `consultant_notes`

### StakeholderInterview  *(formalized: [`schemas/stakeholder-interview.schema.json`](../schemas/stakeholder-interview.schema.json))*
A structured record of one interview with a client stakeholder. Id prefix `intv_`.
- `interview_id`, `related_intake_id`
- `stakeholder_role`, `stakeholder_label` (anonymized), `interviewed_at`, `interviewer`
- `topics_covered`
- `stated_pain_points`, `process_claims`, `system_claims` (recorded as claims to
  validate)
- `quantified_impacts` (metric/value/unit, as reported)
- `contradictions_or_followups`
- `evidence_references`, `consultant_notes`

### VisualObservation  *(formalized: [`schemas/visual-observation.schema.json`](../schemas/visual-observation.schema.json))*
A single structured observation from the on-site walk-around. Id prefix `vobs_`.
- `observation_id`, `related_intake_id`, `observed_at`, `observed_by`
- `site_area`, `observation_type` (storage, labeling, safety, organization, …)
- `description`, `operational_implication`
- `severity` (low/medium/high/critical)
- `suggested_follow_up`
- `evidence_references` (e.g. photographs, consultant notes), `consultant_notes`

### WorkflowObservation  *(formalized: [`schemas/workflow-observation.schema.json`](../schemas/workflow-observation.schema.json))*
An observation about how an inventory-related process actually runs in practice
(as opposed to how it's documented). Id prefix `wobs_`.
- `observation_id`, `related_intake_id`, `observed_at`, `observed_by`
- `workflow_area` (receiving, putaway, picking, cycle_count, replenishment,
  returns, adjustment, reporting, other)
- `current_state`, `observed_gap`, `business_impact`
- `control_risk` (description + severity)
- `potential_quick_win` (flag)
- `evidence_references`, `consultant_notes`

## Derived findings

### DataQualityIssue
An identified problem with the accuracy, completeness, or reliability of the
client's inventory data.
- `description`
- `data_domain` (counts, valuation, master data, transactions)
- `impact_indicator`
- `supporting_evidence` (`EvidenceReference`s)

### ControlGap
A missing or weak internal control over inventory.
- `description`
- `control_type` (segregation of duties, approvals, reconciliation, access)
- `exposure_indicator`
- `supporting_evidence` (`EvidenceReference`s)

### OperationalRisk
A risk to inventory operations (continuity, cost, service, compliance).
- `description`
- `risk_category`
- `likelihood_indicator`, `impact_indicator`
- `supporting_evidence` (`EvidenceReference`s)

## Commercial / output objects

### QuickWin
A low-effort, high-value improvement the client can act on quickly.
- `description`
- `effort_indicator` (low)
- `value_indicator`
- `related_findings` (issues/gaps/risks it addresses)
- `supporting_evidence` (`EvidenceReference`s)

### Recommendation
A recommended action arising from the assessment.
- `title`, `description`
- `rationale`
- `related_findings`
- `effort_indicator`, `value_indicator`, `priority_indicator`
- `supporting_evidence` (`EvidenceReference`s)

### ClientReportSection
A section of the initial management report, drafted for consultant review.
- `section_title`
- `narrative`
- `referenced_findings`
- `supporting_evidence` (`EvidenceReference`s)
- `review_status` (draft / reviewed / approved)

### PhaseTwoOpportunity
A candidate scope item for a paid next phase of work.
- `title`, `description`
- `expected_value`
- `dependencies`
- `related_recommendations`
- `supporting_evidence` (`EvidenceReference`s)

## Cross-cutting object

### EvidenceReference  *(formalized: [`schemas/evidence-reference.schema.json`](../schemas/evidence-reference.schema.json))*
The traceability primitive. Anything asserted should point back to one of these. Id
prefix `evid_`.
- `evidence_id`
- `evidence_type` (interview_statement, visual_observation, document, …)
- `source_type` (stakeholder, site_walk, system, document, consultant, other)
- `collection_method`, `collected_at`, `collected_by`
- `related_object_ids` (ids of objects this evidence supports)
- `summary` (non-sensitive)
- `reliability` (low/medium/high), `confidence_notes`
- `access_notes`, `retention_notes`
- `sensitive_data_flag` (never embeds the sensitive content itself)
- `consultant_notes`

## Conventions

- **Indicators**, not scores. Early objects use qualitative indicators
  (e.g. low/medium/high) rather than false-precision numeric scores.
- **Redactable identity.** Personal names are optional and redactable to respect
  client sensitivities.
- **No PII strategy yet.** A privacy/retention model is deferred to a later phase
  and must be defined before any client data is stored persistently.
