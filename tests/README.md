# Tests

Validation for the source assets. Deliberately dependency-light: Python standard
library plus `jsonschema` (which brings `referencing`). No pytest, no database, no API
server, no network.

**No committed example data.** The repo stores source assets only. Where representative
objects are needed, the harnesses build **synthetic fixtures at runtime**
([`synthetic_fixtures.py`](synthetic_fixtures.py)) and write them to a temporary
directory that is auto-deleted. Nothing is stored. See
[`../docs/FIXTURE_STRATEGY.md`](../docs/FIXTURE_STRATEGY.md).

Thirty-two harnesses, run together by `make validate`:

- `validate_phase1.py` — schemas + synthetic object fixtures.
- `validate_phase2.py` — schemas + a synthetic `EngagementPacket`.
- `validate_phase3_prompts.py` — prompt-contract inventory (stdlib-only).
- `validate_phase4_outputs.py` — output-structure spec, synthetic (stdlib-only).
- `validate_phase5_runner.py` — packet-runner smoke check on a temp fixture (stdlib-only).
- `validate_phase6_docs.py` — consultant-guide doc check (stdlib-only).
- `validate_phase7_policy.py` — repo-hygiene / data-artifact guard (stdlib-only).
- `validate_phase8_architecture.py` — controlled-data architecture doc check (stdlib-only).
- `validate_phase9_governance.py` — governance-state contract check (jsonschema + stdlib).
- `validate_phase10_database_plan.py` — database-plan doc check (stdlib-only).
- `validate_phase11_db_scaffold.py` — MySQL DB-scaffold check (stdlib-only; `make db-check`).
- `validate_phase12_agentnet_mcp_boundary.py` — AgentNet MCP governance-boundary check (stdlib-only).
- `validate_phase13_agent_harness.py` — agent-execution-harness scaffold check (stdlib-only).
- `validate_phase14_evidence_worker.py` — evidence-normalization-worker check (stdlib-only).
- `validate_phase15_review_gate.py` — QA / review-gate check (stdlib-only).
- `validate_phase16_review_persistence.py` — review-persistence-boundary check (stdlib-only).
- `validate_phase17_controlled_db_writer.py` — controlled-DB-writer-boundary check (stdlib-only).
- `validate_phase18_evidence_persistence.py` — evidence-persistence-mapping check (stdlib-only).
- `validate_phase19_agent_run_persistence.py` — agent-run-persistence-mapping check (stdlib-only).
- `validate_phase20_agent_run_writer.py` — controlled-DB agent-run-writer check (structural
  always; DB-backed when SQLAlchemy is present).
- `validate_phase21_evidence_writer.py` — controlled-DB evidence-writer check (structural
  always; DB-backed when SQLAlchemy is present).
- `validate_phase22_review_writer.py` — controlled-DB review-writer check (structural always;
  DB-backed when SQLAlchemy is present).
- `validate_phase23_packet_ingestion.py` — engagement-packet-ingestion-boundary check (stdlib-only).
- `validate_phase24_source_ingestion_writer.py` — controlled-DB source-ingestion-writer check
  (structural always; DB-backed when SQLAlchemy is present).
- `validate_phase25_packet_processing_orchestrator.py` — controlled packet-processing
  orchestrator check (structural + plan-only always; DB-backed when SQLAlchemy is present).
- `validate_phase26_agent_task_queue_readiness.py` — agent task queue / execution readiness
  boundary check (stdlib-only; DB-free — no database layer).
- `validate_phase27_agent_task_queue_writer.py` — controlled-DB agent-task-queue-writer check
  (structural always; DB-backed when SQLAlchemy is present).
- `validate_phase28_packet_task_queue_integration.py` — packet → task queue orchestration
  integration check (structural + plan-only always; DB-backed when SQLAlchemy is present).
- `validate_phase29_review_orchestration_boundary.py` — packet-derived review orchestration
  boundary check (stdlib-only; DB-free — no database layer).
- `validate_phase30_review_bundle_writer.py` — controlled-DB review-bundle-writer check
  (structural always; DB-backed when SQLAlchemy is present).
- `validate_phase31_packet_review_bundle_integration.py` — packet → review bundle orchestration
  integration check (structural + plan-only always; DB-backed when SQLAlchemy is present).
- `validate_phase32_internal_reviewer_decision_boundary.py` — internal reviewer decision boundary
  check (stdlib-only; DB-free — no database layer).
- `validate_phase33_internal_reviewer_decision_writer.py` — controlled-DB
  internal-reviewer-decision-writer check (structural always; DB-backed when SQLAlchemy is present).
- `validate_phase34_intake_note_writer.py` — controlled-DB intake-note-writer check (structural
  always; DB-backed when SQLAlchemy is present).
- `validate_phase34_managed_mysql_rubric.py` — managed-MySQL persistence rubric + Peak-operated
  AgentNet publication policy check (stdlib-only; credential-free; no live network).
- `validate_phase35_managed_record_workflow.py` — governed managed-record workflow integration check
  (structural + plan-only always; DB-backed when SQLAlchemy is present).
- `validate_phase36_internal_assessment_report_planning.py` — internal assessment report planning
  boundary check (stdlib-only; DB-free and network-free).
- `validate_phase37_internal_assessment_report_draft_writer.py` — controlled-DB
  internal-assessment-report-draft-writer check (structural always; DB-backed when SQLAlchemy is
  present).
- `validate_phase38_internal_report_review_packet_writer.py` — controlled-DB
  internal-report-review-packet-writer check (structural always; DB-backed when SQLAlchemy is
  present).
- `validate_phase39_internal_report_review_packet_decision_writer.py` — controlled-DB
  packet-decision-writer check (structural always; DB-backed when SQLAlchemy is present).
- `validate_phase40_internal_report_review_workflow.py` — end-to-end internal report review
  workflow integration check (structural always; DB-backed when SQLAlchemy is present).
- `validate_phase41_managed_mysql_production_parity.py` — managed MySQL production-parity check
  (stdlib-only; offline, credential-free, no network).
- `validate_phase42_governed_mysql_collation_policy.py` — governed MySQL collation policy +
  audit check (stdlib-only; offline, credential-free, no network).
- `validate_phase43_production_mysql_collation_verification.py` — production MySQL collation
  verification check (stdlib-only; offline, credential-free, no network).
- `validate_phase44_governed_identifier_collation_migration.py` — governed identifier collation
  migration check (offline, credential-free, no network).

## `synthetic_fixtures.py`

Not a test — a **module** that builds clearly-synthetic, schema-conforming objects in
memory (ids/labels carry a `synthetic` marker). It is code, not stored data, and is
imported by the phase 1/2 harnesses.

## `validate_phase1.py`

1. **Schema self-check** — every `schemas/*.schema.json` is valid draft 2020-12.
2. **Synthetic fixture conformance** — a synthetic instance of each object is written to
   a temp dir and validated against its schema.
3. **Prefix lint** — synthetic ids/references use their expected prefixes
   (`intake_`, `evid_`, `intv_`, `vobs_`, `wobs_`, `isp_`).

## `validate_phase2.py`

Validates a **synthetic** `EngagementPacket`, which composes the object schemas via
local relative `$ref`. Refs are resolved **offline** via a `referencing` registry built
from every schema's `$id`.

1. **Schema self-check** — all schemas, including `engagement-packet.schema.json`.
2. **Packet conformance** — a synthetic packet (temp file, auto-deleted) validates with
   `$ref`s resolved.
3. **Packet referential lint (blocking)** — every nested `evidence_references` id
   resolves within the packet; every nested `related_intake_id` equals
   `client_intake.intake_id`; ids use expected prefixes.

## `validate_phase3_prompts.py`

Inventory check for the prompt contracts in [`../prompts/`](../prompts/): every required
contract exists and contains all ten required section headings plus a fenced reusable
body. Structure only.

## `validate_phase4_outputs.py`

Validates the **output-structure contract**. Peak commits no sample outputs, so for each
artifact type the harness holds the required section spec, **generates a synthetic
document** into a temp dir, and confirms it contains every required section plus a
synthetic evidence citation. Structure only.

## `validate_phase5_runner.py`

Smoke check for the packet runner ([`../tools/packet_runner.py`](../tools/packet_runner.py)).
The runner has no demo/sample mode, so this test generates a **temporary synthetic
packet** with `tempfile`, passes it via `--packet`, then deletes it. It confirms the
runner exists, exits 0, the output contains the fixture `packet_id`, the prompt-contract
list, and the no-LLM / no-AgentNet / not-stored disclaimers, and that the run **writes
no files**.

## `validate_phase6_docs.py`

Doc check for the consultant guide
([`../docs/CONSULTANT_WORKFLOW.md`](../docs/CONSULTANT_WORKFLOW.md)): required sections
plus honesty/scope phrases. Structure only.

## `validate_phase7_policy.py` (repo-hygiene / data-artifact guard)

Enforces that the repo stores **source assets only**:

1. **Policy docs present** — [`../docs/DATA_HANDLING_POLICY.md`](../docs/DATA_HANDLING_POLICY.md)
   and [`../docs/FIXTURE_STRATEGY.md`](../docs/FIXTURE_STRATEGY.md) exist with their
   required markers.
2. **No stored data artifacts** — forbidden paths must not exist: `examples/`, the old
   redaction guide (removed), any `*.example.json` / `*.example.md`, or `redacted`
   files. The guard fails if they reappear.
3. **Redaction framing stays removed** — tracked docs/code must not reintroduce it (a
   historical note in the two policy docs is allowed).

This is the guard that keeps the repo clean of data artifacts. It does not attempt to
detect real client data inside a supposedly-synthetic file — that remains a human
discipline plus the "client data never in the repo" policy.

## `validate_phase8_architecture.py`

Doc check for the Phase 8 controlled-data architecture:
[`../docs/CONTROLLED_DATA_ARCHITECTURE.md`](../docs/CONTROLLED_DATA_ARCHITECTURE.md),
[`../docs/RESOLVER_CAPSULE_ARCHITECTURE.md`](../docs/RESOLVER_CAPSULE_ARCHITECTURE.md),
[`../docs/ENGAGEMENT_DATA_MODEL.md`](../docs/ENGAGEMENT_DATA_MODEL.md), and
[`../docs/SOURCE_SYSTEM_CAPSULIZATION.md`](../docs/SOURCE_SYSTEM_CAPSULIZATION.md). It
confirms each doc exists with its required markers, re-asserts source-only discipline (no
`examples/`, no removed redaction guide, no `*.example.*` artifacts), checks the
source-only phrase in the README, and fails if any file claims AgentNet is *implemented*
(explicit completion claims; negated policy statements and future-phase descriptions are
fine). The Phase 8 architecture-contract schemas are covered by the schema self-check in
phases 1–2; they carry no fixtures.

## `validate_phase9_governance.py`

