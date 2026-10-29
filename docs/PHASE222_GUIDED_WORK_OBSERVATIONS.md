# Phase 222 — Guided Work Observations

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `8aef09e`.

## Purpose

Phase 218 guides a consultant through an authorized phase's tasks. Phase 222 lets the consultant
write an observation while doing a task, from the task page. That observation then feeds the same
assessment path as every other observation:

```
Phase task → zero or more consultant-authored observations → (optional) linked evidence
```

**Status: CLOSED in production (2026-10-29)**, with one deferred acceptance item: the first real
work observation (see *Production cutover and closure*). Implementation `bb53b17`.

## Rule

A work observation is written by the consultant, in their own words. Task records and captured
evidence can be context or support, but they never create an observation or add words to one.
Recording an observation never:
- changes task status, completion rules or phase readiness;
- creates a finding or recommendation of its own, beyond what any observation already feeds;
- changes recommendation eligibility;
- leads Peak to read or interpret a capture.

## What it is not

There is no SI-generated observation, OCR or image interpretation, scoring, automatic finding or
recommendation, report redesign, client access or publication. It carries no audit or compliance
meaning.

## Model chosen

**One observation model.** A work observation is an ordinary `discovery_observations` row, so it
keeps everything an observation already has:
- the engagement and client;
- the recording consultant (the signed-in consultant);
- the text, category, basis (Phase 216), low-hanging fruit, and effort and value;
- in-place editing, with the existing UPDATE grant and no revision chain;
- Phase 221 evidence links;
- the assessment read (`fetch_observation_summaries`), unchanged.

Only its origin is new. No existing field could hold it: `session_id` names an interview, and
`details_json` is a governance column.

## Data model (migration 025)

One new table, `observation_task_origins`. It is insert-only: an ORM listener refuses update and
delete, singly and in bulk. It is classified `append_only`, so the runtime role needs no UPDATE
grant. No existing table changes, so no existing table is rebuilt and the existing rows and
checksums stay as they are.

| Column | Meaning |
|---|---|
| `id` | `otor_<16 hex>` |
| `client_id`, `engagement_id` | Copied from the task |
| `observation_id` | The `discovery_observations` row |
| `phase_id`, `task_id` | The phase task it was recorded during |

`UNIQUE(observation_id)` (`uq_observation_task_origins_observation`) gives an observation at most
one origin. A task can have any number of observations. The origin is written once, in the same
transaction as the observation, and never moves. There are no foreign keys, as with every workspace
table. All id columns are governed identifiers (`utf8mb4_bin` on MySQL) under the existing `_id`
pattern.

A task record is not linked. Records supersede one another, and the task already ties the
observation to the work. A record can be cited in the observation text if it matters.

## Rules on saving

`POST /tasks/{task_id}/observations` takes the same fields as an observation edit:
- text, category, basis, low-hanging fruit, effort and value;
- an optional prompting question;
- optional `evidence_ids` (Phase 221).

The engagement is the task's engagement. In one transaction:
- The task's phase must be authorized (`phase_not_authorized` / `phase_closed`).
- The task must be accepted and not resolved (`task_not_accepted` / `task_resolved`), the same rule
  as task records and evidence capture.
- The text is required (`invalid_field`). Nothing fills it in.
- A work observation names no interview (422), and the origin cannot be changed on edit (422).
- Each linked capture follows the Phase 221 rules (`invalid_link`, `evidence_replaced`,
  `duplicate_link`).

Any refusal refuses the whole save: no observation, origin or link. The service also refuses a task
of another engagement (`invalid_link`).

## API

| Route | Auth | What it does |
|---|---|---|
| `GET /tasks/{id}/observations` | session | The task's observations, newest first, each with its origin, and `recording_closed` (null when recording is open) |
| `POST /tasks/{id}/observations` | session | Records a work observation (201) |
| `GET /engagements/{id}/discovery`, `GET /observations/{id}` | session | As before, plus `origin` on each observation (null for other observations) |
| `GET /engagements/{id}/assessment` | session | As before, plus `observation_origins` (origin by observation id) **beside** `assessment` |

An origin carries the phase id and title and the task id, title and sequence. No response carries a
storage key or file name.

## Consultant workflow

The task page has an **Observations** section below Photos and documents:
- the observations recorded during this task, each with its linked photos and an Edit link;
- **Add observation** (open when there are none): the usual observation form without the interview
  and question choices, plus the Phase 221 evidence picker. The picker lists this task's captures
  first, then the engagement's other current captures.

