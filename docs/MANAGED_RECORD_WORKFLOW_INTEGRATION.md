# Managed Record Workflow Integration (Phase 35)

A **governed workflow integration layer** over the durable DB-backed records Peak already has. It
connects the existing narrow controlled writers into a single orchestration path that can persist a
whole workflow sequence, under **explicit per-stage persistence gates**.

This is a **workflow integration phase, not a new persistence primitive phase**. Phase 35 adds
**no DB table, no DB model, and no Alembic migration**. The Alembic head remains
`009_intake_note_records`, `make db-check` still expects exactly **15 tables**, and the Phase 17
allowlist gains **no new table/action pair**.

Implementation: [`peak/workflows/`](../peak/workflows/) —
[`contracts.py`](../peak/workflows/contracts.py),
[`governance.py`](../peak/workflows/governance.py),
[`managed_record_workflow.py`](../peak/workflows/managed_record_workflow.py).
Governance rules: [`WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md`](WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md).

---

## What it is — and is not

**Is:** a deterministic sequencing layer that builds one Phase 17 `ControlledWriteRequest` per stage
and hands it to the one narrow writer that owns that stage's table, under a gate the caller must
turn on explicitly.

**Is not:** a new DB table/model/migration, generic CRUD, a generic DB writer, an arbitrary SQL
executor, a broad read/write repository, an ORM, an API, a frontend, report drafting/persistence,
client-facing output, client-facing approval, financial verification, capsule publication, an
AgentNet publish operation, an AgentNet resolver call, an MCP call, a live or mock LLM call, agent
or mock-agent execution, a production DB write path, a cleanup/delete path, seed data, or an
`examples/` directory.

---

## The workflow sequence

Six stages, in this fixed order. Each stage maps to exactly one existing durable record type and one
existing narrow controlled writer:

| # | Stage name (gate key) | Table | Action | Writer (phase) |
|---|---|---|---|---|
| 1 | `intake_note` | `intake_note_records` | `create_intake_note_record` | `persist_intake_note_record` (34) |
| 2 | `source_ingestion` | `source_ingestion_records` | `create_source_ingestion_record` | `persist_source_ingestion_record` (24) |
| 3 | `evidence_reference` | `evidence_references` | `create_draft` | `persist_evidence_reference` (21) |
| 4 | `agent_task_queue` | `agent_task_queue_records` | `create_agent_task_queue_record` | `persist_agent_task_queue_record` (27) |
| 5 | `review_bundle` | `review_bundle_records` | `create_review_bundle_record` | `persist_review_bundle_record` (30) |
| 6 | `reviewer_decision` | `internal_reviewer_decision_records` | `create_internal_reviewer_decision_record` | `persist_internal_reviewer_decision_record` (33) |

**`review_records` is deliberately out of scope.** This layer imports and calls **no Phase 22 review
writer**, writes **no `review_records` row**, and writes **no `agent_run_records` row**. Approval and
agent execution remain owned by their own boundaries.

The stages are **linearly dependent**: a halting stage stops every later stage, and the result
reports `halted_after_stage`.

---

## Public entry point

```python
from peak.workflows import ManagedRecordWorkflowRequest, run_managed_record_workflow

result = run_managed_record_workflow(request, *, session_factory=None)
# -> ManagedRecordWorkflowResult
```

`session_factory` is a zero-arg callable returning a SQLAlchemy `Session`. It is passed straight
through to the narrow writers, which own all session handling, transaction scope, and rollback.

**There is no ambient-DSN fallback.** If a stage's gate is on and no `session_factory` was injected,
that stage is denied (`missing_session_factory`) *before* any connection is opened. Standard
validation therefore needs **no live database credentials and no network**.

Expected governance failures are **typed denials, not exceptions**.

### `ManagedRecordWorkflowRequest`

| Field | Meaning |
|---|---|
| `owner_id`, `client_id`, `engagement_id` | tenant identity; required |
| `authorization_scope` | required; `revoked` is refused outright |
| `requested_by`, `requester_role` | requester traceability; required |
| `workflow_id` | optional short safe id; backs deterministic stage-key derivation |
| `subject_record_id` | the stored `Engagement` id (defaults to `engagement_id`) |
| `intake_note_payload` | Phase 34 `IntakeNoteDraft` |
| `source_ingestion_payload` | Phase 23 `SourceIngestionDraft` |
| `evidence_payload` | Phase 18 `EvidencePersistenceDraft` |
| `agent_task_payload` | Phase 26 `AgentTaskQueueDraft` |
| `review_bundle_payload` | Phase 29 `ReviewBundleDraft` |
| `reviewer_decision_payload` | Phase 32 `InternalReviewerDecisionDraft` |
| `persistence_gates` | `{stage: bool}`; missing == `False` == plan-only |
| `stage_idempotency_keys` | optional `{stage: key}` explicit keys |
| `strict_mode` | when `True`, any stage warning halts the workflow |
| `source_phase`, `lifecycle_status` | passed through to the `ControlledWriteRequest` |