Checks the Phase 9 governance-state contracts:
[`../docs/GOVERNANCE_STATES.md`](../docs/GOVERNANCE_STATES.md) and
[`../docs/STATE_TRANSITIONS.md`](../docs/STATE_TRANSITIONS.md) exist; the governance
schemas (`governance-state`, `authorization-scope`, `review-status`, `lifecycle-status`)
pass `check_schema`; all **eight** state families contain their required enum values; the
key transition arrows and agent guardrail phrases appear in `STATE_TRANSITIONS.md`; the
repo stays source-only; and AgentNet is not claimed as implemented. Uses `jsonschema`
(already a dev dep) plus stdlib.

## `validate_phase10_database_plan.py`

Doc check for the Phase 10 database-planning docs (`DATABASE_IMPLEMENTATION_PLAN.md`,
`DATABASE_RECORD_MODEL.md`, `DATABASE_ACCESS_AND_AUDIT.md`,
`DATABASE_TO_RESOLVER_MAPPING.md`): each exists with its required markers; the strategic
phrases are present (source-only, controlled database, private resolver capsules,
public-but-segregated, private resolver option, no client data in Git, human review
gates, agent permission limits); the repo stays source-only **with no DB implementation**
(no `*.sql`/`*.db`, no `migrations/`, no DB config files); and AgentNet is not claimed as
implemented. Stdlib-only. (Note: `alembic.ini` is an allowed Phase 11 source asset and is
not treated as a forbidden DB config.)

## `validate_phase11_db_scaffold.py` (`make db-check`)

Structural check for the Phase 11 MySQL scaffold: the `peak/db/` package (base, enums,
models, session), `alembic.ini` + `alembic/env.py` + the initial migration, `.env.example`,
`requirements.txt`, and `docs/DATABASE_SCAFFOLD.md` all exist; `.env` is gitignored and
untracked while `.env.example` is allowed; there is **no stored data, no database file, no
seed/`INSERT` in migrations, and no obvious committed credential**; the `peak/db/enums.py`
values stay aligned to the Phase 9 schema enums; MySQL is documented; and AgentNet is not
claimed as implemented. If SQLAlchemy **and** Alembic are installed it additionally
imports them and `peak.db.models`, confirms `Base.metadata` defines **exactly** the 11
expected tables with unique names, and asserts every table carries the required
governance/audit columns (`owner_id`, `authorization_scope`, `review_status`,
`lifecycle_status`, `created_at`, `updated_at`); if the dependencies are absent that step
is skipped (structural check still runs). The structural portion is stdlib-only; the
dependency-backed portion runs when the `requirements.txt` packages are installed — e.g.
`make validate PYTHON=.venv/bin/python` (see
[`../docs/DATABASE_SCAFFOLD.md`](../docs/DATABASE_SCAFFOLD.md)).

## `validate_phase12_agentnet_mcp_boundary.py`

Boundary check for Peak's **governance wrapper** around the **existing AgentNet MCP
connector** (a separate repo; not reimplemented here). Confirms the `peak/agentnet/`
scaffold files exist and compile; imports the package and asserts `KNOWN_MCP_TOOLS` is
**exactly** `agentnet.resolve` / `agentnet.resolve_history` / `agentnet.validate_capsule`;
exercises the governance guards (a valid request is permitted; publication-style and
unknown tools, missing `owner_id`, and revoked/archived lifecycle are rejected); confirms
the **no-network mock boundary** always reports `live_call_made = False` and
`agentnet_integration_active = False`; scans the package for **network imports, credential
reads, or connector imports** (there are none); checks the boundary docs carry the
required language (no live calls, no capsule publication, AgentNet integration is not
complete); and re-asserts source-only discipline. Stdlib-only; **makes no network call**.
See [`../docs/AGENTNET_MCP_BOUNDARY.md`](../docs/AGENTNET_MCP_BOUNDARY.md).

## `validate_phase13_agent_harness.py`

Scaffold check for the Peak internal **agent execution harness** (`peak/agents/`; no live
execution). Confirms the package files exist and compile; imports the package and asserts
the registry lists **exactly** the 10 known agents/workers, each with a
workflow/purpose/output/review default and (where set) an existing prompt contract;
exercises the **no-op mock executor** (a permitted task returns `llm_call_made`,
`agentnet_call_made`, `database_write_made`, and `client_facing_output_created` all
`False`, with `output_status = draft` / `review_status = needs_review`); confirms
governance rejects an unknown agent, missing `owner_id`, revoked/archived lifecycle,
`client_facing_output_requested`, and `llm_execution_allowed`; scans the package for
**network and database imports** (there are none); checks the docs describe AgentNet as
not-yet-implemented; and re-asserts source-only discipline. Stdlib-only; **makes no live
call**. See [`../docs/AGENT_EXECUTION_HARNESS.md`](../docs/AGENT_EXECUTION_HARNESS.md).

## `validate_phase14_evidence_worker.py`

Check for the first production-shaped worker, the **Evidence Normalization Worker**
(`peak/workers/`). Confirms the package files exist and compile and the package imports;
normalizes a **valid in-memory synthetic request** and asserts the result is **review-gated**
(`permitted`, `output_status = draft`, `review_status = needs_review`, `authoritative`,
`client_facing_approved`, `capsule_candidate_ready`, `database_write_made`, `llm_call_made`,
`agentnet_call_made`, `network_call_made`, `capsule_publication_made` all as required);
confirms governance rejects missing `owner_id`/`client_id`/`engagement_id`, rejected
`review_status`, revoked/archived/deleted `lifecycle_status`, missing `raw_evidence` /
`source_reference`, and a request↔source scope mismatch; scans the package for
**network/database/LLM imports or credentials** (there are none); checks the docs carry the
review-gate phrases; and re-asserts source-only discipline. Stdlib-only; **no live call and
no stored data**. See
[`../docs/EVIDENCE_NORMALIZATION_WORKER.md`](../docs/EVIDENCE_NORMALIZATION_WORKER.md).

## `validate_phase15_review_gate.py`

Check for the **QA / Review Gate** (`peak/review/`). Confirms the package files exist and
compile and the package imports; evaluates a **valid in-memory synthetic** `approve_internal`
request and asserts the result is **production-shaped but no-side-effect** (`permitted`,
`next_review_status = approved_internal`, `authoritative = true` for internal reliance only,
`client_facing_approved` and `capsule_candidate_ready` `false`, and `database_write_made`,
`llm_call_made`, `agentnet_call_made`, `network_call_made`, `capsule_publication_made`,
`client_facing_output_created` all `false`); confirms governance rejects missing
`owner_id`/`client_id`/`engagement_id`/`requested_by`/`reviewer_role`, a mismatched subject
scope, each prohibited decision (`client_facing_approve`, `publish_capsule`,
`verify_financial_impact`, `approve_authoritative_external`), revoked/archived lifecycle, and
`approve_internal` with an incomplete/missing checklist — while `reject` is permitted (with
warnings) despite an incomplete checklist; scans the package for **network/database/LLM
imports or credentials** (there are none); checks the docs carry the no-side-effect phrases;
and re-asserts source-only discipline. Stdlib-only; **no live call and no stored review
records**. See [`../docs/QA_REVIEW_GATE.md`](../docs/QA_REVIEW_GATE.md).

## `validate_phase16_review_persistence.py`

Check for the **Review Persistence Boundary** (`peak/review/persistence_contracts.py`,
`persistence_governance.py`, `review_record_mapper.py`). Confirms the files exist and compile
and the package imports; prepares persistence for a **valid in-memory** permitted
`ReviewGateResult` + `StoredReviewSubjectSnapshot` and asserts the result is **DB-aware but
not DB-writing** (`permitted`, `write_plan.target_table = review_records`,
`review_record_id`/`created_at` `None`, `requires_controlled_db_writer = true`, and
`database_write_made`, `database_connection_made`, `stored_review_record_created`,
`llm_call_made`, `agentnet_call_made`, `network_call_made`, `capsule_publication_made`,
`client_facing_output_created` all `false`); confirms governance rejects missing
`owner_id`/`client_id`/`engagement_id`/`requested_by`/`reviewer_role`, a missing
`subject_snapshot`/`review_gate_result`, an owner/client/engagement mismatch, a
`request.authorization_scope` that does not match the subject's `stored_authorization_scope`
(and a missing stored scope), prohibited request/subject lifecycle statuses, an unpermitted
gate result, a gate result with any call/write flag set true, and an unknown persistence
action — and that a denied request yields no write plan (side-effect-free denial); scans the
new files for **network/database/LLM imports or credentials** (there are none); checks the
docs carry the DB-aware-not-DB-writing phrases; and re-asserts source-only discipline.
Stdlib-only; **no live database read/write and no stored review records**. See
[`../docs/REVIEW_PERSISTENCE_BOUNDARY.md`](../docs/REVIEW_PERSISTENCE_BOUNDARY.md) and
[`../docs/DB_BACKED_REVIEW_SCOPE_POLICY.md`](../docs/DB_BACKED_REVIEW_SCOPE_POLICY.md).

## `validate_phase17_controlled_db_writer.py`

Check for the **Controlled DB Writer Boundary** (`peak/persistence/`). Confirms the package
files exist and compile and the package imports; asserts the **table/action allowlist** holds
exactly the expected allowed tables/actions and its `is_allowed_*` / `is_prohibited_*` helpers
behave; prepares a controlled write for a **valid in-memory** request and asserts the result
is **DB-aware but not DB-writing** (`permitted`, `write_plan.requires_controlled_db_writer =
true`, and `database_write_made`, `database_connection_made`, `sql_execution_made`,
`stored_record_created`, `llm_call_made`, `agentnet_call_made`, `network_call_made`,
`capsule_publication_made`, `client_facing_output_created` all `false`, with the audit draft's
`audit_record_id`/`created_at` `None`); confirms governance rejects each missing required
field (including `idempotency_key`), an owner/client/engagement mismatch, a
`request.authorization_scope` that does not match the subject's `stored_authorization_scope`,
prohibited request/subject lifecycle statuses, prohibited tables (`clients`, `engagements`,
`financial_impact_estimates`, `resolver_capsule_records`), unlisted tables/actions, and
publish / client-facing-approve / verify-financial / delete / raw_sql / migrate / seed
actions — and that a denied request yields no write plan (side-effect-free denial); scans the
package for **network / database / SQLAlchemy / `peak.db` / LLM imports or credentials** (there
are none); checks the docs carry the boundary phrases; and re-asserts source-only discipline.
Stdlib-only; **no live database connection, no SQL execution, and no stored records**. See
[`../docs/CONTROLLED_DB_WRITER_BOUNDARY.md`](../docs/CONTROLLED_DB_WRITER_BOUNDARY.md) and
[`../docs/CONTROLLED_WRITE_ALLOWLIST.md`](../docs/CONTROLLED_WRITE_ALLOWLIST.md).

## `validate_phase18_evidence_persistence.py`