The text starts empty and nothing is prefilled from a record, caption or result summary. Recording an
observation is optional and no completion rule asks for one. If the API has no Phase 222 route, the
section reads "Observations are currently unavailable here" and the rest of the task page is
unchanged.

On the engagement page, a work observation's card shows **Work observation** and **Observed during:
Task n: title · phase**, linked to the task. The edit page is the existing one.

**Touch targets.** With real content on these pages, some existing links were under 40px: the
evidence provenance task link (Phase 221) and the assessment trace links "Open observation", the
interview link, "Set one in Discovery" and "Start an interview" (Phase 206). They are now
touch-sized. The provenance line puts kind and date on one row and the task link on its own row.
This changes styling only.

## Assessment integration and provenance

A work observation becomes a discovery-derived finding exactly like any other observation: same
read, same projection and same finding fields, quoting the consultant's text. No finding-generation,
recommendation or readiness rule changed. On the assessment page its card's trace reads **Work
observation · Observed during: Task n: title · phase** where an interview observation reads "From
the interview with …". Linked evidence shows below it (Phase 221).

The origin is returned beside the assessment, not inside it:
- the assessment dataclasses and Markdown are unchanged;
- the Final Report (JSON, Markdown, DOCX, stored versions) is unchanged. A work observation appears
  there as any observation does, with the existing "Recorded outside an interview" trace.

## Validation

`tests/validate_phase222_guided_work_observations.py` (`make validate-phase222`) covers:
- **migration 025:** upgrade, head ancestry, column parity, UNIQUE observation, downgrade, no data;
- **persistence policy:** `append_only`, one create action, ORM refuses update and delete;
- **recording:** with and without evidence (this task's and another task's), engagement, consultant,
  exact text and basis, origin, the task read, the engagement list, edit in place keeps the origin;
- **refusals:** another engagement's evidence, an unknown task, an unauthorized phase, a resolved
  task, an interview, another engagement's task, missing or blank text, moving the origin, and an
  atomic refusal that writes nothing;
- **nothing automatic:** a task record and captures create no observation;
- **assessment:** the finding quotes the text and has the same fields as any observation's;
  `observation_origins` and links beside it; nothing inside the assessment or report;
- **boundary:** only observations, origins and links change; evidence-backed findings, Final Report
  recommendations, task status and readiness are unchanged; reads write nothing;
- **no leaks:** no storage key or file name in any response;
- **static UI:** the task section, degrade path, neutral labels, no generated wording, the
  advisory-boundary scan, and no report or workflow code reading origins.

The Phase 221 harness's literal head check now asserts that the head descends from 024.

## Production sequencing (when approved)

The API must not run against production before migration 025 exists, because the discovery,
observation and assessment reads now read origins. The web may go first: without the route, the
task section reads as unavailable and every other page is unchanged.

1. Commit with `[skip render]`.
2. Apply migration 025 with `peak_prod_migrate`. The runtime role needs no new grant.
3. Move `EXPECTED_ALEMBIC_HEAD` to `025_observation_task_origins` in a follow-up commit. Run the
   verifier and the Phase 50 gate.
4. Deploy the API, then confirm the web.

## Production schema cutover (2026-10-29)

**Status: schema cutover complete.** The API deploy and production checks followed the same day.

**Preflight (read-only).** The repository was at `bb53b17`, clean, with one Alembic head; 025 was
the only pending step. The migration file was identical to the committed one. As
`peak_prod_verify_ro`:
- head `024_observation_evidence_links`;
- 37 base tables, `observation_task_origins` absent;
- the 30-table `COUNT(*)` + `CHECKSUM TABLE` baseline (133 rows) identical to the Phase 221 final
  snapshot;
- verifier `verified_safe_no_remediation_required` (420/420, 11/11).

The Phase 50 gate passed as `peak_prod_runtime`.

**Migration.** Migration 025 was re-read just before it ran, identical to the reviewed file. As
`peak_prod_migrate`, with the target guard (`PEAK_ALEMBIC_TARGET=production`,
`PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`):
`alembic upgrade 025_observation_task_origins` ran `024 → 025` only.

**Schema check afterwards (read-only):**

