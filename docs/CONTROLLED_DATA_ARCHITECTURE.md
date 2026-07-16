# Controlled Data Architecture

How Peak stores and grounds real engagement data **outside** this repository. This is
**architecture documentation only** — no database, API, resolver, or ingestion pipeline
is implemented here. AgentNet grounding/resolution is **intended future architecture,
not implemented**.

## Dual role & AI-readiness

Peak has a dual role in every engagement: (1) use AI **internally** to assess and
recommend improvements to the client's current inventory/warehouse operations, and (2)
progressively refine messy client data, workflows, evidence, and operational knowledge so
the client becomes **ready for capsulization** and eventual **AgentNet-based agentic AI
operations**. These are **parallel goals** — each engagement phase should produce
immediate consulting value *and* prepare the client for the next phase. The controlled
database (see [`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md)) is a
**pre-capsulization staging layer** designed to support both. AgentNet remains intended
future architecture, not implemented.

## Principles

- **The repo is source-only.** It contains source assets only: docs, schemas, prompt
  contracts, tools, validation logic, and policy. It stores **no client data** and **no
  data artifacts**.
- **Controlled storage is the system of record.** Live engagement data lives in Peak's
  **controlled engagement database/storage**, under access control and authorization —
  never in Git.
- **Private resolver capsules are the governed grounding layer.** Grounding/resolution
  operates over **private resolver capsules** (see
  [`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md)), not over repo
  files.
- **Source systems remain the origin of operational facts** where applicable (ERP/WMS,
  reports, telemetry, logs). See
  [`SOURCE_SYSTEM_CAPSULIZATION.md`](SOURCE_SYSTEM_CAPSULIZATION.md).
- **Agent/AI workflows consume authorized data through controlled access paths** — they
  read from controlled storage / resolver capsules under authorization, never from
  committed repo data (there is none).
- **No client data in Git.** Not for examples, fixtures, demos, training, tests, or any
  non-engagement use.
- **Synthetic runtime fixtures only for validation** — generated in temp locations,
  never committed (see [`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md)).

## Architecture diagram

```
Peak repo
  -> source definitions only (docs, schemas, prompt contracts, tools, validation, policy)

Client source systems / notes / exports / telemetry
  -> controlled engagement database        (system of record for live engagement data)
  -> capsulization pipeline                (intended future architecture)
  -> private resolver capsules             (governed grounding/resolution layer)
  -> internal Peak AI workflows            (consume authorized data via controlled access)
```

The two lanes never cross: the repo defines the *shapes and process*; the controlled
data layer holds the *data*. Agent/AI workflows are driven by the repo's definitions but
operate on data only through controlled, authorized access paths.

## Data classification

Every item is exactly one of these classes:

| Class | Meaning | Where it lives |
| --- | --- | --- |
| `source_asset` | Repo-owned, non-data material (docs, schemas, prompts, tools, tests, policy) | This repository |
| `live_client_data` | Authorized engagement data | Controlled engagement storage (authorized use only) |
| `private_capsule` | Resolver-grounded client/project knowledge | Resolver layer (governed) |
| `peak_methodology` | Reusable internal Peak knowledge | Repo (as source assets) and/or methodology capsules |
| `synthetic_runtime_fixture` | Temporary generated test fixture | Temp dir at test time only — never committed |
| `prohibited_repo_data` | Any data-like thing stored in Git | **Not allowed** — the data-artifact guard fails on it |

Rules:

- `live_client_data` is used **only for authorized live client engagement work**, never
  for examples/fixtures/demos/training/tests.
- Nothing that is `live_client_data` or `private_capsule` is ever committed to the repo.
- The only data-shaped thing allowed near the repo is a `synthetic_runtime_fixture`, and
  only transiently at test time.

## What this repo defines (architecture contracts)

The controlled data layer is described by architecture-contract schemas (shapes only —
**no instances are committed**):

- [`../schemas/engagement-record.schema.json`](../schemas/engagement-record.schema.json)
- [`../schemas/financial-impact-estimate.schema.json`](../schemas/financial-impact-estimate.schema.json)
- [`../schemas/source-system-reference.schema.json`](../schemas/source-system-reference.schema.json)
- [`../schemas/resolver-capsule-record.schema.json`](../schemas/resolver-capsule-record.schema.json)

See [`ENGAGEMENT_DATA_MODEL.md`](ENGAGEMENT_DATA_MODEL.md) for the full model. These are
**architecture models, not a database migration** — no DB vendor is chosen and no SQL is
written. The staged plan for standing up the controlled database is in
[`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md), with the record
groups in [`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md), access/audit in
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md), and the capsule mapping in
[`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md).

## Governance states

Every record in controlled storage carries governance state (authorization, review,
lifecycle, plus domain-specific status) that gates how it may be used and who may advance
it. The allowed states and transitions are defined in
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) and
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md), with enum contracts in
[`../schemas/governance-state.schema.json`](../schemas/governance-state.schema.json).
Agent/AI workflows must default their output to `draft`/`needs_review` and may never set
`client_facing_approved` — human review gates are preserved by contract.

## Preparing records for controlled storage (workers)