Check for the **Evidence Persistence Mapping** (`peak/evidence/`), which connects the Phase 14
normalized evidence output to the Phase 17 controlled writer boundary. Confirms the package
files exist and compile and the package imports; maps a **valid in-memory** normalized
evidence result + stored parent subject snapshot and asserts the result is **DB-aware but not
DB-writing** (`permitted`; the `EvidencePersistenceDraft` is review-gated with
`evidence_record_id`/`created_at` `None`, `output_status = draft`, `review_status =
needs_review`, `authoritative`/`client_facing_approved`/`capsule_candidate_ready` `false`; the
Phase 17 `ControlledWriteRequest` targets `evidence_references` / `create_draft`; the plan's
`requires_controlled_db_writer = true`; and `database_write_made`, `database_connection_made`,
`sql_execution_made`, `stored_record_created`, `llm_call_made`, `agentnet_call_made`,
`network_call_made`, `capsule_publication_made`, `client_facing_output_created` all `false`);
confirms governance rejects each missing required field (including `idempotency_key`), a
subject **or** normalized-record owner/client/engagement mismatch, a
`request.authorization_scope` that does not match the subject's `stored_authorization_scope`,
prohibited lifecycle statuses, an unpermitted or side-effect-flagged `normalization_result`,
and a normalized record that is authoritative / client-facing-approved / capsule-ready or off
the review gate — and that a denied request yields no draft/request/plan (side-effect-free
denial); scans the package for **network / database / SQLAlchemy / `peak.db` / LLM imports or
credentials** (there are none); checks the docs carry the mapping phrases; and re-asserts
source-only discipline. Stdlib-only; **no live database connection, no SQL execution, and no
stored records**. See [`../docs/EVIDENCE_PERSISTENCE_MAPPING.md`](../docs/EVIDENCE_PERSISTENCE_MAPPING.md)
and [`../docs/EVIDENCE_WRITE_PLAN_POLICY.md`](../docs/EVIDENCE_WRITE_PLAN_POLICY.md).

## `validate_phase19_agent_run_persistence.py`

Check for the **Agent Run Persistence Mapping** (`peak/agents/persistence_contracts.py`,
`persistence_governance.py`, `agent_run_mapper.py`), which connects the Phase 13 agent run
output to the Phase 17 controlled writer boundary. Confirms the new files exist and compile
and `peak.agents` imports; maps a **valid in-memory** agent task result + run draft + stored
subject snapshot and asserts the result is **DB-aware but not DB-writing** (`permitted`; the
`AgentRunPersistenceDraft` is review-gated with `agent_run_record_id`/`created_at` `None`,
`output_status = draft`, `review_status = needs_review`; the Phase 17 `ControlledWriteRequest`
targets `agent_run_records` / `create_agent_run_record`; the plan's
`requires_controlled_db_writer = true`; and `database_write_made`, `database_connection_made`,
`sql_execution_made`, `stored_record_created`, `llm_call_made`, `agentnet_call_made`,
`network_call_made`, `capsule_publication_made`, `client_facing_output_created` all `false`);
confirms governance rejects each missing required field (including `idempotency_key`), a
subject **or** task-request owner/client/engagement mismatch, a `request.authorization_scope`
that does not match the subject's `stored_authorization_scope`, prohibited lifecycle statuses,
and an `AgentTaskResult` with a side-effect flag set or off the `draft` / `needs_review` gate
— and that a denied request yields no draft/request/plan (side-effect-free denial); scans the
new files for **network / database / SQLAlchemy / `peak.db` / LLM imports or credentials**
(there are none); checks the docs carry the mapping phrases; and re-asserts source-only
discipline. Stdlib-only; **no live database connection, no SQL execution, and no stored
records**. See [`../docs/AGENT_RUN_PERSISTENCE_MAPPING.md`](../docs/AGENT_RUN_PERSISTENCE_MAPPING.md)
and [`../docs/AGENT_RUN_WRITE_PLAN_POLICY.md`](../docs/AGENT_RUN_WRITE_PLAN_POLICY.md).

## `validate_phase20_agent_run_writer.py`

Check for the Phase 20 **controlled DB agent-run writer** (`peak/db/agent_run_writer.py`,
`peak/db/writer_contracts.py`). Runs in two layers. The **structural** layer (always,
stdlib-only) confirms the files exist and compile; that the Phase 19 agent-domain mapper
stays **DB-free** (no SQLAlchemy/Alembic/`peak.db` import — a regression guard); that the
writer imports no LLM/AgentNet/connector/network client or credential; that the
`002_agent_run_idempotency` migration is additive schema-only (no INSERT/seed, has
upgrade+downgrade, adds the unique idempotency index); that the docs carry the required
language; and that the repo stays source-only. The **DB-backed** layer runs only when
SQLAlchemy is importable: it builds a **temporary local SQLite database** from the models
(deleted afterward — nothing committed) and exercises real behavior — successful create
(exactly one row, server-stamped id/timestamp, stored `output_status=draft` /
`review_status=needs_review`, accurate receipt flags), idempotent replay (no second row),
conflicting replay (denied, existing row unchanged), DB-backed authorization (request scope
vs the stored `Engagement.authorization_scope`; missing stored/request scope; missing
subject), identity mismatches (owner/client/engagement/subject/task-request), the
table/action allowlist, draft-posture rejections, side-effect discipline (no unrelated table
mutation), and transaction/failure semantics (`failed_before_write`,
`write_outcome_uncertain`, and the `IntegrityError` race → replay/conflict). If SQLAlchemy is
absent the DB layer is skipped with instructions and the harness still exits 0. Run the full
suite with `make validate-phase20 PYTHON=.venv/bin/python`. See
[`../docs/AGENT_RUN_CONTROLLED_WRITER.md`](../docs/AGENT_RUN_CONTROLLED_WRITER.md) and
[`../docs/AGENT_RUN_IDEMPOTENCY_POLICY.md`](../docs/AGENT_RUN_IDEMPOTENCY_POLICY.md).

## `validate_phase21_evidence_writer.py`

Check for the Phase 21 **controlled DB evidence writer** (`peak/db/evidence_writer.py`,
`peak/db/writer_contracts.py`) — the same two-layer pattern as Phase 20, applied to
`evidence_references`. The **structural** layer confirms the files exist and compile; that the
Phase 18 evidence-domain mapper stays **DB-free**; that the writer imports no
LLM/AgentNet/connector/network client or credential; that the `003_evidence_idempotency`
migration is additive schema-only (no INSERT/seed, upgrade+downgrade, adds the unique index,
`down_revision = 002_agent_run_idem`); that the docs carry the required language; and that the
repo stays source-only. The **DB-backed** layer (when SQLAlchemy is importable) builds a
**temporary local SQLite database** (deleted afterward) and exercises real behavior —
successful create (exactly one row, server-stamped `evid_` id/timestamp, stored
`output_status=draft` / `review_status=needs_review` / `lifecycle_status=active`, mapped
columns, accurate receipt flags), idempotent replay, conflicting replay (denied, row
unchanged), DB-backed authorization (request scope vs stored `Engagement.authorization_scope`;
missing stored/request scope; missing subject; owner/client/engagement mismatch), the
table/action allowlist (wrong table/action + delete-/publish-/client-facing-/financial-like
actions), draft-posture rejections (bad output/review/lifecycle status, authoritative,
client-facing, capsule-ready, caller-supplied id/timestamp), side-effect discipline (no
unrelated table mutation), and transaction/failure semantics (`failed_before_write`,
`write_outcome_uncertain`, and the `IntegrityError` race → replay/conflict). Skips the DB layer
with instructions if SQLAlchemy is absent (still exits 0). Run the full suite with
`make validate-phase21 PYTHON=.venv/bin/python`. See
[`../docs/EVIDENCE_CONTROLLED_WRITER.md`](../docs/EVIDENCE_CONTROLLED_WRITER.md) and
[`../docs/EVIDENCE_IDEMPOTENCY_POLICY.md`](../docs/EVIDENCE_IDEMPOTENCY_POLICY.md).

## `validate_phase22_review_writer.py`

Check for the Phase 22 **controlled DB review writer** (`peak/db/review_writer.py`,
`peak/db/writer_contracts.py`) — the same two-layer pattern, applied to `review_records`. The
**structural** layer confirms the files exist and compile; that the Phase 16 review-persistence
mapper stays **DB-free**; that the writer imports no LLM/AgentNet/connector/network client or
credential; that the `004_review_idempotency` migration is additive schema-only (no INSERT/seed,
upgrade+downgrade, adds the unique index, `down_revision = 003_evidence_idem`); that the docs
carry the required language; and that the repo stays source-only. The **DB-backed** layer (when
SQLAlchemy is importable) builds a **temporary local SQLite database** (deleted afterward) and
exercises real behavior — successful create for `approve_internal` (one row, server-stamped
`rev_` id/timestamp, stored decision/authoritative/target_id/subject_record_type/new_status/
lifecycle/output_status, accurate receipt flags) and for a non-authoritative `reject`;
idempotent replay; conflicting replay (denied, row unchanged); DB-backed authorization (request
scope vs stored `Engagement.authorization_scope`; missing stored/request scope; missing subject;
owner/client/engagement mismatch); the table/action allowlist (wrong table/action +
delete-/publish-/client-facing-/financial-like actions); decision/posture rejections
(caller-supplied id/timestamp, client-facing/capsule flags, authoritative on a non-approve
decision, approve_internal without `approved_internal`, and the prohibited
`client_facing_approve`/`verify_financial_impact`/`publish_capsule` decisions); side-effect
discipline (no unrelated table mutation); and transaction/failure semantics
(`failed_before_write`, `write_outcome_uncertain`, and the `IntegrityError` race →
replay/conflict). Skips the DB layer with instructions if SQLAlchemy is absent (still exits 0).
Run the full suite with `make validate-phase22 PYTHON=.venv/bin/python`. See
[`../docs/REVIEW_CONTROLLED_WRITER.md`](../docs/REVIEW_CONTROLLED_WRITER.md) and
[`../docs/REVIEW_IDEMPOTENCY_POLICY.md`](../docs/REVIEW_IDEMPOTENCY_POLICY.md).

## `validate_phase23_packet_ingestion.py`

