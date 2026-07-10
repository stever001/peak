# Engagement Data Model

The conceptual model for **live engagement data** as held in Peak's controlled
engagement database/storage — **outside this repository**. This is an **architecture
model, not a database migration**: **no DB vendor is chosen**, **no SQL is written**, and
**no data is stored**. No instances of any object below are committed to the repo.

## Concepts

| Concept | Role | Repo contract |
| --- | --- | --- |
| **Client** | The client organization (identity in controlled storage). | `client_` id convention |
| **Engagement** | A unit of authorized work for a client. | [`../schemas/engagement-record.schema.json`](../schemas/engagement-record.schema.json) |
| **EngagementPacket** | The first-thread assessment bundle for an engagement. | [`../schemas/engagement-packet.schema.json`](../schemas/engagement-packet.schema.json) |
| **EvidenceReference** | Traceability primitive for evidence. | [`../schemas/evidence-reference.schema.json`](../schemas/evidence-reference.schema.json) |
| **StakeholderInterview** | A structured interview record. | [`../schemas/stakeholder-interview.schema.json`](../schemas/stakeholder-interview.schema.json) |
| **VisualObservation** | A walk-around observation. | [`../schemas/visual-observation.schema.json`](../schemas/visual-observation.schema.json) |
| **WorkflowObservation** | How a process actually runs. | [`../schemas/workflow-observation.schema.json`](../schemas/workflow-observation.schema.json) |
| **InventorySystemProfile** | The client's inventory systems/data environment. | [`../schemas/inventory-system-profile.schema.json`](../schemas/inventory-system-profile.schema.json) |
| **ControlGap** | A missing/weak internal control. | candidate (see [`DATA_OBJECTS.md`](DATA_OBJECTS.md)) |
| **OperationalRisk** | A risk to inventory operations. | candidate |
| **QuickWin** | A low-effort, high-value improvement. | candidate |
| **Recommendation** | A recommended action. | candidate |
| **FinancialImpactEstimate** | Quantified financial impact of a finding. | [`../schemas/financial-impact-estimate.schema.json`](../schemas/financial-impact-estimate.schema.json) |
| **ReviewStatus** | Governance review state carried by records. | enum: `draft`/`in_review`/`reviewed`/`approved`/`rejected` |
| **ResolverCapsuleRecord** | A private grounding capsule. | [`../schemas/resolver-capsule-record.schema.json`](../schemas/resolver-capsule-record.schema.json) |
| **SourceSystemReference** | A reference to a client source system/location. | [`../schemas/source-system-reference.schema.json`](../schemas/source-system-reference.schema.json) |

## Relationships (conceptual)

```
Client 1───* Engagement 1───* EngagementPacket
                 │                    ├─ EvidenceReference *
                 │                    ├─ StakeholderInterview *
                 │                    ├─ VisualObservation *
                 │                    ├─ WorkflowObservation *
                 │                    └─ InventorySystemProfile 1
                 ├───* SourceSystemReference ──┐  (origin of operational facts)
                 ├───* FinancialImpactEstimate │
                 ├───* ControlGap / OperationalRisk / QuickWin / Recommendation
                 └───* ResolverCapsuleRecord  ◄┘  (grounded on sources + evidence)
```

`ReviewStatus` is a cross-cutting state (draft → in_review → reviewed → approved) that
findings, estimates, capsules, and records carry through governance.

## FinancialImpactEstimate

Actual financial numbers are supported for **live engagement work** — held in controlled
storage, never in the repo. The shape
([`../schemas/financial-impact-estimate.schema.json`](../schemas/financial-impact-estimate.schema.json))
carries: `impact_id`, `engagement_id`, `related_finding_id`, `impact_type`,
`amount_low`, `amount_high`, `currency`, `period`, `calculation_basis`,
`source_evidence_ids`, `assumptions`, `confidence`, `verification_status`,
`review_status`, `client_facing_approved`, `notes`.

Rules for financial data:

- **Authorized** — used only within authorized live engagement work.
- **Evidence-linked** — every figure traces to `source_evidence_ids`.
- **Source-labeled** — `verification_status` distinguishes *reported* from *verified*.
- **Access-controlled** — held in controlled storage, not Git.
- **Human-reviewed** — `review_status` and `client_facing_approved` gate client sharing.
- **No invented ROI.** Do not fabricate or extrapolate impact.
- **No financial numbers in repo examples.** The repo commits no instances and no real
  figures.

## Not in scope here

This is a conceptual/architecture model. It intentionally does **not**: pick a database,
define SQL/DDL, specify indexes, or store any data. Implementation is future work under
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).