The request **never accepts** raw client files, binary blobs, DB URLs, credentials, raw SQL, LLM
prompts, AgentNet resolver credentials, final client-facing language, or arbitrary workflow JSON
blobs.

---

## Upstream handoff: already-shaped drafts

Stage payloads are **already-shaped drafts**, produced upstream by the existing DB-free boundaries.
Phase 35 does **not** re-invoke those planners, and deliberately does not refactor them:

| DB-free boundary | Phase 35 posture |
|---|---|
| Engagement packet ingestion (P23) | **Handoff.** Caller supplies the derived `SourceIngestionDraft`. |
| Evidence normalization (P14) + evidence persistence mapping (P18) | **Handoff.** Caller supplies the mapped `EvidencePersistenceDraft`. |
| Agent task queue readiness (P26) | **Handoff.** Caller supplies the `AgentTaskQueueDraft`. |
| Review orchestration planning (P29) | **Handoff.** Caller supplies the `ReviewBundleDraft`. |
| Internal reviewer decision planning (P32) | **Handoff.** Caller supplies the `InternalReviewerDecisionDraft`. |
| Intake note drafting (P34) | **Handoff.** Caller supplies the `IntakeNoteDraft`. |

Rationale: the Phase 25/28/31 packet processor already sequences those DB-free planners and emits
exactly these drafts. Re-deriving them here would duplicate a stable path and pull broad earlier
phases into a workflow-integration change. Accepting shaped drafts keeps Phase 35 small, typed, and
auditable. Each payload is still type-checked against the exact draft class its narrow writer
accepts, so a mistyped payload is rejected before any DB connection is opened.

---

## Persistence gates

Gates are **explicit and per-stage**. The default is **plan-only and no-side-effect** — an absent or
`False` gate means the stage is planned and no writer is called. **No stage can silently escalate
from plan-only to persistence.**

| Situation | Stage outcome | Writer called? |
|---|---|---|
| No payload, gate off | `skipped` | no |
| Payload present, gate off | `planned` | no |
| Gate on, payload missing | `denied` (`missing_stage_payload`) | no |
| Gate on, payload unsafe / identity mismatch | `denied` | no |
| Gate on, no `session_factory` | `denied` (`missing_session_factory`) | no |
| Gate on, payload safe, factory injected | `persisted` / `replayed` / `conflicted` / `denied` / `failed_before_write` / `write_outcome_uncertain` | yes |
| Earlier stage halted | `halted` | no |

Payload safety and identity checks run in **plan-only mode too**, so an unsafe payload is surfaced
before anyone turns its gate on. Neither mode opens a database connection when it denies.

---

## Idempotency key derivation

Every key this layer produces is **stage-namespaced**:

```
wf35::<stage>::<stage-local component>
```

The namespace prefix means a single string can never be reused across two tables/actions — an
`intake_note` key and a `review_bundle` key are distinct even if the caller passes the same literal.

The rule, in order:

1. **Explicit key** — if `stage_idempotency_keys[stage]` is present and non-blank, it is respected
   as the stage-local component: `wf35::<stage>::<explicit key>`.
2. **Derived key** — otherwise the key is
   `wf35::<stage>::<workflow_id>::<fingerprint>`, where `<fingerprint>` is the first 16 hex
   characters of a SHA-256 over the stage's **safe, stable, non-content** fields:

   | Stage | Fingerprint fields |
   |---|---|
   | `intake_note` | `note_type`, `note_source`, `captured_by`, `source_ref`, `source_ingestion_record_id` |
   | `source_ingestion` | `packet_reference_id`, `packet_schema_name`, `packet_schema_version`, `packet_hash` |
   | `evidence_reference` | `source_reference_id`, `evidence_type`, `operational_area`, `inventory_process_area` |
   | `agent_task_queue` | `agent_name`, `workflow`, `task_type`, `requested_action` |
   | `review_bundle` | `packet_processing_receipt_ref`, `reviewer_role`, `review_scope` |
   | `reviewer_decision` | `review_bundle_ref`, `review_bundle_record_id`, `reviewer_role`, `decision_intent` |

   Note bodies, summaries, and any prose are **excluded** from the fingerprint. It exists to make a
   key stable and collision-resistant, not to fingerprint stored content — each narrow writer still
   computes its own full `payload_fingerprint` for replay-vs-conflict detection.