Check for the Phase 23 **engagement packet ingestion boundary** (`peak/ingestion/`).
Stdlib-only; no database. Confirms the package files exist and compile and `peak.ingestion`
imports; prepares an ingestion plan from a **valid in-memory** packet and asserts it is
no-side-effect (review-gated `SourceIngestionDraft` with `source_ingestion_record_id` /
`created_at` `None` and `output_status=draft` / `review_status=needs_review`; Phase 14
`EvidenceNormalizationRequest` objects derived from present sections with non-object items
skipped-with-warning; Phase 13 `AgentTaskRequest` objects for **known registry agents only**,
unknown agents skipped-with-warning, `llm_execution_allowed`/`client_facing_output_requested`
false; a Phase 17 `ControlledWriteRequest` for `source_ingestion_records` /
`create_source_ingestion_record` as a plan only; and `direct_database_write_made`,
`database_connection_made`, `sql_execution_made`, `stored_record_created`, `llm_call_made`,
`agentnet_call_made`, `network_call_made`, `capsule_publication_made`,
`client_facing_output_created` all `false`); confirms governance rejects each missing required
field (including `idempotency_key`), a packet-reference owner/client/engagement or
authorization-scope mismatch, prohibited lifecycle statuses, a non-dict payload, and
credential/secret keys (top-level and nested) — and that secret **values** are never echoed in
denial reasons; scans the package for **network / database / SQLAlchemy / `peak.db` / LLM
imports or credential values** (there are none); checks the docs carry the boundary phrases;
and re-asserts source-only discipline. See
[`../docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](../docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md)
and [`../docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md`](../docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md).

## `validate_phase24_source_ingestion_writer.py`

Check for the Phase 24 **controlled DB source-ingestion writer** (`peak/db/source_ingestion_writer.py`,
`peak/db/writer_contracts.py`) — the same two-layer pattern, applied to
`source_ingestion_records`. The **structural** layer confirms the files exist and compile; that
the Phase 23 ingestion package stays **DB-free**; that the writer imports no
LLM/AgentNet/connector/network client or credential value; that the `005_source_ingestion_idempotency`
migration is additive schema-only (no INSERT/seed, upgrade+downgrade, adds the unique index,
`down_revision = 004_review_idem`); that the docs carry the required language (including
**packet metadata only**); and that the repo stays source-only. The **DB-backed** layer (when
SQLAlchemy is importable) builds a **temporary local SQLite database** (deleted afterward) and
exercises real behavior — migration upgrade/downgrade/re-upgrade; successful create (one row,
server-stamped `ing_` id/timestamp, packet **metadata only** stored — never the full payload,
`source_reference_id` = packet reference id, stored `output_status=draft` /
`review_status=needs_review` / `lifecycle_status=active`, accurate receipt flags); idempotent
replay; conflicting replay (denied, row unchanged); DB-backed authorization (request scope vs
stored `Engagement.authorization_scope`; missing stored/request scope; missing subject;
owner/client/engagement mismatch); the table/action allowlist (wrong table/action +
delete-/publish-/client-facing-/financial-/raw_sql-like actions); posture/content rejections
(bad output/review/lifecycle status, authoritative, client-facing, capsule-ready, caller-supplied
id/timestamp, missing source reference, and injected `packet_payload` / `raw_packet_content` /
secret attributes — with secret values never echoed); side-effect discipline (no unrelated table
mutation); and transaction/failure semantics (`failed_before_write`, `write_outcome_uncertain`,
and the `IntegrityError` race → replay/conflict). Skips the DB layer with instructions if
SQLAlchemy is absent (still exits 0). Run the full suite with
`make validate-phase24 PYTHON=.venv/bin/python`. See
[`../docs/SOURCE_INGESTION_CONTROLLED_WRITER.md`](../docs/SOURCE_INGESTION_CONTROLLED_WRITER.md)
and [`../docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md`](../docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md).

## `validate_phase25_packet_processing_orchestrator.py`

Check for the Phase 25 **controlled engagement packet processing orchestrator**
(`peak/orchestration/`) — a controlled sequencing layer over the existing narrow boundaries,
not a generic importer/workflow engine/CRUD/write dispatcher. Runs in three layers. The
**structural** layer (always, stdlib-only) confirms the package files exist and compile; that
the Phase 23 ingestion package stays **DB-free** (regression); that the orchestrator imports no
network/LLM/AgentNet/connector client and **no top-level SQLAlchemy / `peak.db`** (the DB
writers are lazy-imported inside the persistence stages, so plan-only runs without SQLAlchemy);
that **no new migration** was added (Alembic head stays `005_source_ingestion_idem` — exactly
five migration files); that the docs carry the required language (controlled sequencing layer,
plan-only, no stage may silently escalate, preflight helpful-but-not-authoritative, stored
Engagement authorization authoritative, identity necessary-but-not-sufficient, no live
LLM/AgentNet/capsule/financial/client-facing); and that the repo stays source-only. The
**plan-only** layer (always, stdlib-only) runs `process_engagement_packet` on a **valid
in-memory** packet and asserts it is no-side-effect — a receipt with `orchestration_outcome =
planned`, the derived plan exposed (source draft, plan-only source `ControlledWriteRequest`
targeting `source_ingestion_records` / `create_source_ingestion_record`, Phase 14 evidence
requests, Phase 13 agent task requests for **known registry agents only**, unknown agents
skipped-with-warning, `llm_execution_allowed`/`client_facing_output_requested`/
`resolver_context_allowed` false), **every side-effect flag false**, and **no raw packet payload
sentinel** leaked into the receipt; that **no stage silently escalates** (persistence requested
under `plan_only=true` → `skipped_plan_only`; requested without `session_factory` →
`skipped_missing_session_factory`, not a failure; not-included → `skipped_not_requested`); that
agent-run persistence is deferred as `skipped_no_safe_contract_path`; and that denials
(secret-key packet, packet-reference owner/scope mismatch, revoked lifecycle, missing
`idempotency_key`) return an outcome of `denied` without echoing secret values. The **DB-backed**
layer runs only when SQLAlchemy is importable: it builds a **temporary local SQLite database**
(deleted afterward) and exercises controlled persistence **through the existing narrow writers
only** — Phase 24 source-ingestion (create → exactly one row + accurate DB flags with all
non-DB side-effect flags false; idempotent replay; conflicting key → writer `denied`
/`idempotency_conflict` → orchestration `partial`; stored-Engagement scope mismatch → writer
`denied`/`stored_scope_mismatch`, no row) and Phase 21 evidence (rows == normalization count,
receipts target `evidence_references` / `create_draft`, no source/agent/review rows; and
`skipped_no_safe_contract_path` when normalization is disabled). If SQLAlchemy is absent the DB
layer is skipped with instructions and the harness still exits 0. Run the full suite with
`make validate-phase25 PYTHON=.venv/bin/python`. See
[`../docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](../docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md)
and [`../docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md`](../docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md).

## `validate_phase26_agent_task_queue_readiness.py`

Check for the Phase 26 **Controlled Agent Task Queue / Execution Readiness Boundary**
(`peak/task_queue/`) — a DB-free readiness/queue-planning boundary over derived Phase 13
`AgentTaskRequest` objects, analogous to Phase 23. Stdlib-only; **no database** (Phase 26 writes
nothing and connects to nothing). The **structural** layer confirms the package files exist,
compile, and import; that the package imports no SQLAlchemy / Alembic / `peak.db` / live-or-mock
LLM / AgentNet / MCP / resolver / connector / network module; that the Phase 23 ingestion package
stays DB-free; that the Phase 25 commit is present in recent history; that **no Phase 26 migration**
was added (Phase 26 is a DB-free boundary; later phases such as Phase 27 legitimately add
migrations); and that the docs carry the required language. The **functional** layer runs
`prepare_agent_task_queue_plan` and asserts: a valid task becomes a review-gated,
`not_executed` / `execution_allowed=false` queue draft with no id/created_at and a deterministic
per-task idempotency key, plus a plan-only Phase 17 `ControlledWriteRequest` targeting
`agent_task_queue_records` / `create_agent_task_queue_record`; evidence-wired tasks reach
`ready_for_future_controlled_execution` (still not executable now); multiple tasks get distinct
keys; unknown agents are blocked (partial / all-blocked outcomes); request-level identity / scope /
idempotency / lifecycle denials and per-task `blocked_invalid_scope` / `blocked_lifecycle` /
`blocked_by_policy` (LLM / resolver / client-facing requested) / `blocked_missing_evidence`
behave; raw packet payload, raw evidence/interview text, source bytes, secret-like keys, and
execution/network/financial/publication intent keys are rejected without echoing values; and
**every side-effect flag stays `false`** across all outcomes. The **integration** layer feeds the
exact Phase 13 `AgentTaskRequest` objects produced by the Phase 23 ingestion boundary and surfaced
by the Phase 25 orchestrator (plan-only) into Phase 26 and confirms no side effects — verifying the
documented Phase 25 → Phase 26 handoff. It also re-asserts source-only discipline and that
`.claude/settings.local.json` stays untracked. See
[`../docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](../docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md)
and [`../docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md`](../docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md).

## `validate_phase27_agent_task_queue_writer.py`

Check for the Phase 27 **controlled DB agent-task-queue writer** (`peak/db/agent_task_queue_writer.py`,
`peak/db/writer_contracts.py`) — the same two-layer pattern as Phases 20–24, applied to
`agent_task_queue_records`. The **structural** layer confirms the files exist and compile; that the
Phase 26 `peak/task_queue` package stays **DB-free**; that the writer imports no
LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential; that the
`006_agent_task_queue_records` migration is additive schema-only (creates one table, no INSERT/seed,
upgrade+downgrade, adds the unique index, `down_revision = 005_source_ingestion_idem`); that the docs
carry the required language; and that the repo stays source-only. The **DB-backed** layer (when
SQLAlchemy is importable) builds a **temporary local SQLite database** (deleted afterward) and
exercises real behavior — migration upgrade/downgrade/re-upgrade; successful create (one row,
server-stamped `atq_` id/timestamp, **safe references only** — evidence ids as a list, no raw
content, review-gated `output_status=draft` / `review_status=needs_review` /
`lifecycle_status=draft` / `execution_status=not_executed` with all execution flags false and
`requires_human_review=true`); side-effect discipline (**no `agent_run_records` row**, no unrelated
writes); idempotent replay; conflicting replay (denied, row unchanged); DB-backed authorization
(request scope vs stored `Engagement.authorization_scope`; missing stored/request scope; missing
subject; owner/client/engagement mismatch); draft/request identity + **Phase 13 registry** gate
(unknown agent rejected); table/action allowlist (wrong table/action + delete-/update-/publish-/
execute-/client-facing-/financial-/raw_sql-like actions, and an `agent_run_records` target
rejected); posture rejections (bad output/review/lifecycle/execution status, authoritative,
client-facing, capsule-ready, execution/LLM/AgentNet/resolver/network allowed,
`requires_human_review=false`, caller-supplied id/timestamp, missing/blocked readiness_state);
content/secret guard (injected `packet_payload` / `raw_packet_content` / `raw_evidence_text` /
`raw_interview_text` / `source_bytes` / `api_key` / `connection_string` / `token` attributes
rejected without echoing values); and transaction/failure semantics (`failed_before_write`,
`write_outcome_uncertain`, and the `IntegrityError` race → replay/conflict). Skips the DB layer
with instructions if SQLAlchemy is absent (still exits 0). Run the full suite with
`make validate-phase27 PYTHON=.venv/bin/python`. See
[`../docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](../docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md)
and [`../docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md`](../docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md).