| Property | After |
|---|---|
| Alembic head | `025_observation_task_origins`, single row |
| Base tables | 38 (37 application + `alembic_version`), matching the models |
| `observation_task_origins` | InnoDB, 0 rows; 16 columns, nullability and collation as the model; 11 governed columns `utf8mb4_bin` |
| Constraints | primary key; UNIQUE `uq_observation_task_origins_observation (observation_id)`; 10 `ix_*`; no CHECK, trigger or foreign key |
| Existing tables | no `CREATE_TIME` changed (no rebuild); the 30-table baseline (133 rows) unchanged |
| `observation_evidence_links`, `phase_task_evidence` | 0 rows each |
| Phase 217 tables | `roadmap_items`, `engagement_phases`, `phase_tasks`, `phase_task_records` all 0 rows |

**Grants.** None changed. `SHOW GRANTS` for `peak_prod_runtime` was identical before and after.
The schema-wide `SELECT, INSERT` on `defaultdb.*` covers the append-only origin table. No grant
names `observation_task_origins`, and there is no UPDATE or DELETE on it. The Phase 50 gate passed.

**Verifier.** `EXPECTED_ALEMBIC_HEAD` was moved to 025 only after the migration. The live run
returned `verified_safe_no_remediation_required`:
- head matches;
- 38 tables;
- 431/431 governed columns deterministic (420 + 11);
- 11/11 idempotency boundaries safe;
- 0 at risk.

**Not done.** No Render deploy or environment change, no Vercel action and no R2 action during the
schema cutover. No production data was created.

At the end of the schema cutover, the API deploy and the production checks were still to do. Both
were completed the same day (see the next section).

## Production cutover and closure (2026-10-29)

**Status: complete (2026-10-29). Phase 222 is CLOSED**, with one deferred acceptance item (below).
No production data was written.

- **Schema.** Migration 025 applied and verified (previous section). The verifier pin was moved to
  025 in `b632b8a`.
- **Releases.**
  - Render API `peak-consultant-api`, deploy `dep-dbhq3vqfngtc73caanpg`, **Live**, at commit
    `b632b8a10cb9d5a9ac919448346b90966e4ba29b`; startup was clean;
  - Vercel web: the production deployment of `b632b8a`, successful.

  No environment variable, grant or R2 change was needed.
- **API check (read-only, logged out):**
  - `/healthz` returned 200;
  - `GET` and `POST /tasks/{id}/observations` return 401. A route that does not exist returns 404, so
    the Phase 222 route is deployed and requires a session;
  - the Phase 221 evidence route and the assessment also return 401.
- **No signed-in check.** A signed-in read would have shown only empty state, because there is no
  task. Phase 221's signed-in checks already cover the engagement, discovery and assessment pages
  on the same production data.
- **Preservation (read-only, at closure):**
  - head `025_observation_task_origins`, 38 base tables;
  - `observation_task_origins`, `observation_evidence_links` and `phase_task_evidence` 0 rows;
  - `roadmap_items`, `engagement_phases`, `phase_tasks` and `phase_task_records` 0 rows;
  - the 30-table baseline unchanged at 133 rows, `changed_tables = []`;
  - runtime grants identical to the pre-migration record, with no UPDATE or DELETE on the new table;
  - the Phase 50 gate PASS: required grants present, no excess grants, no global privileges and no
    grant option;
  - the verifier `verified_safe_no_remediation_required`: head matches, 431/431 governed columns
    deterministic, 11/11 idempotency boundaries safe, 0 at risk, no warnings, no schema change or
    data write.

**Deferred acceptance.** Production has no engagement phase and no phase task. Four
consultant-workspace internal-test engagements exist, but all are logically deleted. The one active
engagement is the legacy internal-test anchor, which cannot have phases or tasks. So there is no
legitimate task to record a work observation against.

A synthetic client, engagement, phase, task and authorization chain was deliberately not created
only for acceptance. The first production work observation is deferred until the first legitimate
authorized production task exists. This is an operational acceptance checkpoint, not unfinished
implementation: the full write and read path is covered by the Phase 222 harness and the local
walkthrough.

When the first real work observation is recorded, confirm:
- the POST through the task page (`POST /tasks/{id}/observations`) returns 201;
- exactly one `discovery_observations` row is created;
- exactly one `observation_task_origins` row is created for it;
- its client, engagement, phase and task match the task;
- its `session_id` is null;
- its recorder is the signed-in consultant;
- the task, engagement discovery, observation and assessment reads show the expected origin;
- task status, phase status, readiness and recommendations do not change;
- the verifier and the Phase 50 gate remain clean afterwards.
