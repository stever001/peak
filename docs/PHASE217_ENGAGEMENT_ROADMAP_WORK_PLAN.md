# Phase 217 — Engagement Roadmap and Guided Work Plan Foundation

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `63b3c65`.

## Purpose

Peak should let a relatively inexperienced consultant deliver professional SMB inventory and
process consulting: interpret discovery, propose useful follow-on phases, have each paid phase
separately agreed, be guided step by step through the authorized work, and record what actually
happened, so that findings and the Final Report can later rest on completed, documented work.

Phase 217 builds only the primitives:

```
Discovery → roadmap item (advisory) → engagement phase (separately authorized)
          → guided work plan (ordered tasks) → consultant task records → completion readiness
```

Not built: proposal documents, fees, e-signature, billing, evidence/photo upload, Final Report
changes, AgentNet changes, a governed audit capability, consultant training, a generic workflow
engine, any web UI.

## Current state found (before Phase 217)

- `engagements.status` is a coarse engagement state (active / on_hold / closed) and
  `engagements.current_phase` is a free-text label. There was no phase entity.
- Contract C9 and ARTIFACT_LIFECYCLE AL1 already define "Engagement Phase" as a *consulting stage*
  and place it between engagement and artifact. `artifacts.engagement_phase_label` snapshots the
  free-text label. The new record realizes that concept; it does not conflict with it.
- Discovery observations (Phase 204/216) are explicit consultant statements with an optional
  prompting question (whose category places them in a discovery domain) and a basis. They are the
  only legitimate grounding for a roadmap suggestion. Answers guide discovery and never establish
  anything (Phase 216, Contract C4).
- Artifacts and versions are engagement-scoped and immutable; a proposal or final report artifact
  can later bind to a phase by an added `engagement_phase_id` on `artifacts`.
- Discovery observations cannot be reused as phase-work records: the assessment and Final Report
  compose from them, so phase work would leak into the report. Phase work gets its own records.

## Model (migration `022_engagement_roadmap_work_plan`, four new tables)

| Table | What it is | Mutability |
|---|---|---|
| `roadmap_items` | Proposed future work: sequence, title, problem framing, rationale, expected outcome, source observation ids, origin (`peak_method` / `consultant` / `si_suggested`), template key, method version | Framing fixed at creation; revision = new item with `supersedes_item_id`. Lifecycle: proposed → accepted / deferred / declined; superseded |
| `engagement_phases` | One authorized unit of work: origin (`roadmap_item` / `manual` + required reason), title, scope, status planned → authorized → completed, authorization basis/reference/who/when, completion who/when | Status columns only |
| `phase_tasks` | Ordered guided tasks of one phase: instructions, why, what to observe, suggested evidence kinds, follow-up questions, expected result, required, requires-record, prerequisites, one condition (an earlier task recorded a given record kind), origin, template key, inclusion reason, `added_after_authorization`, status, notes, result summary | Framing fixed; only progress columns change |
| `phase_task_records` | What the consultant recorded: note, interview response, measurement, mismatch (structured fields per kind), basis; photo / document photo / document reserved | Insert-only (ORM listeners refuse update/delete); a correction supersedes |

Work-plan state is derived (not_started / draft / active / closed). A proposal/fee binding is not a
column; it is future artifact binding.

## Rules enforced (service `peak/workspace/engagement_phases.py`)

- A Peak Method or synthesis roadmap item must cite observations of its own engagement
  (`ungrounded_suggestion`). Suggestions (`peak/workspace/peak_method_phases.py`) are deterministic:
  a template is suggested when an observation falls in one of its discovery categories.
- Accepting a roadmap item authorizes nothing. Only an accepted item becomes a phase, at most once.
- Authorization is recorded by the engagement's Lead or an Admin, with a stated basis. Nothing infers
  it. No record or completion is possible before it.