## `validate_phase28_packet_task_queue_integration.py`

Check for the Phase 28 **packet → task queue orchestration integration** (`peak/orchestration/`)
— wiring the Phase 26 readiness planner and Phase 27 writer into the Phase 25 packet processor.
Three layers. The **structural** layer confirms the orchestration files + integration doc exist
and compile; that the Phase 23 ingestion and Phase 26 `task_queue` packages stay **DB-free**; that
the orchestrator imports no live LLM / MockLLM / executor / AgentNet / MCP / resolver / connector /
network module and **no top-level** SQLAlchemy / `peak.db` (the Phase 27 writer is lazy-imported);
that the Phase 27 commit is present; that **no Phase 28 migration** was added (head stays
`006_agent_task_queue_records`); and that the docs carry the required language. The **plan-only**
layer (stdlib-only) confirms default packet processing derives Phase 13 tasks, runs the Phase 26
readiness planner, exposes review-gated / not-executed queue drafts + assessments + plan-only
Phase 17 write requests with correct counts, keeps **every side-effect flag false**, executes
nothing, writes no `agent_run_records`, leaks no raw payload sentinel, blocks evidence-dependent
tasks in-band without failing the packet, and **never silently escalates** persistence
(`skipped_not_requested` / `skipped_plan_only` / `skipped_missing_session_factory`). The
**DB-backed** layer (when SQLAlchemy is importable) builds a **temporary local SQLite database**
(deleted afterward) and exercises controlled persistence **through the Phase 27 writer only** —
create (rows == valid drafts, receipts attached, DB flags true, execution flags false, **no
`agent_run_records`**), idempotent replay, conflict (same key, different fingerprint → denied →
orchestration `partial`), stored-`Engagement` scope mismatch denied by the writer and surfaced,
and a regression check that source-ingestion (Phase 24) and evidence (Phase 18/21) persistence
still work. Skips the DB layer with instructions if SQLAlchemy is absent (still exits 0). Run the
full suite with `make validate-phase28 PYTHON=.venv/bin/python`. See
[`../docs/PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](../docs/PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md).

## `validate_phase29_review_orchestration_boundary.py`

Check for the Phase 29 **Packet-Derived Review Orchestration Boundary** (`peak/review_orchestration/`)
— a DB-free review-planning boundary over packet-derived outputs, analogous to Phase 26.
Stdlib-only; **no database** (Phase 29 writes nothing, approves nothing, and connects to nothing).
The **structural** layer confirms the package files exist, compile, and import; that the package
imports no SQLAlchemy / Alembic / `peak.db` / live-or-mock LLM / AgentNet / MCP / resolver /
connector / network module; that the Phase 23 ingestion and Phase 26 `task_queue` packages stay
DB-free; that the Phase 28 commit is present; that **no Phase 29 migration** was added (head stays
`006_agent_task_queue_records`) and **no new DB table** was declared; and that the docs carry the
required language. The **functional** layer runs `prepare_packet_review_plan` and asserts: a valid
request produces review bundle drafts, review plan items (source / evidence / agent-task-queue /
packet-processing / cross-stage / missing-evidence), and a `ready_for_human_review` assessment —
review-gated and **not approved** (`approval_allowed=false`, `requires_human_review=true`, no
id/created_at); **every side-effect flag false**; strict/no-subject → denied and non-strict/
no-subject → `blocked_no_subjects` (no stored-record claim); identity / scope / lifecycle denials;
approval / execution / client-facing / publication / financial-verification intent denials (with
the mapped `blocked_*` readiness state); and content safety — raw packet payload, raw evidence /
interview text, source bytes, generated output, arbitrary JSON refs, multiline raw text, and
secret-like keys rejected **without echoing values**. The **integration** layer confirms Phase 29
consumes safe references shaped like Phase 25/28 packet-processing output and synthetic Phase
27-style ids with no DB access, and that the package imports neither the Phase 27 writer nor the
Phase 22 writer (no `review_records` write). See
[`../docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](../docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md)
and [`../docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md`](../docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md).

## `validate_phase30_review_bundle_writer.py`

Check for the Phase 30 **controlled DB review-bundle writer** (`peak/db/review_bundle_writer.py`,
`peak/db/writer_contracts.py`) — the same two-layer pattern as Phases 20–24 and 27, applied to
`review_bundle_records` (the persistence counterpart to Phase 29). The **structural** layer confirms
the files exist and compile; that the Phase 29 `peak/review_orchestration` package stays **DB-free**;
that the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client, no
Phase 22 review writer, and no credential; that the `007_review_bundle_records` migration is
additive schema-only (creates one table, no INSERT/seed, upgrade+downgrade, adds the unique index,
`down_revision = 006_agent_task_queue_records`); that the docs carry the required language; and that
the repo stays source-only. The **DB-backed** layer (when SQLAlchemy is importable) builds a
**temporary local SQLite database** (deleted afterward) and exercises real behavior — migration
upgrade/downgrade/re-upgrade; successful create (one row, server-stamped `rvb_` id/timestamp, **safe
references only** — source/evidence/task ids + subject id+type in `details_json`, no raw content,
review-gated `output_status=draft` / `review_status=needs_review` / `lifecycle_status=draft` with all
approval/execution/publication/financial flags false and `requires_human_review=true`); side-effect
discipline (**no `review_records` row, no `agent_run_records` row**, no unrelated writes); idempotent
replay; conflicting replay (denied, row unchanged); DB-backed authorization (request scope vs stored
`Engagement.authorization_scope`; missing stored/request scope; missing subject;
owner/client/engagement mismatch); draft/request identity mismatches; table/action allowlist (wrong
table/action + approve-/update-/delete-/publish-/execute-/client-facing-/financial-/raw_sql-like
actions, and `review_records` / `agent_run_records` targets rejected); posture rejections (each
posture flag, caller-supplied id/timestamp); content/decision/secret guard (injected `packet_payload`
/ `raw_evidence_text` / `raw_interview_text` / `source_bytes` / `generated_output` /
`approval_decision` / `api_key` / `connection_string` / `token` / `credential` attributes rejected
without echoing values); and transaction/failure semantics (`failed_before_write`,
`write_outcome_uncertain`, and the `IntegrityError` race → replay/conflict). Skips the DB layer with
instructions if SQLAlchemy is absent (still exits 0). Run the full suite with
`make validate-phase30 PYTHON=.venv/bin/python`. See
[`../docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md`](../docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md) and
[`../docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md`](../docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md).

## `validate_phase31_packet_review_bundle_integration.py`

Check for the Phase 31 **packet → review bundle orchestration integration** (`peak/orchestration/`)
— wiring the Phase 29 review planner and Phase 30 writer into the Phase 25/28 packet processor.
Three layers. The **structural** layer confirms the orchestration files + integration doc exist and
compile; that the Phase 23 ingestion, Phase 26 task_queue, and Phase 29 review_orchestration
packages stay **DB-free**; that the orchestrator imports no live LLM / MockLLM / executor / AgentNet
/ MCP / resolver / network module, **no top-level** SQLAlchemy / `peak.db` (the Phase 30 writer is
lazy-imported), and **no Phase 22 review writer**; that the Phase 30 commit is present; that **no
Phase 31 migration** was added (head stays `007_review_bundle_records`); and that the docs carry the
required language. The **plan-only** layer (stdlib-only) confirms default packet processing runs the
Phase 29 review planner, exposes review-gated / not-approved review bundle drafts + plan items +
readiness assessments with correct counts, keeps **every side-effect flag false**, approves nothing,
executes nothing, writes no `review_records`/`agent_run_records`, leaks no raw payload sentinel, and
**never silently escalates** persistence (`skipped_not_requested` / `skipped_plan_only` /
`skipped_missing_session_factory`). The **DB-backed** layer (when SQLAlchemy is importable) builds a
**temporary local SQLite database** (deleted afterward) and exercises controlled persistence
**through the Phase 30 writer only** — create (rows == drafts, receipts attached, DB flags true,
approval/execution flags false, **no `review_records`**, **no `agent_run_records`**), idempotent
replay, conflict (same review key, different fingerprint → denied → orchestration `partial`),
stored-`Engagement` scope mismatch denied by the writer and surfaced, and a regression check that
source (Phase 24), evidence (Phase 18/21), and task-queue (Phase 27) persistence still work. Skips
the DB layer with instructions if SQLAlchemy is absent (still exits 0). Run the full suite with
`make validate-phase31 PYTHON=.venv/bin/python`. See
[`../docs/PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md`](../docs/PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md).

## `validate_phase32_internal_reviewer_decision_boundary.py`

Check for the Phase 32 **Internal Reviewer Decision Boundary** (`peak/reviewer_decisions/`) — a
DB-free decision-planning boundary over review-bundle references and safe reviewer selections,
analogous to Phase 29. Stdlib-only; **no database** (Phase 32 writes nothing, approves nothing, and
connects to nothing). The **structural** layer confirms the package files exist, compile, and
import; that the package imports no SQLAlchemy / Alembic / `peak.db` / Phase 22 review writer /
live-or-mock LLM / AgentNet / MCP / resolver / connector / network module; that the Phase 23
ingestion, Phase 26 task_queue, and Phase 29 review_orchestration packages stay DB-free; that the
Phase 31 commit is present; that the Phase 30 migration `007_review_bundle_records` is present and
the **Phase 32 package declares no SQLAlchemy model/table** (persistence is owned by the separate
Phase 33 writer); and that the docs carry the required language. The **functional** layer runs `prepare_internal_reviewer_decision` and asserts: a
valid request produces one decision draft + routing plan + `ready_to_record` readiness assessment —
review-gated and **not approved** (`approval_allowed=false`, `review_approval_made=false`, no
id/created_at); **every side-effect flag false** and `controlled_write_request_count=0`;
deterministic routing per allowed intent (incl. `return_for_revision` → `<stage>_revision`);
`ready_for_internal_use` is accepted but approves nothing; identity / scope / lifecycle /
missing-field / missing-bundle denials; disallowed intents (`approve_internal`, `publish_capsule`,
`verify_financial_impact`, `execute_agent`, `send_to_client`, …) → `blocked_disallowed_intent` and
unsupported → `blocked_unsupported_intent`; and content safety — raw packet payload, raw
evidence/interview text, source bytes, generated output, arbitrary JSON refs, multiline summaries,
DB-URL/raw-SQL keys, and secret-like keys rejected **without echoing values**. The **integration**
layer confirms Phase 32 consumes safe references shaped like Phase 30 output (`review_bundle_record_id`)
and Phase 29 output (review plan item refs) with no DB access, and imports neither the Phase 30
writer nor the Phase 22 writer nor `peak.db`. See
[`../docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](../docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md) and
[`../docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md`](../docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md).

## `validate_phase33_internal_reviewer_decision_writer.py`

Check for the Phase 33 **Internal Reviewer Decision Controlled Writer**
(`peak/db/internal_reviewer_decision_writer.py`) — the seventh narrow live DB writer and the
persistence counterpart to Phase 32. The **structural** layer (always, stdlib-only) confirms the
writer/receipt/migration/doc files exist and compile; that the Phase 32 `peak/reviewer_decisions`
package stays DB-free; that the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/
connector/network client, credential, or Phase 22 review writer; that migration
`008_internal_reviewer_decision_records` is additive schema-only (one table, no INSERT/seed,
`down_revision = 007_review_bundle_records`); that the Phase 17 allowlist gained exactly the one
new table/action (no broadening); and that the docs carry the required language (incl. **14
tables**). The **DB-backed** layer (when SQLAlchemy is importable) exercises real behavior against a
temporary SQLite database: migration upgrade/downgrade/re-upgrade; a successful create storing safe
references only in the review-gated **non-approval** posture (`ready_for_internal_use` stored but
not approval); the DB-layer CWR planner helper; idempotent replay and conflicting replay; DB-backed
stored-`Engagement` authorization (stored-scope comparison, identity necessary but not sufficient,
prohibited stored lifecycle); pre-DB draft/request identity and scope mismatches; table/action
allowlist denials (incl. `review_records`/`agent_run_records` targets and approve/publish/execute/
client-facing/financial/raw-SQL actions); decision-intent denials (`approve_internal`,
`publish_capsule`, `verify_financial_impact`, `execute_agent`, `send_to_client`, …) with every
allowed intent persisting; posture/caller-field rejections; content-attribute and summary/followup
value-safety rejections **without echoing values**; side-effect discipline (no
`review_records`/`agent_run_records` write); and transaction/failure semantics
(`failed_before_write`, `write_outcome_uncertain`, `IntegrityError` race). Run
`make validate-phase33 PYTHON=.venv/bin/python` for the DB layer. See
[`../docs/INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](../docs/INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md) and
[`../docs/INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md`](../docs/INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md).