3. **Neither** — with no `workflow_id` and no explicit key there is nothing deterministic to derive
   from, so the stage is **denied** (`missing_stage_idempotency_key`) rather than given a random key.
4. A key longer than the writers' 128-character bound is denied (`idempotency_key_too_long`).

Consequences, by design:

- **Replay** — the same workflow and the same payload derive the same key, so a re-run returns each
  writer's `idempotent_replay` and creates **no duplicate row**.
- **Conflict** — an *explicit* stage key reused with a changed payload produces the writer's
  `idempotency_conflict`, which halts the dependent stages.

---

## Authorization and identity propagation

Every stage propagates `owner_id`, `client_id`, `engagement_id`, `authorization_scope`,
`requested_by`, `requester_role`, and the derived stage idempotency key into the Phase 17
`ControlledWriteRequest`.

**This layer never weakens writer authorization.** Each narrow writer still loads the stored
`Engagement` named by `subject_record_id` and compares `request.authorization_scope` against the
stored `authorization_scope`. **The stored Engagement remains the authorization anchor**, and
**identity matching is necessary but not sufficient**.

Pre-flight identity checks are defense in depth, run before any writer is invoked:

- every stage payload's `owner_id` / `client_id` / `engagement_id` must equal the workflow's;
- every payload carrying `authorization_scope` must match the workflow's;
- stage refs must be short safe refs/IDs;
- **cross-tenant and cross-engagement payloads are denied before any write**.

---

## Result contract

`ManagedRecordWorkflowResult` reports `outcome` (`denied` / `planned` / `persisted` / `partial` /
`halted`), `permitted`, `reason_code`, the identity echo, and the full stage bookkeeping:
`stages_requested`, `stages_planned`, `stages_skipped`, `stages_persisted`, `stages_replayed`,
`stages_denied`, `stages_conflicted`, `stages_halted`, and `halted_after_stage`.

It also carries `stage_results`, sanitized `receipts` by stage, `created_record_refs` by stage
(server-assigned ids only, never content), `table_write_counts` by controlled table,
`stage_idempotency_keys`, `warnings`, and `reasons`.

Side-effect flags report **actual behavior**: `database_connection_made`, `sql_execution_made`,
`database_write_made`, `stored_record_created`. The following are **always false** —

`review_records_write_made`, `agent_run_records_write_made`, `review_approval_made`,
`client_facing_output_created`, `financial_verification_made`, `capsule_publication_made`,
`agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`.

### What a result never echoes

Intake note body / `note_text`, raw packet payload, raw evidence or interview text, source bytes,
generated agent output, credentials or secrets, DSNs, raw SQL, stack traces, final client-facing
language, and approval decisions. Denials report only a **field name and a marker category** — never
the offending value. Writer reasons and warnings are re-scanned by this layer and replaced with a
category-only placeholder if they would ever carry an unsafe marker.

---

## Managed MySQL posture

Phase 35 orchestrates durable records intended for **managed remote MySQL** environments. It changes
none of the persistence rubric:

- **Managed remote MySQL is the operational data store** for operational client/engagement data.
- **Client Isolation Option A** (a shared managed database per environment with strict tenant
  columns and authorization gates) remains the **default**.
- **SQLite is not the production-readiness proof path** — it is a fast local structural smoke path
  only. The Phase 35 test harness uses a temporary SQLite database in exactly that spirit.
- **Managed MySQL test/staging validation is required** before treating DB-backed functionality as
  production-ready. The **production DB is not the main smoke-test target**.
- Standard `make validate` requires **no live DSN and no network**; the managed-MySQL targets
  (`db-check-managed-test`, `managed-mysql-smoke`, `managed-mysql-migration-check`) remain **opt-in
  and are not part of `make validate`**.
- Phase 35 adds **no DSN, no production DB write path, and no cleanup/delete path**.

See [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md),
[`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md), and
[`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md).

---

## AgentNet publication policy

Phase 35 **does not alter the Peak-operated AgentNet publication policy** and adds **no publishing
code**. Clients do not operate any AgentNet publishing tools; the client authorizes Peak in the
consulting agreement to act as authorized capsule/node publisher; Peak operates all publishing
workflows as a managed service. There is no client-facing AgentNet publisher UI, no client-held
publishing credentials, no client-operated resolver publication tools, and no direct client
publication path. Publication remains deferred behind future controlled publication gates.

See [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## Validation

```bash
make validate-phase35   # structural + plan-only always; DB-backed via .venv
```

The DB-backed layer builds a **temporary local SQLite database** and is skipped with instructions
when SQLAlchemy is absent (still exiting 0). SQLite here is a **local structural smoke path only,
not production proof**.