Records destined for controlled storage are shaped by **production-shaped but review-gated**
workers before any persistence exists. The first is the **Evidence Normalization Worker**
([`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md),
[`../peak/workers/`](../peak/workers/)): it produces `NormalizedEvidenceRecord`s whose
shape fits this architecture, defaulting to `draft`/`needs_review` and non-authoritative.
**No database write happens yet** — a future governed writer persists reviewed records
under access control ([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)); see
the record lifecycle in [`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md).

The **Phase 18 Evidence Persistence Mapping**
([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
[`../peak/evidence/`](../peak/evidence/)) is the step that connects a normalized record to
that future write: it maps the record into an `EvidencePersistenceDraft` and routes it
through the Phase 17 controlled writer boundary as a no-op plan for `evidence_references` /
`create_draft` — **DB-aware but not DB-writing**. Evidence workers still do not write
directly to the DB, and every future write passes through the allowlist, `idempotency_key`,
and parent-subject stored-scope checks.

The **Phase 19 Agent Run Persistence Mapping**
([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md),
[`../peak/agents/`](../peak/agents/)) does the same for agent run provenance: it maps a
Phase 13 agent output into an `AgentRunPersistenceDraft` and a Phase 17 no-op plan for
`agent_run_records` / `create_agent_run_record`. Agent execution still does not write
directly to the DB; the same allowlist, idempotency, and stored-scope checks apply, anchored
on the stored engagement/client/subject.

The **Phase 20 Agent Run Controlled Writer**
([`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md),
[`../peak/db/agent_run_writer.py`](../peak/db/agent_run_writer.py)) is the first component
that actually **persists** into this controlled store — creating one review-gated
`agent_run_records` row. It closes the gap between "plan" and "row" for one narrow table
only, and it re-loads the authoritative stored `Engagement` scope from the database at
write-time (the mapping snapshot is not trusted as proof of authorization). The **Phase 21
Evidence Controlled Writer** ([`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md),
[`../peak/db/evidence_writer.py`](../peak/db/evidence_writer.py)) does the same for
`evidence_references` (`create_draft`), using the identical stored-`Engagement` authorization
and DB-enforced idempotency. The **Phase 22 Review Record Controlled Writer**
([`REVIEW_CONTROLLED_WRITER.md`](REVIEW_CONTROLLED_WRITER.md),
[`../peak/db/review_writer.py`](../peak/db/review_writer.py)) is the third, persisting
`review_records` (`create_review_record`) from a Phase 16 `ReviewRecordDraft` under the same
authorization and idempotency rules. Everything else in this architecture remains plan-only
until it gets its own reviewed writer.

External material enters through the **Phase 23 Engagement Packet Ingestion Boundary**
([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md),
[`../peak/ingestion/`](../peak/ingestion/)) — an **ingestion boundary, not a direct importer
and not a DB writer**. It validates an `EngagementPacket`, rejects credential/secret payloads,
and derives review-gated plans (a `SourceIngestionDraft`, Phase 14 evidence requests, Phase 13
agent tasks, a no-op Phase 17 write plan) that route through the existing controlled
boundaries. Packet ingestion **does not write directly to the database** and does not bypass
the evidence, agent, review, or controlled-writer boundaries; `source_ingestion_records`
persistence requires a future narrow writer.

Whether a worker output may be relied on internally is decided by the **QA / Review Gate**
([`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md), [`../peak/review/`](../peak/review/), Phase 15):
a production-shaped but **no-side-effect** review decision (`approve_internal` means
internal reliance only). It stores nothing — there are **no stored review records** in this
phase — and never creates client-facing approval; a future governed writer would persist
the decision as a `ReviewRecord`.

The **Phase 16 Review Persistence Boundary** ([`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md),
[`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md)) prepares that future
persistence — **DB-aware but not DB-writing**. It produces a `ReviewRecordDraft` and a no-op
`ReviewWritePlan` (target `review_records`) with **no live database read/write** and no
stored review records. Because authority to act on a stored record depends on the record's
own governance state, a DB-backed review must compare `request.authorization_scope` against
the subject's stored `authorization_scope` (loaded from controlled storage) — owner/client/
engagement matching is necessary but not sufficient.

The **Phase 17 Controlled DB Writer Boundary** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md),
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md), [`../peak/persistence/`](../peak/persistence/))
generalizes that idea into the front door for *all* future controlled writes into this
architecture — still **DB-aware but not DB-writing**. Every future persistence must pass
through a **table/action allowlist** and the subject stored-scope check before a no-op
`ControlledWritePlan` is produced; nothing here opens a database connection, executes SQL,
or stores a record. `clients` / `engagements` and the financial/resolver tables are excluded
from this early boundary until explicit governance gates exist.

## Grounding access boundary (AgentNet MCP connector)

When future workflows reach the resolver for grounding, they do so through the **existing
AgentNet MCP connector** (a separate repo), fronted by Peak's own **governance wrapper**
that checks owner/engagement scope and governance state before any call. This boundary is
contracts/scaffold only — it makes **no live calls**, and **AgentNet integration is not
complete**. See [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md) and
[`PEAK_RESOLVER_ACCESS_POLICY.md`](PEAK_RESOLVER_ACCESS_POLICY.md).
