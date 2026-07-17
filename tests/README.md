# Tests

Validation for the source assets. Deliberately dependency-light: Python standard
library plus `jsonschema` (which brings `referencing`). No pytest, no database, no API
server, no network.

**No committed example data.** The repo stores source assets only. Where representative
objects are needed, the harnesses build **synthetic fixtures at runtime**
([`synthetic_fixtures.py`](synthetic_fixtures.py)) and write them to a temporary
directory that is auto-deleted. Nothing is stored. See
[`../docs/FIXTURE_STRATEGY.md`](../docs/FIXTURE_STRATEGY.md).

Twenty-six harnesses, run together by `make validate`:

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
was added (exactly five migration files, no `006_*`, Alembic head stays `005_source_ingestion_idem`);
and that the docs carry the required language. The **functional** layer runs
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

## Running

This machine uses `python3` (there is no bare `python`). From the repo root:

```bash
# one-time: install the dev dependency
make install-dev          # == python3 -m pip install -r requirements-dev.txt

# run all harnesses
make validate             # == phase1 … phase26

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
```

## Exit codes

All twenty-six harnesses share the same convention:

| Code | Meaning |
| --- | --- |
| `0` | All blocking checks passed. |
| `1` | A schema, fixture/packet conformance, structure, or hygiene check failed. |
| `2` | A dependency is missing (install `requirements-dev.txt`). |

The nonzero-on-failure behavior makes these harnesses safe to wire into CI later
without additional tooling.