- Tasks are completed only by the signed-in consultant, with a result summary, after prerequisites,
  and with a record when the task requires one. A synthesis-suggested task enters as `suggested` and
  does nothing until a consultant accepts it. Tasks added after authorization are marked.
- **Readiness** (`phase_readiness`): ready when the phase is authorized, the plan has a task, and
  every required task that applies is completed or resolved not applicable with a reason. Optional,
  suggested and unmet-condition tasks never block. A phase completes only when ready.
- Framing passes the advisory boundary (Contract C21, [`ADVISORY_ENGAGEMENT_BOUNDARY.md`](ADVISORY_ENGAGEMENT_BOUNDARY.md)).

## API

`GET /engagements/{id}/roadmap` · `POST /engagements/{id}/roadmap-items` ·
`POST /roadmap-items/{id}/decision` · `POST /roadmap-items/{id}/revision` ·
`GET|POST /engagements/{id}/phases` · `GET /phases/{id}` · `GET /phases/{id}/readiness` ·
`POST /phases/{id}/authorization` · `POST /phases/{id}/template-tasks` · `POST /phases/{id}/tasks` ·
`POST /phases/{id}/completion` · `PATCH /tasks/{id}` · `POST /tasks/{id}/acceptance` ·
`POST /tasks/{id}/completion` · `POST /tasks/{id}/not-applicable` · `POST /tasks/{id}/records`.

## Production cutover

