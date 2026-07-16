# Engagement Packet Ingestion Boundary (Phase 23)

How Peak accepts an external `EngagementPacket`, validates its contract/shape, and derives
**production-shaped but review-gated** ingestion plans — routing eligible material into the
existing governance boundaries **without writing anything to the database**. This is an
**ingestion boundary**, not a generic importer and not a direct DB writer. **AgentNet
integration is not complete.**

## Purpose

A packet is how messy, real-world engagement material arrives: evidence items, source
references, interview notes, walk-around and inventory observations, and (optionally)
requests to run known internal agents. Phase 23 is the controlled front door for that
material. It validates the packet's identity, scope, and shape; rejects credential/secret
payloads; and turns the packet into no-side-effect *plans* — a `SourceIngestionDraft`,
Phase 14 evidence normalization requests, Phase 13 agent task requests, and (optionally) a
Phase 17 controlled write request — that later, narrower components can act on under their
own governance.

## How Phase 23 follows the DB-backed triad (Phases 20–22)

Phases 20–22 delivered three narrow live DB writers (`agent_run_records`,
`evidence_references`, `review_records`), each executing exactly one governed write. Phase 23
sits *upstream* of all of them: it accepts external packets and prepares the material those
boundaries will eventually consume. Crucially, **packet ingestion is a boundary, not a
direct importer** — it does **no direct DB writes from packet ingestion**, and it never
bypasses the evidence, agent, review, or controlled-writer boundaries.

## Core flow

```
EngagementPacket reference + payload
  -> validate packet contract / shape
  -> evaluate ingestion governance (identity, scope, secrets, lifecycle)
  -> derive SourceIngestionDraft                 (review-gated; not stored)
  -> derive Phase 14 EvidenceNormalizationRequest[]  (from present sections)
  -> derive Phase 13 AgentTaskRequest[]              (known registry agents only; not run)
  -> optionally prepare a Phase 17 ControlledWriteRequest (plan only)
  -> no direct DB writes from ingestion
```

## No side effects

- **no direct DB writes from packet ingestion**, no database connection, no SQL execution,
  no stored records;
- **packet contents are not stored** in this phase — the payload is read in memory to derive
  plans and then discarded by the caller; nothing is persisted;
- **ingestion plans are not writes** — every derived object is an in-memory plan;
- **no live LLM** call, **no AgentNet** call, no MCP/resolver call, no **database call**, no
  network or file call;
- **no client-facing approval**, **no financial verification**, **no capsule publication**;
- packet payloads containing **credentials/secrets** keys are rejected outright.

The `PacketIngestionResult` and `PacketIngestionPlan` report `direct_database_write_made`,
`database_connection_made`, `sql_execution_made`, `stored_record_created`, `llm_call_made`,
`agentnet_call_made`, `network_call_made`, `capsule_publication_made`, and
`client_facing_output_created` all `false`.

## Source ingestion drafts are production-shaped but review-gated

The `SourceIngestionDraft` is **production-shaped** — its fields line up with the
`source_ingestion_records` table — but its *status* is always gated: `output_status=draft`,
`review_status=needs_review`, `lifecycle_status=active`, non-authoritative, not
client-facing-approved, not a capsule candidate. `source_ingestion_record_id` and
`created_at` stay `None` — a **future source ingestion writer** (not this phase) assigns
them.

## Derived evidence requests may be prepared but not persisted directly

Structurally present evidence-like sections (`evidence_items`, `source_references`,
`interview_notes`, `walkaround_observations`, `inventory_observations`) are converted into
Phase 14 `EvidenceNormalizationRequest` objects. These are **not persisted directly**: they
flow to the Phase 14 worker (review-gated normalization) and, only later, to the Phase 21
evidence controlled writer. Only a short, non-sensitive `raw_text_preview` is carried; full
raw text is never stored.

## Derived agent tasks may be prepared but not executed

`requested_agent_tasks` are mapped to Phase 13 `AgentTaskRequest` objects **only** for agent
names in the Phase 13 registry; unknown agents are skipped with a warning, never executed.
Derived tasks keep `llm_execution_allowed=false` and `client_facing_output_requested=false`,
default to `draft` / `needs_review`, and are **not executed** — the Phase 13 harness (and its
governance) runs them later, if at all.

## Controlled write requests are plans only

If useful, ingestion prepares a Phase 17 `ControlledWriteRequest` targeting
`source_ingestion_records` / `create_source_ingestion_record` with the `SourceIngestionDraft`
as its `record_draft` and the request's `idempotency_key`. This is routed through the
existing Phase 17 boundary as a **plan only**; ingestion calls **no** DB writer. A write plan
is not a write.

## Boundaries

- **No direct DB writes**, no SQL, no DB connection, no stored packet or ingestion record.
- **No live LLM / AgentNet / MCP / resolver / network call.**
- **No client-facing approval, no financial verification, no capsule publication.**
- **No bypass** — packet-derived material always flows through the evidence, agent, review,
  and controlled-writer boundaries. The **Phase 24 Source Ingestion Record Controlled Writer**
  ([`SOURCE_INGESTION_CONTROLLED_WRITER.md`](SOURCE_INGESTION_CONTROLLED_WRITER.md),
  [`../peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py)) performs
  the real `source_ingestion_records` write under access control
  ([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)) — it re-loads the stored
  `Engagement` scope at write-time, persists **packet metadata only** (never the payload), and
  enforces DB-level idempotency.