## `validate_phase34_intake_note_writer.py`

Check for the Phase 34 **Intake Note Controlled Writer** (`peak/db/intake_note_writer.py`) — the
eighth narrow live DB writer and the first to store authorized operational `note_text`. The
**structural** layer (always, stdlib-only) confirms the writer/receipt/migration/doc files exist and
compile; the writer imports no LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client,
credential, or Phase 22 review writer; the Phase 32 package stays DB-free and Phase 33 still uses the
public classifier; migration `009_intake_note_records` is additive schema-only (`down_revision =
008`); the Phase 17 allowlist gained exactly the one new table/action; and the docs carry the
required language. The **DB-backed** layer (temporary SQLite — a fast structural smoke path, **not**
production proof) exercises: successful create with `note_text` persisted but **never echoed** in the
receipt; idempotent replay and conflict (an edited note under the same key conflicts); stored-
`Engagement` authorization; identity/allowlist/posture rejections; `note_text` content-safety
(ordinary prose passes; credential/DSN/SQL/private-key/stack-trace/JSON markers denied without
echoing; over-length denied) plus label/summary safety; side-effect discipline; and
transaction/failure/race semantics. Run `make validate-phase34 PYTHON=.venv/bin/python` for the DB
layer. See [`../docs/INTAKE_NOTE_CONTROLLED_WRITER.md`](../docs/INTAKE_NOTE_CONTROLLED_WRITER.md) and
[`../docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md`](../docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md).

## `validate_phase34_managed_mysql_rubric.py`

