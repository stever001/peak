# Data Objects

This document lists the **initial data object candidates** for Peak's internal AI
operating system. These are candidates, not final schemas — they define the shared
vocabulary before any schema, database, or code is committed.

Design notes:

- Objects are described in **portable, vendor-neutral** terms. No storage engine or
  serialization format is assumed. Field types are conceptual.
- Every substantive finding links to one or more `EvidenceReference`s. This is the
  backbone of Peak's evidence-first approach.
- These will be formalized as schemas under [`schemas/`](../schemas/) in a later
  phase (see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)).

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

## Core objects

### ClientIntake
Structured capture of a new client and engagement context.
- `client_name`, `industry`, `size_indicator`
- `engagement_reason`, `stated_objectives`
- `known_pain_points`
- `inventory_context` (locations, product types, systems in use — high level)
- `sensitivities` / access constraints
- `intake_source` (call, questionnaire, referral)
- `created_by`, `created_at`

### InventorySystemProfile
A profile of the client's inventory systems, processes, and environment, built up
during planning and discovery.
- `systems` (named ERP/WMS/spreadsheet/manual processes — described generically)
- `locations`, `product_categories`
- `counting_method(s)`, `valuation_method`
- `integration_points`, `known_limitations`
- `confidence` (how well understood, and gaps remaining)
- linked `EvidenceReference`s

### StakeholderInterview
A structured record of one interview with a client stakeholder.
- `stakeholder_role`, `stakeholder_name` (optional / redactable)
- `interview_date`, `interviewer`
- `topics_covered`
- `key_statements` (each linkable as evidence)
- `perceived_pain_points`, `contradictions_noted`
- linked `EvidenceReference`s

### VisualObservation
A single structured observation from the on-site walk-around.
- `location` / area
- `observation` (what was seen)
- `category` (e.g. storage, labeling, safety, organization)
- `severity_indicator`
- `media_reference` (photo/note pointer — no media stored yet)
- linked `EvidenceReference`

### WorkflowObservation
An observation about how an inventory-related process actually runs in practice
(as opposed to how it's documented).
- `process_name` (e.g. receiving, put-away, picking, cycle count)
- `observed_behavior`
- `documented_vs_actual_gap`
- `bottleneck_or_waste_noted`
- linked `EvidenceReference`

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

### EvidenceReference
The traceability primitive. Anything asserted should point back to one of these.
- `evidence_id`
- `source_type` (interview, visual observation, workflow observation, document)
- `source_ref` (pointer to the originating object/record)
- `excerpt_or_summary`
- `captured_by`, `captured_at`
- `reliability_indicator`

## Conventions

- **Indicators**, not scores. Early objects use qualitative indicators
  (e.g. low/medium/high) rather than false-precision numeric scores.
- **Redactable identity.** Personal names are optional and redactable to respect
  client sensitivities.
- **No PII strategy yet.** A privacy/retention model is deferred to a later phase
  and must be defined before any client data is stored persistently.
