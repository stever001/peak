# Evidence Normalization Worker (Phase 14)

The first **production-shaped** Peak internal worker. It turns a raw evidence reference
into a structured, **review-gated** `NormalizedEvidenceRecord` — high-quality output that
is nonetheless never authoritative on its own. **AgentNet integration is not complete.**

## Purpose

Consulting engagements generate messy, heterogeneous evidence — interview notes,
walk-around notes, photos, source-system observations, inventory reports. Before any of it
can support an assessment, report, proposal, or (much later) a resolver capsule, it has to
be **normalized** into consistent, traceable records. This worker is that normalization
step: deterministic, scoped, and governed.

## Why evidence normalization is the first real worker

Evidence is the traceability primitive for everything Peak produces (see
[`DATA_OBJECTS.md`](DATA_OBJECTS.md) and
[`../schemas/evidence-reference.schema.json`](../schemas/evidence-reference.schema.json)).
Normalizing it well — with clear source references, areas, and quality signals — is the
highest-leverage, lowest-risk place to make a worker **production-shaped**: the output
record is suitable for the controlled data architecture later, without needing a live
model, a database, or any client-facing surface today.

## Production-shaped but review-gated

The worker produces records whose *shape* is ready for later controlled storage, but whose
*status* is always gated:

- `output_status = draft`
- `review_status = needs_review`
- `authoritative = false`
- `client_facing_approved = false`
- `capsule_candidate_ready = false`

High-quality structure does **not** confer authority. A record becomes authoritative or
client-facing only through the future human/QA review gates
([`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md),
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md)). The **QA / Review Gate**
([`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md), Phase 15) evaluates these drafts for internal
reliance — a production-shaped but no-side-effect decision that stores nothing.

## Deterministic / no-live-call behavior in Phase 14

Normalization is fully deterministic — dictionary and keyword maps, no inference engine.
In this phase the worker makes **no live LLM call**, **no AgentNet call**, **no database
write** (or read), and no network or file write. The only outputs are in-memory dataclass
instances returned to the caller; nothing is stored.

Deterministic behavior includes: mapping `source_type`/`content_type` to a schema-aligned
`evidence_type`; deriving a coarse `operational_area` and `inventory_process_area` from
keyword hints in the observation context / preview; setting `confidence_level` and
`reliability` from input completeness; flagging missing `observed_at` / `source_location` /
`raw_text_preview`; and building a conservative, self-labeled title and summary.

## Expected future inputs

The worker is shaped to accept (in future) normalized wrappers around: interview notes,
walk-around notes, photographs, source-system observations, inventory reports,
receiving/shipping observations, and cycle-count findings. Today those arrive only as
in-memory synthetic objects in tests; **no example data files are committed**.

## Expected normalized output categories

Each record carries: `evidence_type`, `operational_area`, `inventory_process_area`,
`normalized_title`, `normalized_summary`, `observed_condition`, `source_type`,
`source_location`, `confidence_level`, completeness flags, and quality signals — plus the
review-gate fields above.

## How it supports later workflows

Normalized evidence is the input other workers/consultants build on: assessment and
initial report generation, quick-win and next-phase proposal drafting, and — only after
review and approval — preparation of **capsule candidates**
([`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md)). The worker prepares
the raw material; humans and later governed steps decide what becomes authoritative.

## Boundaries

- **No authority escalation** — the worker cannot mark anything authoritative or
  `approved_internal`.
- **No client-facing output** — nothing here is client-facing; that requires an explicit
  future human approval gate.
- **No database write in this phase** — records are in-memory only; a future
  controlled-DB writer persists them under access control
  ([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)).
- **No AgentNet / LLM / network call in this phase.**
- **No capsule publication** — deferred, and not implemented here.

## Persistence is planned, never executed here (Phase 18)

The worker never writes to the database. When a normalized record is destined for controlled
storage, the **Phase 18 Evidence Persistence Mapping**
([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
[`../peak/evidence/`](../peak/evidence/)) maps it into a production-shaped but review-gated
`EvidencePersistenceDraft` and routes it through the Phase 17 controlled writer boundary as a
no-op plan targeting `evidence_references` / `create_draft` — **DB-aware but not DB-writing**.
**Evidence workers still do not write directly to the DB**; a future controlled DB writer
executes the plan after the allowlist, `idempotency_key`, and stored-scope checks pass.

Raw evidence may also arrive from an external packet: the **Phase 23 Engagement Packet
Ingestion Boundary** ([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md))
derives Phase 14 `EvidenceNormalizationRequest` objects from a validated packet's evidence-like
sections (carrying only a short `raw_text_preview`, never full raw text), which then feed this
worker under its normal review gate. Ingestion is a boundary, not a writer, and does not
persist anything.

The **Phase 25 Controlled Packet Processing Orchestrator**
([`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md))
runs this worker as its (default-on, DB-free) evidence-normalization stage over the derived
requests, and — only when explicitly requested with a `session_factory` — routes each normalized
record through the Phase 18 mapping into the Phase 21 evidence writer. Normalization stays
deterministic (no LLM/AgentNet/network); the review gate is unchanged.

Evidence-reference ids (safe references) may later be organized for human review by the **Phase 29
Packet-Derived Review Orchestration Boundary**
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md))
as `evidence_reference_review` items — DB-free, no approval, no raw content.