Check for the Phase 34 **managed MySQL persistence rubric** and **Peak-operated AgentNet publication
policy** (stdlib-only, credential-free, no live network). It verifies the rubric/isolation/parity
docs state that managed remote MySQL is the operational store, Client Isolation Option A is the
default, **SQLite is not the production-readiness proof path**, managed MySQL test/staging is required
for production readiness, the production DB is not the main smoke-test target, and there is no broad
production delete/cleanup path; that the `PEAK_MANAGED_MYSQL_{TEST,STAGING,PROD}_DSN` env-var names
are documented **without values**; that the AgentNet policy makes Peak the authorized publisher,
forbids client-facing publisher UI / client-held credentials / client-operated resolver tools /
direct client publication, and keeps publication disabled; that the opt-in
`db-check-managed-test` / `managed-mysql-smoke` / `managed-mysql-migration-check` targets skip
cleanly with no DSN, refuse `prod`, and never print a DSN (verified by running
`tools/managed_mysql_check.py`); and that no credentials / `.env` / AgentNet publish code were
committed. See [`../docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](../docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md),
[`../docs/CLIENT_ISOLATION_MODEL.md`](../docs/CLIENT_ISOLATION_MODEL.md),
[`../docs/PRODUCTION_PARITY_DB_VALIDATION.md`](../docs/PRODUCTION_PARITY_DB_VALIDATION.md), and
[`../docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](../docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

## `validate_phase35_managed_record_workflow.py`

Check for the Phase 35 **governed managed-record workflow integration layer**
(`peak/workflows/`) — the DB-free sequencing layer that drives six existing durable record types
through their existing narrow controlled writers under explicit per-stage persistence gates.

Structural: the package/contracts/docs exist and compile; the package imports no
SQLAlchemy/Alembic/DB-model/migration at module scope (proved at runtime in a subprocess), no
LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential, no Phase 22 review
writer, no agent-run writer, no raw SQL, and no publication code; the Phase 17 allowlist gained **no**
new table/action pair; **no migration `010`** was added and `db-check` still expects **15 tables**;
the eight existing writers remain and Phases 32/33/34 are intact; the docs carry the required
language; the managed-MySQL and AgentNet publication policies are unchanged; the repo stays
source-only.

Plan-only / DB-free: gate behavior (planned / skipped / denied), stage idempotency-key derivation and
`wf35::<stage>::` prefixing, identity and `authorization_scope` pre-flight denial, prohibited
key/value denial with **canary values that must never be echoed**, strict-mode halting vs non-strict
warning collection, and `note_text` never appearing in a result.

DB-backed (SQLAlchemy present, temporary local SQLite): a fully gated six-stage workflow persisting
through the six narrow writers, per-stage gating, sanitized receipts and record refs,
`table_write_counts`, idempotent replay with no duplicate rows, writer-denial and
idempotency-conflict halting, stored-scope authorization still enforced by the writers, and
side-effect discipline (**no `review_records` / `agent_run_records` row**). SQLite here is only a
fast local structural smoke path — **not** the production-readiness proof path. Run
`make validate-phase35 PYTHON=.venv/bin/python` for the DB layer. See
[`../docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md`](../docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md)
and
[`../docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md`](../docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md).

## `validate_phase36_internal_assessment_report_planning.py`

Check for the Phase 36 **Internal Assessment Report Assembly Planning Boundary**
(`peak/reports/`) — the DB-free planner that turns governed record references and reviewer decisions
into an internal report *assembly plan*. Stdlib-only: no database, no credentials, no network.

Structural: the package/contracts/docs exist and compile; `peak/reports` imports no
SQLAlchemy/Alembic/`peak.db`/DB-writer/AgentNet/MCP/resolver/connector/network/LLM/MockLLM/agent-
executor/publication module and no random-id or timestamp source (import cleanliness is proved at
runtime in a subprocess); the public entry point and every typed contract exist; the Phase 17
allowlist gained **no** new pair; no migration `010`; `db-check` still expects **15 tables**; no
report table or report writer was added; Phases 32/33/34/35 are intact.

Behavioral: a valid request yields a deterministic plan with internal-only posture, all fourteen
sections in canonical order, reference-only evidence traces, positional finding/recommendation slots,
and gaps for every unsatisfied category; the fingerprint is stable across reference reordering and
duplication but changes with the reference set or section selection; `future_financial_verification_items`
and `future_capsule_candidate_items` exist while `financial_verified` / `capsule_candidate_ready` /
`publication_allowed` stay false.

Denials: missing identity/scope/plan-id, revoked scope, blocked lifecycle, unsupported or duplicate
sections, unsupported audience (`client`/`external`), every elevated posture flag, cross-tenant /
cross-engagement / cross-owner / scope-mismatched structured references, and unsafe
(multiline/overlong/whitespace/quoted/non-string) references.

Leak safety: ~28 prohibited keys and DSN/raw-SQL/raw-content/credential/stack-trace values are denied
before a plan is assembled, and a **canary value never reaches any reason, warning, or result**. See
[`../docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`](../docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md)
and
[`../docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md`](../docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md).

## `validate_phase37_internal_assessment_report_draft_writer.py`

Check for the Phase 37 **Internal Assessment Report Draft Controlled Writer**
(`peak/db/internal_assessment_report_draft_writer.py`) — the ninth narrow live DB writer and the
persistence counterpart to Phase 36.

Structural (always): the writer/receipt/model/migration/docs exist and compile; the writer imports no
LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential and no Phase 22
review writer or agent-run writer; it executes no raw SQL and has no update/delete path; the Phase 36
`peak/reports` package **stays DB-free** (verified at runtime in a subprocess); the Phase 17 allowlist
gained exactly one pair (11 tables / 13 actions); migration `010` is additive schema-only with
`down_revision = 009_intake_note_records`, creates one table, has no INSERT/seed, and its downgrade
drops only that table; the chain stays linear; `db-check` now expects **16 tables**.

DB-backed (temporary local SQLite): migration upgrade/downgrade/re-upgrade; successful create with
structure and references stored and **no prose, no raw-content key, and no ROI/currency figure**;
the CWR helper bridge; idempotent replay and conflict; stored-`Engagement` authorization denials
(missing subject, missing/mismatched stored scope, owner/client mismatch, blocked lifecycle);
identity and posture denials (caller-supplied id/timestamp, non-internal audience, every elevated
flag, non-`plan` output status, approved review status, non-draft lifecycle, client-facing nested
candidate); allowlist denials (wrong table/action, update/delete/upsert/raw-SQL/publish/approve/send/
verify actions); content-safety denials with a **canary that never reaches a receipt or a row**; and
transaction/failure semantics. SQLite here is a structural smoke path only — **not** production
proof. Run `make validate-phase37 PYTHON=.venv/bin/python` for the DB layer. See
[`../docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](../docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md)
and
[`../docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md`](../docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md).

## `validate_phase38_internal_report_review_packet_writer.py`

Check for the Phase 38 **Internal Report Review Packet Controlled Writer**
(`peak/db/internal_report_review_packet_writer.py`) — the tenth narrow live DB writer.

Structural (always): writer/contracts/model/migration/docs exist and compile; the writer imports no
LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential and no Phase 22
review writer or agent-run writer; it executes no raw SQL, has no update/delete path, and reads only
the two authorized stored models (`Engagement`, `InternalAssessmentReportDraftRecord`); Phase 36
`peak/reports` stays DB-free and the Phase 37 writer is unchanged in substance; the Phase 17
allowlist gained exactly one pair (12 tables / 14 actions); migration `011` is additive schema-only
with `down_revision = 010_…`; the chain stays linear; `db-check` now expects **17 tables**; and
**every index/constraint name fits MySQL's 64-character identifier limit**.

DB-backed (temporary local SQLite): migration upgrade/downgrade/re-upgrade; successful create with
labels/statuses/refs stored and **no prose, no raw-content key, and no ROI/currency figure**; stored
report-draft linkage validation (missing row, tenant/scope mismatch, every posture elevation, and
provenance mismatches); idempotent replay and conflict; stored-`Engagement` authorization denials;
identity and posture denials (caller-supplied id/timestamp, non-internal audience, elevated
packet/review/lifecycle/decision status, supplied decision link, every elevated flag,
approval-flavoured checklist status, unexpected checklist key); allowlist denials; **structural
bounds for all six list families with runtime-generated items and an at-limit control**;
content-safety denials with a **canary that never reaches a receipt or a row**, including
client-facing/approval **intent** in reviewer questions; and transaction/failure semantics. SQLite
here is a structural smoke path only — **not** production proof. Run
`make validate-phase38 PYTHON=.venv/bin/python` for the DB layer. See
[`../docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](../docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md)
and
[`../docs/INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md`](../docs/INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md).

## `validate_phase39_internal_report_review_packet_decision_writer.py`

Check for the Phase 39 **Internal Report Review Packet Decision Controlled Writer**
(`peak/db/internal_report_review_packet_decision_writer.py`) — the eleventh narrow live DB writer.

Structural (always): writer/contracts/model/migration/docs exist and compile; the writer imports no
LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client or credential and no Phase 22
review writer or agent-run writer; it executes no raw SQL, has no update/delete path, **reads only
the three authorized stored models** and calls `session.add` exactly once; it reuses the closed
Phase 32 decision vocabulary; Phase 36 `peak/reports` stays DB-free and the Phase 33/37/38 writers
are unchanged; the allowlist gained exactly one pair (13 tables / 15 actions); migration `012` is
additive schema-only with `down_revision = 011_…`; the chain stays linear; `db-check` now expects
**18 tables**; and every identifier fits MySQL's 64-character limit.

DB-backed (temporary local SQLite, over a real Phase 37 → 38 → 39 chain): migration reversibility;
successful create with the audit chain preserved and upstream fingerprints copied from the stored
rows; **byte-for-byte proof that the packet and report-draft rows are not modified**; every intent in
the closed vocabulary accepted with its server-derived `decision_status`, and eleven approval-like
intents denied; idempotent replay and conflict (including a conflict when only the intent changes);
seven stored-`Engagement` denials; **twenty** stored-packet denials and **twelve** stored-report-draft
denials; request/draft denials; allowlist denials; structural bounds with runtime-generated items;
content-safety denials with a **canary that never reaches a receipt or a row**, including
client-facing/approval **intent** in the summary; and transaction/failure semantics. SQLite here is a
structural smoke path only — **not** production proof. Run
`make validate-phase39 PYTHON=.venv/bin/python` for the DB layer. See
[`../docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](../docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md)
and
[`../docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md`](../docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md).

---

## `validate_phase40_internal_report_review_workflow.py`

Check for the Phase 40 **end-to-end internal report review workflow integration layer**
([`../peak/workflows/internal_report_review_workflow.py`](../peak/workflows/internal_report_review_workflow.py)) —
a **read-only** consolidation over the Phase 37 report draft, Phase 38 review packet, and Phase 39
packet decision rows.

Structural (always, stdlib-only): the module/doc/harness exist and compile; the module imports no
LLM/MockLLM/executor/AgentNet/MCP/resolver/connector/network client, no credential, and **no writer
function**; it has no `session.add`/`delete`/`merge`/`flush`/`commit`, no `update()`/`delete` path,
and no raw SQL (boundary claims are checked against tokenized code, so a docstring naming the
forbidden thing cannot pass or fail the check by accident); `import peak.workflows` still loads no
DB driver and a DB-free denial needs none; the public entry point and the typed
request/result/trace contracts exist; the baseline is unchanged (Alembic head `012`, 18 tables, 13
allowlist tables / 15 actions, no migration `013`, no new table/model/writer/allowlist pair, and no
pending diff on the Phase 37/38/39 writers, `peak/db/models.py`, or `alembic/versions`, and the
*generic* allowlist unchanged with `engagements`/`clients` still prohibited on it — the allowlist
*file* stopped being frozen at Phase 54, which legitimately added the one-pair engagement
anchor-creation gate beside those generic sets); Phase 36 `peak/reports` stays DB-free; the closed computed vocabularies cover
the whole Phase 32 decision vocabulary and stay in lockstep with Phase 39's server-side
`decision_status` derivation; the docs carry the required language; the repo stays source-only.

DB-backed (temporary local SQLite, over a genuine Phase 37 → 38 → 39 chain): a successful read-only
summary; **proof that no row is inserted, updated, or deleted and that the packet and report-draft
rows are byte-for-byte unchanged**; the full `decision_intent` → computed-state mapping across the
whole closed vocabulary; the awaiting-decision path; the conflicting-decisions path with no
automatic resolution; idempotent duplicates collapsing to one state; inconsistent / non-internal /
out-of-scope decision rows excluded with non-echoing warnings and `strict_mode` escalation; **eight**
stored-`Engagement` blockers, **eighteen** stored-report-draft blockers, and **twenty-two**
stored-review-packet blockers (including the packet-decision-column reconciliation that is never
repaired by writing); non-echoing content safety with a **canary that never reaches a result**;
determinism; and read-failure semantics. SQLite here is a structural smoke path only — **not**
production proof. Run `make validate-phase40 PYTHON=.venv/bin/python` for the DB layer. See
[`../docs/INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md`](../docs/INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md).

---

## `validate_phase41_managed_mysql_production_parity.py`

Check for the Phase 41 **managed MySQL production-parity validation layer**
([`../tools/managed_mysql_parity_check.py`](../tools/managed_mysql_parity_check.py)). Stdlib-only,
offline, credential-free — it needs no managed database and makes no network call.

Verifies the parity tool is validation-only (no writer, no CRUD, no SQL execution, no database
connection, no DB driver at module scope, no LLM/agent/AgentNet/network path, no `.env` read, no
committed DSN or credential); that static mode runs offline and exits 0 even with a DSN exported;
that the identifier limit is genuinely **enforced** — a throwaway copy of the migrations is
injected with the real 69-character Phase 38 index name and the checker must **fail** with exit 1,
so a green run means something; that the collation gap is surfaced as a warning naming its
idempotency consequence and proposing no migration; that a tier which cannot run declares itself
skipped rather than reporting a pass it did not earn.

Also verifies the staging gate is skip-safe and fail-closed (exit 0 with no configuration, importing
no DB driver and reading no `.env`; **REFUSED** with exit 2 for `--env prod` and for a DSN that is
not marked disposable; **HOLD** rather than an automatic live run when fully configured), that a
**canary DSN and secret are never echoed in any mode**, that `make validate` stays offline while
every DB-capable target stays out of it, and the standing baseline regressions (head `012`, 12
migrations, no `013`, 18 tables, 13 allowlist tables / 15 actions, 11 writers, no new
table/model/migration/writer/allowlist pair, and the managed-MySQL / Client Isolation Option A /
AgentNet publication policies intact).

Run `make validate-phase41`. No `PYTHON=.venv/bin/python` variant is required — the harness is
offline in both interpreters, though the venv adds the tool's model-introspection and
migration-simulation tiers. See
[`../docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md`](../docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md).

---

## `validate_phase42_governed_mysql_collation_policy.py`

Check for the Phase 42 **governed MySQL collation policy and offline audit**
([`../tools/governed_mysql_collation_audit.py`](../tools/governed_mysql_collation_audit.py)).
Stdlib-only, offline, credential-free.

Verifies the audit is analysis-only (no writer, no CRUD, no SQL, no database connection, no DB
driver at module scope, no `.env` read, no committed DSN, and no `op.*`/`ALTER TABLE` that would
constitute a schema proposal); that it runs on both interpreter tiers and **declares which tier
ran** — with the source-scan fallback forced deterministically via a `None` entry in `sys.modules`
so the non-authoritative tier is genuinely exercised and asserts it draws no policy conclusion.

Verifies the audit classifies every string column, places each required governed column
(`id`, `owner_id`, `client_id`, `engagement_id`, `authorization_scope`, `idempotency_key`, and the
four fingerprints) in its expected class, separates `ordinary_text` and `json_or_details_text`,
ranks enum/status as deterministic-**preferred** rather than required, reports CRITICAL/HIGH/MEDIUM
risk tiers, names the `UNIQUE (owner_id, client_id, engagement_id, idempotency_key)` boundary with
its concrete `idem-key-1` / `idem-KEY-1` consequence, and keeps `packet_hash` correctly outside the
column set. Output is asserted **byte-identical across runs** (deterministic) and free of any
canary DSN even when one is exported.

The audit is a real control: a negative test renames a required governed column in a throwaway copy
of the models and asserts the audit **fails with exit 1** — while the ordinary unpinned-collation
finding exits **0** as `NEEDS_REMEDIATION`, because a known documented finding is not a build
failure.

Also verifies the policy doc states its rules and constraints (server-default collation
insufficient for governed boundaries; future governed columns must state collation explicitly;
remediation needs approval; production is not a smoke-test target; no client or seed data; downgrade
posture; index byte math; additive ALTER-only), that **no migration `013` exists**, that nothing
changed under `alembic/`, `schemas/`, or `peak/`, that the Phase 41 checker still passes with a
*more precise* (not weakened) warning that now references this audit, and the standing baseline and
policy regressions.

Run `make validate-phase42`. Offline in both interpreters; the venv adds the model-introspection
tier. See
[`../docs/GOVERNED_MYSQL_COLLATION_POLICY.md`](../docs/GOVERNED_MYSQL_COLLATION_POLICY.md).

---

## `validate_phase43_production_mysql_collation_verification.py`

Check for the Phase 43 **read-only production collation verification tool**
([`../tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py)).
Stdlib-only and offline: it needs no production credentials and connects to nothing.

Proves the tool is structurally incapable of mutating production — no mutating SQL anywhere in the
source, no writer, no migration runner or `op.*` call, no ORM session or `create_all`, no DB driver
at module scope, no `.env` read, and no code path accepting SQL from argv, environment, or file.
The read-only guard is then **exercised directly** against 19 hostile statements (DDL, DML,
multi-statement, `OUTFILE`, `LOAD DATA`, `CALL`, `SET`, `GRANT`/`REVOKE`, a read-only statement
that is simply not on the allowlist, and one that would return governed row values) — all must be
refused — while every allowlisted query must be accepted, must be `SELECT`/`SHOW`, and must not
return a governed column in its **select list** (a `GROUP BY` key is fine; a returned value is not).
Identifier injection is refused, and the sanitizer and `safe_error()` are checked against a canary.