**Status: complete (2026-10-23). Phase 217 is CLOSED.** The sequence below was carried out as
written. The [record](#production-cutover-record-2026-10-23) follows it.

### Runtime grant policy (Phase 50 gate, prepared in the repository)

`APPROVED_TABLE_UPDATE` in `tools/production_runtime_connectivity_gate.py` now holds exactly nine
tables: the six from Phases 203/205 (`clients`, `engagements`, `discovery_questions`,
`discovery_sessions`, `discovery_answers`, `discovery_observations`) plus `roadmap_items`,
`engagement_phases` and `phase_tasks`. **`phase_task_records` is not approved:** it is insert-only,
so table-level UPDATE on it fails the gate. The rest of the policy is unchanged: global `USAGE`
only; `defaultdb.*` exactly `SELECT, INSERT`; no UPDATE at schema or global scope; DELETE, DDL,
admin, role and `GRANT OPTION` fail. Today's six-table production grants are a subset and still pass.

### Why the order matters

- The Phase 217 API runs on a `021` schema, but only partly: existing routes are unaffected (no
  existing model changed), and the 17 Phase 217 routes fail with a generic 500 (`no such table`),
  writing nothing. There is no startup schema-head check. So `022` must be applied first.
- After `022` and before the UPDATE grants, phase work would create rows but fail on any status
  change (authorization, task progress). The grants must be in place before the deploy.

### Expected numbers at `022`

- 35 base tables (31 + 4), no existing table altered, every new table empty.
- Verifier: 394/394 governed columns deterministic (345 + 49 new, all pinned `utf8mb4_bin` by the
  migration), 11/11 idempotency boundaries (unchanged; the new tables carry no `idempotency_key`).
- Constraints:
  - CHECK: `ck_roadmap_items_{status,origin,sequence}`, `ck_engagement_phases_{status,origin}`,
    `ck_phase_tasks_{status,origin,condition_kind,sequence}`, `ck_phase_task_records_{kind,basis}`;
  - UNIQUE: `uq_roadmap_items_supersedes`, `uq_engagement_phases_roadmap_item`,
    `uq_phase_tasks_sequence`, `uq_phase_task_records_supersedes`;
  - 31 secondary `ix_*` indexes.

### Sequence (each step separately approved)

1. **Repository.** The commit containing this section and the nine-table gate is on `origin/main`.
2. **Preflight, read-only, as `peak_prod_verify_ro`:**
   - `alembic_version` is a single row `021_discovery_observation_trace_basis`;
   - 31 base tables, none of the four new ones;
   - `make production-mysql-collation-verify` (pin still `021`) returns
     `verified_safe_no_remediation_required`, 345/345, 11/11;
   - record `COUNT(*)` and `CHECKSUM TABLE` for each of the 30 existing application tables
     (SELECT only; the Phase 216 count-and-fingerprint method).
3. **Preflight gate, as `peak_prod_runtime`:** `make runtime-connectivity-gate` passes against the
   current six-table grants under the nine-table policy.
4. **Migrate**, as `peak_prod_migrate`, in a subshell: `PEAK_ALEMBIC_TARGET=production`,
   `PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`,
   `alembic upgrade 022_engagement_roadmap_work_plan`. Applies `021 → 022` only.
5. **Verify the schema, read-only:**
   - head `022_engagement_roadmap_work_plan`;
   - 35 base tables;
   - the four tables exist, are empty, and carry the constraints and indexes listed above (from
     `information_schema`).
6. **SELECT/INSERT coverage.** As `peak_prod_runtime`, `SHOW GRANTS FOR CURRENT_USER()` still shows
   `SELECT, INSERT ON defaultdb.*` with no table-level revoke. That schema-scoped grant covers all
   four new tables. A `SELECT COUNT(*)` on each returns 0. INSERT is proven by scope, not by writing.
7. **Grant.** As `peak_prod_migrate` (as in Phase 205):
   ```sql
   GRANT UPDATE ON `defaultdb`.`roadmap_items`      TO `peak_prod_runtime`@`%`;
   GRANT UPDATE ON `defaultdb`.`engagement_phases`  TO `peak_prod_runtime`@`%`;
   GRANT UPDATE ON `defaultdb`.`phase_tasks`        TO `peak_prod_runtime`@`%`;
   ```
   **No grant on `phase_task_records`.** No DELETE, DDL or schema-wide change.
8. **Confirm no UPDATE on `phase_task_records`.** As `peak_prod_runtime`, `SHOW GRANTS` is exactly:
   - USAGE on `*.*`;
   - `SELECT, INSERT` on `defaultdb.*`;
   - nine table-level UPDATE lines;
   - no line naming `phase_task_records`.
9. **Gate.** `make runtime-connectivity-gate` against the live grants passes. The gate itself fails
   on UPDATE on `phase_task_records`, or on any tenth table.
10. **Verifier re-pin.**
    - Move `EXPECTED_ALEMBIC_HEAD` to `022_engagement_roadmap_work_plan` only now (Phase 58 rule),
      in a separate commit.
    - Run `make production-mysql-collation-verify`. Expect `verified_safe_no_remediation_required`,
      394/394, 11/11, 35 tables.
11. **No unexpected change.** Repeat the step 2 `COUNT(*)` and `CHECKSUM TABLE` for the 30 existing
    tables. They must equal the preflight values.
12. **Only then is the API eligible for deployment:**
    - manual Render deploy, Auto-Deploy confirmed off first;
    - health, login and logged-out checks;
    - Phase 217 routes return 401 when logged out, not 404.

    No Vercel deploy: Phase 217 has no UI.

**Rollback before step 7:** `alembic downgrade 021_discovery_observation_trace_basis` drops the four
empty tables. This needs separate approval, and the API must not have been deployed.

### Production cutover record (2026-10-23)

**Commits.** Implementation `3994ed8`; cutover preparation `6d558ab` (nine-table Phase 50 policy,
Phase 217 harness made order-independent); verifier pin `ba07f1e` `[skip render]`.

**Preflight (read-only).** As `peak_prod_verify_ro` unless noted:
- head `021_discovery_observation_trace_basis`;
- 31 base tables, none of the four Phase 217 tables;
- verifier `verified_safe_no_remediation_required`: 345/345 governed columns, 11/11 idempotency
  boundaries;
- `COUNT(*)` + `CHECKSUM TABLE` baseline over the 30 existing application tables (133 rows),
  identical on two passes;
- as `peak_prod_runtime`: runtime grants were the original six table UPDATEs, and the Phase 50 gate
  passed under the nine-table policy.

**Migration.** As `peak_prod_migrate`, with the target guard (`PEAK_ALEMBIC_TARGET=production`,
`PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`):
`alembic upgrade 022_engagement_roadmap_work_plan` ran `021 → 022` only, exit 0.

**Schema check afterwards (read-only):**

| Property | After |
|---|---|
| Alembic head | `022_engagement_roadmap_work_plan`, single row |
| Base tables | 35 (34 application + `alembic_version`) |
| New tables | `roadmap_items`, `engagement_phases`, `phase_tasks`, `phase_task_records`; InnoDB, primary key each, all empty |
| Constraints | 11 CHECK and 4 UNIQUE, names as designed; no foreign keys (none declared) |
| Indexes | 31 `ix_*` |
| Collation | 49/49 new governed columns `utf8mb4_bin`; 345/345 existing governed columns unchanged |
| Existing tables | no `CREATE_TIME` at or after the new tables (no rebuild); counts and checksums equal the baseline |

**Grants.** As `peak_prod_migrate`, exactly the three statements in step 7. As `peak_prod_runtime`,
`SHOW GRANTS` afterwards was:
- USAGE on `*.*`;
- `SELECT, INSERT` on `defaultdb.*`;
- table-level UPDATE on exactly the nine approved tables.

There was no UPDATE on `phase_task_records`, no schema or global UPDATE, no DELETE, DDL or admin
privilege, no `GRANT OPTION` and no role. The live Phase 50 gate passed.

**Verifier.** `EXPECTED_ALEMBIC_HEAD` was moved to 022 only after the migration (`ba07f1e`). The live
run returned `verified_safe_no_remediation_required`:
- head matches;
- 35 tables;
- 394/394 governed columns deterministic;
- 11/11 idempotency boundaries safe;
- no warnings.

**Render deploy.**
- `peak-consultant-api`: manual deploy `dep-dbdu468n74is73etg0b0` of `ba07f1e`, status **Live**.
- Auto-Deploy stayed Off, and no environment variable changed.
- Since `3994ed8`, the deployed tree differs only by the gate, tests, docs and verifier pin; there
  is no application code change.

**Post-deploy checks** (non-destructive):
- **Health:** `/healthz` returned 200.
- **Logged-out protection:** 401 on `/auth/me`, `/engagements`, `/clients`, `/questions`,
  `/consultants`, an engagement, its Final Report, and `POST /clients`.
- **Route registration:** all 17 Phase 217 routes returned 404 before the deploy and **401** after
  it, logged out. No 404 or 500.
- **Authenticated, read-only** (existing Admin, run by the operator):
  - login returned 200;
  - `/auth/me` returned 200 with role `admin`;
  - `/engagements` returned 200 with 1 engagement;
  - that engagement's `/roadmap` returned 200 (0 items, 0 suggestions);
  - its `/phases` returned 200 (0 phases);
  - logout returned 204, and `/auth/me` afterwards returned 401.
- **Runtime identity:** the process-list probe (read-only, as `peak_prod_migrate`; user names and
  counts only) showed one API connection, `peak_prod_runtime` on `defaultdb`, besides the server's
  `event_scheduler`. No `peak_prod_verify_ro` or other application user was observed.

**Final state.**
- Head `022`.
- Phase 50 gate PASS; verifier 394/394 and 11/11.
- The 30 existing tables' counts and checksums still equal the pre-022 baseline (133 rows).
- `roadmap_items`, `engagement_phases`, `phase_tasks` and `phase_task_records` each have 0 rows. No
  Phase 217 production record was created.

**No Vercel deploy:** Phase 217 has no UI. No production data was written at any step.

**Phase 217 is CLOSED.**

## Validation

`tests/validate_phase217_engagement_roadmap_work_plan.py` (`make validate-phase217`, in
`make validate`); `--example` prints the receiving example end to end.
