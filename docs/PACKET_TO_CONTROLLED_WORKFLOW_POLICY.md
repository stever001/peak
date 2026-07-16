# Packet → Controlled Workflow Policy (Phase 23)

The rules that govern how an external `EngagementPacket` becomes controlled, review-gated
work. This is a governance **contract** enforced by the Phase 23 **ingestion boundary**
([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md)). It is
a boundary, not an importer: **ingestion plans are not writes**, and **packet contents are
not stored**.

## Allowed packet-derived outputs

- A **`SourceIngestionDraft`** — production-shaped but review-gated (`output_status=draft`,
  `review_status=needs_review`, non-authoritative, not client-facing, not a capsule
  candidate); `source_ingestion_record_id` / `created_at` left `None`.
- **Phase 14 `EvidenceNormalizationRequest` objects** derived from structurally present
  evidence-like sections.
- **Phase 13 `AgentTaskRequest` objects** for known registry agents only (never executed).
- Optionally, a **Phase 17 `ControlledWriteRequest`** for `source_ingestion_records` —
  a plan only.

## Prohibited packet-derived effects

Ingestion may never, from a packet: perform **no direct DB writes from packet ingestion**
(no write, no connection, no SQL, no stored record); make a **no live LLM** / **no AgentNet**
/ MCP / resolver / network / **no database call**; create **no client-facing approval**;
perform **no financial verification**; do **no capsule publication**; call any Phase 20/21/22
DB writer; or persist packet contents. **Credentials/secrets** in a packet payload are
rejected.

## Packet identity and authorization-scope checks

- Request `owner_id` / `client_id` / `engagement_id` must match the `packet_reference`.
- `request.authorization_scope` must equal `packet_reference.authorization_scope`.
- **Owner/client/engagement matching is necessary but not sufficient** — the scope must
  match too, and the packet reference's `lifecycle_status` must not be `revoked` /
  `archived` / `deleted_reference_only`.

## `idempotency_key` requirement

Every ingestion request must carry an `idempotency_key`. It is required now so that a future
source ingestion writer can dedupe and make retries replay-safe (matching the Phase 20–22
uniqueness pattern over `(owner, client, engagement, idempotency_key)`). A request without an
`idempotency_key` is denied.

## Secret-key rejection

The packet payload is scanned (top-level and nested) for keys containing credential/secret
terms — `password`, `secret`, `api_key`, `token`, `private_key`, `credential`,
`connection_string`, `access_key`, and similar. A match denies the request. **Only key names
are ever reported; secret values are never logged or echoed.**

## Why ingestion does not bypass existing boundaries

Ingestion produces *requests and plans*, not results. Derived evidence flows through the
Phase 14 review-gated normalization worker and (later) the Phase 21 evidence controlled
writer; derived agent tasks flow through the Phase 13 harness and its governance; review
decisions flow through Phases 15/16 and the Phase 22 review writer; and any actual write
goes through a narrow Phase 17–style controlled writer. Ingestion never shortcuts these — it
only prepares material for them, so every downstream governance gate still applies.

## DB-backed source ingestion writer (Phase 24)

Phase 23 does **not** persist a `source_ingestion_records` row. It prepares a
`SourceIngestionDraft` and (optionally) a Phase 17 `ControlledWriteRequest` targeting
`source_ingestion_records` / `create_source_ingestion_record`. **Source ingestion records
require a narrow writer before persistence** — that writer is the **Phase 24 Source Ingestion
Record Controlled Writer** ([`SOURCE_INGESTION_CONTROLLED_WRITER.md`](SOURCE_INGESTION_CONTROLLED_WRITER.md),
[`SOURCE_INGESTION_IDEMPOTENCY_POLICY.md`](SOURCE_INGESTION_IDEMPOTENCY_POLICY.md)), which
mirrors the Phase 20–22 pattern: at write-time it re-loads the authoritative stored
`Engagement` scope (not the packet reference), enforces DB-level idempotency, persists **packet
metadata only**, and creates exactly one review-gated row. Outside that writer,
`source_ingestion_records` remains plan-only.

The **Phase 25 Controlled Packet Processing Orchestrator**
([`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md),
[`PACKET_PROCESSING_ORCHESTRATION_POLICY.md`](PACKET_PROCESSING_ORCHESTRATION_POLICY.md))
sequences these packet-derived outputs deterministically. It preserves every prohibited-effect
rule here: plan-only is the default, no stage silently escalates to persistence, persistence
runs only through the existing narrow writers, and raw packet payload content is never stored or
echoed. It grants no new write authority.