Verifies fail-closed gating: unconfigured skips (exit 0) importing no driver and reading no `.env`;
a connection setting without `PEAK_PRODUCTION_DB_READONLY_CONFIRM` **refuses** (exit 2) with
`production_connection_attempted=False`; affirmation without a connection setting skips. A canary
DSN, username, host, and secret are never echoed in any mode.

A **fake cursor drives the complete query path with no database**, proving the tool classifies a
case-insensitive production as `verified_risk_live_remediation_required` and a deterministic one as
`verified_safe_no_remediation_required`, counts exactly **11** idempotency boundaries (not all 18
tables), issues only read-only `INFORMATION_SCHEMA` statements, reports the server version as a
family only, keeps the collision probe **opt-in and off by default**, returns integer counts only,
and emits no production row value.

Also verifies the docs state the production posture, the required env vars **by name only**, the
go/no-go rule, and backup/tested-restore/maintenance-window requirements; that the Phase 42
duplicate-key direction claim was corrected; that **no migration `013` exists**; that nothing
changed under `alembic/`, `schemas/`, or `peak/`; that the production target stays out of
`make validate`; and the standing baseline and policy regressions.

Run `make validate-phase43`. Offline in both interpreters; the venv adds the query-path simulation.
See
[`../docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](../docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md).

---

## `validate_phase44_governed_identifier_collation_migration.py`

Check for the Phase 44 **governed identifier collation migration** — migration
`013_governed_identifier_collation_policy` plus the model metadata that pins `utf8mb4_bin` on the
211 governed columns. Offline and credential-free.

Verifies the baseline moved correctly (head 012 → 013, 13 migrations, still 18 tables, no new
table/model entity or allowlist pair, 11 writers, only `peak/db/models.py` and `peak/db/base.py`
changed under `peak/`, no earlier migration edited); that migration `013` is **ALTER-only** (no
`create_table`/`drop_table`/`add_column`/`drop_column`/`create_index`/`drop_index`/`bulk_insert`/
`execute`, no INSERT/UPDATE/DELETE/TRUNCATE/GRANT/REVOKE, no raw `text()`, no seed or client data,
no index or constraint name anywhere) and correctly dialect-gated so SQLite is a deliberate no-op.

The mapping is extracted with `ast` rather than by importing the migration — which both works
without Alembic installed and *proves the literal is static*, since a runtime-built list would fail
`literal_eval`. It is then compared **both directions** against the live models: every governed
model column appears in the migration, every mapped column exists in the model with matching length
and nullability, and no `ordinary_text`, `json_or_details_text`, or `governed_enum_status` column
was swept in.

Model policy is checked on effective types: exactly 211 governed columns resolve to `utf8mb4_bin`,
zero remain unpinned, zero non-governed columns were forced into a binary collation, all 11
idempotency-boundary tables and every hash/fingerprint and scope column are deterministic, MySQL DDL
carries `COLLATE utf8mb4_bin` while SQLite DDL carries none, and `create_all` still builds all 18
tables on SQLite. The migration is then applied, reversed, and re-applied on a temporary SQLite
database.

Finally it confirms the audit reports `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED` (not
`NEEDS_REMEDIATION`) while still saying production is unverified and migration 013 must still run
there, that the parity checker and production verifier still pass and skip safely, and the standing
forbidden-path and policy guarantees.

Run `make validate-phase44`. Offline in both interpreters; the venv adds the model-comparison and
migration-run tiers. See
[`../docs/GOVERNED_MYSQL_COLLATION_POLICY.md`](../docs/GOVERNED_MYSQL_COLLATION_POLICY.md).

## Running

This machine uses `python3` (there is no bare `python`). From the repo root:

```bash
# one-time: install the dev dependency
make install-dev          # == python3 -m pip install -r requirements-dev.txt

# run all harnesses
make validate             # == phase1 … phase44

# or run one at a time
make validate-phase1
make validate-phase2
make validate-phase3
make validate-phase4
make validate-phase5
make validate-phase6
make validate-phase7
make validate-phase8
make validate-phase9
make validate-phase10
make validate-phase11   # == make db-check
make validate-phase12
make validate-phase13
make validate-phase14
make validate-phase15
make validate-phase16
make validate-phase17
make validate-phase18
make validate-phase19
make validate-phase20   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase21   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase22   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase23   # stdlib-only; no database
make validate-phase24   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase25   # structural+plan-only always; add PYTHON=.venv/bin/python for the DB layer
make validate-phase26   # stdlib-only; DB-free (no database layer)
make validate-phase27   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase28   # structural+plan-only always; add PYTHON=.venv/bin/python for the DB layer
make validate-phase29   # stdlib-only; DB-free (no database layer)
make validate-phase30   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase31   # structural+plan-only always; add PYTHON=.venv/bin/python for the DB layer
make validate-phase32   # stdlib-only; DB-free (no database layer)
make validate-phase33   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase34   # DB-backed intake-note writer + managed-MySQL rubric; add PYTHON=.venv/bin/python
make validate-phase35   # structural+plan-only always; add PYTHON=.venv/bin/python for the DB layer
make validate-phase36   # stdlib-only; DB-free and network-free
make validate-phase37   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase38   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase39   # DB-backed; add PYTHON=.venv/bin/python for the full suite
make validate-phase40   # structural always; add PYTHON=.venv/bin/python for the DB layer
make validate-phase41   # offline; no credentials, no network (venv adds the simulation tiers)
make validate-phase42   # offline; no credentials, no network (venv adds the model tier)
make validate-phase43   # offline; no credentials, no network (venv adds the query simulation)
make validate-phase44   # offline; no credentials, no network (venv adds model + migration tiers)
# opt-in managed MySQL (credential-free; skip safely with no DSN; never part of `make validate`):
make db-check-managed-test          # managed test-env rubric check
make managed-mysql-smoke            # managed test-env smoke runbook
make managed-mysql-migration-check  # managed test-env migration runbook
make mysql-parity-static            # offline MySQL parity checks (safe; no credentials)
make mysql-parity-staging           # opt-in disposable-staging parity gate (skips with no DSN)
make mysql-collation-audit          # offline governed-collation audit (safe; no credentials)
make production-mysql-collation-verify  # READ-ONLY production check (opt-in; skips unless configured)
```

Or invoke them directly, without the Makefile:

```bash
python3 tests/validate_phase1.py
python3 tests/validate_phase2.py
python3 tests/validate_phase3_prompts.py       # stdlib-only, no dependency needed
python3 tests/validate_phase4_outputs.py       # stdlib-only, no dependency needed
python3 tests/validate_phase5_runner.py        # stdlib-only, no dependency needed
python3 tests/validate_phase6_docs.py          # stdlib-only, no dependency needed
python3 tests/validate_phase7_policy.py        # stdlib-only, no dependency needed
python3 tests/validate_phase8_architecture.py  # stdlib-only, no dependency needed
python3 tests/validate_phase9_governance.py    # jsonschema + stdlib
python3 tests/validate_phase10_database_plan.py # stdlib-only, no dependency needed
python3 tests/validate_phase11_db_scaffold.py   # stdlib-only, no dependency needed
python3 tests/validate_phase12_agentnet_mcp_boundary.py  # stdlib-only, no dependency needed
python3 tests/validate_phase13_agent_harness.py          # stdlib-only, no dependency needed
python3 tests/validate_phase14_evidence_worker.py        # stdlib-only, no dependency needed
python3 tests/validate_phase15_review_gate.py            # stdlib-only, no dependency needed
python3 tests/validate_phase16_review_persistence.py     # stdlib-only, no dependency needed
python3 tests/validate_phase17_controlled_db_writer.py   # stdlib-only, no dependency needed
python3 tests/validate_phase18_evidence_persistence.py   # stdlib-only, no dependency needed
python3 tests/validate_phase19_agent_run_persistence.py  # stdlib-only, no dependency needed
.venv/bin/python tests/validate_phase20_agent_run_writer.py  # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase21_evidence_writer.py   # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase22_review_writer.py     # DB-backed (SQLAlchemy); skips DB layer on plain python3
python3 tests/validate_phase23_packet_ingestion.py           # stdlib-only, no dependency needed
.venv/bin/python tests/validate_phase24_source_ingestion_writer.py  # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase25_packet_processing_orchestrator.py  # structural+plan-only always; DB layer needs SQLAlchemy
python3 tests/validate_phase26_agent_task_queue_readiness.py               # stdlib-only, no dependency needed (DB-free)
.venv/bin/python tests/validate_phase27_agent_task_queue_writer.py         # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase28_packet_task_queue_integration.py   # structural+plan-only always; DB layer needs SQLAlchemy
python3 tests/validate_phase29_review_orchestration_boundary.py             # stdlib-only, no dependency needed (DB-free)
.venv/bin/python tests/validate_phase30_review_bundle_writer.py             # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase31_packet_review_bundle_integration.py # structural+plan-only always; DB layer needs SQLAlchemy
python3 tests/validate_phase32_internal_reviewer_decision_boundary.py       # stdlib-only, no dependency needed (DB-free)
.venv/bin/python tests/validate_phase33_internal_reviewer_decision_writer.py # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase34_intake_note_writer.py               # DB-backed (SQLAlchemy); skips DB layer on plain python3
python3 tests/validate_phase34_managed_mysql_rubric.py                       # stdlib-only, credential-free, no live network
.venv/bin/python tests/validate_phase35_managed_record_workflow.py           # structural+plan-only always; DB layer needs SQLAlchemy
python3 tests/validate_phase36_internal_assessment_report_planning.py        # stdlib-only, no dependency needed (DB-free)
.venv/bin/python tests/validate_phase37_internal_assessment_report_draft_writer.py # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase38_internal_report_review_packet_writer.py   # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase39_internal_report_review_packet_decision_writer.py # DB-backed (SQLAlchemy); skips DB layer on plain python3
.venv/bin/python tests/validate_phase40_internal_report_review_workflow.py # DB-backed (SQLAlchemy); skips DB layer on plain python3
python3 tests/validate_phase41_managed_mysql_production_parity.py # offline; credential-free; no network
python3 tests/validate_phase42_governed_mysql_collation_policy.py # offline; credential-free; no network
python3 tests/validate_phase43_production_mysql_collation_verification.py # offline; credential-free; no network
```

## Exit codes

All thirty-two harnesses share the same convention:

| Code | Meaning |
| --- | --- |
| `0` | All blocking checks passed. |
| `1` | A schema, fixture/packet conformance, structure, or hygiene check failed. |
| `2` | A dependency is missing (install `requirements-dev.txt`). |

The nonzero-on-failure behavior makes these harnesses safe to wire into CI later
without additional tooling.
