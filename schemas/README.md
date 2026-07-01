# Schemas

Portable, storage-agnostic **JSON Schema (draft 2020-12)** definitions for Peak's
internal assessment data objects. These formalize the candidate objects described in
[`../docs/DATA_OBJECTS.md`](../docs/DATA_OBJECTS.md).

## Scope (Phase 1)

Phase 1 defines the **first-thread assessment objects**:

| Schema | Object | Local id prefix |
| --- | --- | --- |
| `client-intake.schema.json` | `ClientIntake` | `intake_` |
| `evidence-reference.schema.json` | `EvidenceReference` | `evid_` |
| `stakeholder-interview.schema.json` | `StakeholderInterview` | `intv_` |
| `visual-observation.schema.json` | `VisualObservation` | `vobs_` |
| `workflow-observation.schema.json` | `WorkflowObservation` | `wobs_` |
| `inventory-system-profile.schema.json` | `InventorySystemProfile` | `isp_` |

Worked, anonymized examples for each live in [`../examples/`](../examples/).

## Conventions

- **Draft 2020-12.** Each schema declares `$schema`, a stable `$id`, `title`,
  `description`, `type`, `properties`, `required`, and `additionalProperties: false`
  (on the root and every nested object).
- **Portable `$id`s.** Ids use the `https://peak.internal/schemas/v1/` namespace.
  This is an internal, non-resolving namespace — a stable identifier, not a live
  URL, and it implies no hosting or vendor dependency.
- **Stable local identifiers.** Each object carries a prefixed id (see table). The
  prefix pattern is enforced loosely (`^prefix_[A-Za-z0-9][A-Za-z0-9_-]*$`) so ids
  are recognizable and validatable without over-constraining.
- **Evidence-first.** Objects carry `evidence_references` (arrays of `evid_` ids),
  and many nested findings/claims carry their own. `EvidenceReference` is the
  traceability primitive everything points back to.
- **ISO-8601 timestamps.** Date/time fields use `format: date-time`.
- **Qualitative indicators, not false precision.** Severity, reliability, urgency,
  confidence, etc. use small enums (typically `low`/`medium`/`high`, plus
  `critical`/`unknown` where useful) rather than numeric scores at this stage.
- **Enums are deliberately conservative.** Where a concept is still immature, an
  `other` member is provided rather than forcing a premature taxonomy.
- **Consultant-readable.** Free-text `consultant_notes` (and `notes`) fields exist
  so human judgment travels alongside structured data.
- **No PII, no sensitive content.** Names are anonymized labels. `EvidenceReference`
  records a `sensitive_data_flag` and summaries but never embeds sensitive content.
- **No storage/implementation fields.** No primary keys, foreign keys, row-version
  timestamps, or other database-specific concerns. These objects are a portable
  interchange vocabulary, not a persistence model.

## Design intent

These objects are meant to be **evidence-first, consultant-readable, agent-usable,
and management-report-ready**, and to be suitable for later AgentNet grounding and
resolution. **AgentNet is not integrated** — that grounding is intended future
architecture (see [`../docs/OPERATING_MODEL.md`](../docs/OPERATING_MODEL.md)).

## Validation

The examples in [`../examples/`](../examples/) validate against these schemas under
draft 2020-12. A committed validation test harness is the recommended next step (see
[`../docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md) and
[`../tests/`](../tests/)).
