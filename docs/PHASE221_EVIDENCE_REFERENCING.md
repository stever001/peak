# Phase 221 — Evidence Referencing

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `0001174`.

## Purpose

Phase 220 lets a consultant capture photos and document photos on a task. Phase 221 lets the
consultant say which of those captures support an observation they wrote, and shows that link
later in the internal assessment:

```
Observation (consultant's own words) → zero or more captured items of the same engagement
```

**Status: CLOSED in production (2026-10-29)**, with one deferred acceptance item: the first real
observation→evidence link (see *Production cutover and closure*). Implementation `0fd8bd1`.

## Rule

Evidence remains source material. A link is the consultant's statement that a capture supports
their observation. It never:
- creates an observation, finding or recommendation;
- adds words to an observation;
- changes readiness, task status or recommendation eligibility;
- becomes governed assessment evidence (`evidence_references`);
- leads Peak to read, parse or interpret the capture (no OCR, CV or inference).

## What it is not

There is no unlink, re-link, scoring, automatic suggestion, client upload, PDF, report image
embedding, publication, or retention/delete system. A link is not an audit or compliance record.

## Existing linkage

None was reusable:
- `evidence_references` is the governed assessment-evidence chain. Phase 220 deliberately keeps
  captures out of it.
- `phase_task_evidence.task_record_id` links a capture to a task record, not to an observation.
- `roadmap_items.source_observation_ids` is a JSON list on another record type.

So Phase 221 adds the smallest explicit link table.

## Data model (migration 024)

One new table, `observation_evidence_links`. It is insert-only: an ORM listener refuses update and
delete, singly and in bulk. It is classified `append_only`, so the runtime role needs no UPDATE
grant. No existing table changes.

| Column | Meaning |
|---|---|
| `id` | `oevl_<16 hex>` |
| `client_id`, `engagement_id` | Copied from the observation |
| `observation_id` | A `discovery_observations` row |
| `evidence_id` | A `phase_task_evidence` row of the same engagement |
| `linked_by_consultant_id` | The signed-in consultant; `created_at` says when |

`UNIQUE(observation_id, evidence_id)` (`uq_observation_evidence_links_pair`) links a pair at most
once. There are no foreign keys, as with every workspace table. All id columns are governed
identifiers (`utf8mb4_bin` on MySQL) under the existing `_id` collation pattern, so the collation
audit needed no change.

## Rules on saving

`evidence_ids` is accepted on `POST /engagements/{id}/observations` and
`PATCH /observations/{id}`. The links are written in the **same transaction** as the observation:
- Each capture must belong to the observation's engagement (`invalid_link`).
- Each capture must be current, not replaced (`evidence_replaced`).
- A pair cannot be linked twice, and the same id cannot be chosen twice (`duplicate_link`).
- At most 50 links per save.

Any refusal refuses the whole save: no observation, no edit, no link. A PATCH adds links; it never
removes one. The linking consultant is always the signed-in consultant.

## API

| Route | Auth | What it does |
|---|---|---|
| `GET /engagements/{id}/evidence` | session | `available`: current captures, newest first. `links`: each observation's linked captures. Every item has a 15-minute `content_path` |
| `POST /engagements/{id}/observations` | session | As before, plus optional `evidence_ids` |
| `PATCH /observations/{id}` | session | As before, plus optional `evidence_ids` (adds only) |
| `GET /engagements/{id}/assessment` | session | As before, plus `observation_evidence` (links by observation id) **beside** `assessment` |

Each item carries:
- kind and caption;
- the originating task (id, title, phase);
- who added it and when;
- `superseded` and `superseded_by`;
- for a link, who linked it and when.

Items never carry a storage key, file name or hash. Content is served by the Phase 220
`/evidence-content/{token}` route unchanged.

## Consultant workflow

- **Add observation** (engagement → Discovery): below the observation fields there is a "Supporting
  photos and documents (optional)" list. Each item shows a thumbnail, caption, kind, originating
  task (linked) and date, with a checkbox. The observation text stays empty until the consultant
  writes it. Nothing is prefilled from a caption.
- **Observation cards** show their linked captures.
- **Edit observation** shows the existing links above the form. The picker offers only captures not
  yet linked.
- Linking is optional everywhere. If the API has no Phase 221 route, the pages show and save
  observations exactly as before. The form sends `evidence_ids` only when one is chosen.

No "Use in observation" shortcut was added to the task page.

## Assessment traceability

Each discovery-derived finding card shows "Supporting photos and documents (n)". For each item it
shows the caption, kind, originating task, date and "Open full size". The links are returned
outside the assessment dataclasses. So:
- the assessment, its findings, low-hanging fruit and evidence-backed findings are unchanged;
- recommendations and the Markdown are unchanged;
- the Final Report (JSON, Markdown, DOCX, stored versions) is unchanged and embeds no image.

## Supersession

A link names the exact capture chosen. If that capture is later replaced on its task, the link
stays on the original. It is shown as "Replaced on its task since it was linked" and still opens.
The newer capture is never substituted. It becomes available to link separately. A replaced
capture cannot be newly linked.

## Validation

`tests/validate_phase221_evidence_referencing.py` (`make validate-phase221`) covers:
- **migration 024:** upgrade, single head, column parity, UNIQUE pair, downgrade, no data;
- **persistence policy:** `append_only`, one create action, ORM refuses update and delete;
- **links:** no links, one link, several links, adding on edit, the same capture on two
  observations;
- **refusals:** duplicate, repeated id, another engagement's capture, unknown and replaced captures,
  and an atomic refusal that writes nothing;
- **supersession:** the link is kept and labelled, nothing is substituted, the newer capture is
  offered;
- **assessment:** count, caption, task, and content opening;
- **no leaks:** no storage key or file name in any response;
- **boundary:** only the link table changes. The finding, evidence-backed material, Final Report
  recommendations, task status and readiness are unchanged, and nothing linked appears inside the
  assessment or report;
- **static UI:** picker, graceful degrade, no generated wording, the advisory-boundary scan.

## Production sequencing (when approved)

The API must not run against production before migration 024 exists, because its engagement
evidence read would fail. The web may go first: without the route, linking is hidden.

1. Commit with `[skip render]`.
2. Apply migration 024 with `peak_prod_migrate`. The runtime role needs no new grant.
3. Move `EXPECTED_ALEMBIC_HEAD` to `024_observation_evidence_links` in a follow-up commit. Run the
   verifier and the Phase 50 gate.
4. Deploy the API, then confirm the web.

## Production schema cutover (2026-10-29)

**Status: schema cutover complete.** The API deploy and production checks followed the same day.

**Preflight (read-only).** The repository was at `0fd8bd1`, clean, with one Alembic head; 024 was
the only pending step. The migration file was identical to the committed one. As
`peak_prod_verify_ro`:
- head `023_phase_task_evidence`;
- 36 base tables, `observation_evidence_links` absent;
- the 30-table `COUNT(*)` + `CHECKSUM TABLE` baseline (133 rows) identical to the Phase 220 final
  snapshot;
- verifier `verified_safe_no_remediation_required` (409/409, 11/11).

The Phase 50 gate passed as `peak_prod_runtime`.

**Migration.** Migration 024 was re-read just before it ran, identical to the reviewed file. As
`peak_prod_migrate`, with the target guard (`PEAK_ALEMBIC_TARGET=production`,
`PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`):
`alembic upgrade 024_observation_evidence_links` ran `023 → 024` only.

**Schema check afterwards (read-only):**

| Property | After |
|---|---|
| Alembic head | `024_observation_evidence_links`, single row |
| Base tables | 37 (36 application + `alembic_version`), matching the models |
| `observation_evidence_links` | InnoDB, 0 rows; 16 columns, nullability and collation as the model; 11 governed columns `utf8mb4_bin` |
| Constraints | primary key; UNIQUE `uq_observation_evidence_links_pair (observation_id, evidence_id)`; 9 `ix_*`; no CHECK, trigger or foreign key |
| Existing tables | no `CREATE_TIME` changed (no rebuild); the 30-table baseline (133 rows) unchanged |
| `phase_task_evidence` | 0 rows |
| Phase 217 tables | `roadmap_items`, `engagement_phases`, `phase_tasks`, `phase_task_records` all 0 rows |

**Grants.** None changed. `SHOW GRANTS` for `peak_prod_runtime` was identical before and after.
The schema-wide `SELECT, INSERT` on `defaultdb.*` covers the append-only link table. There is no
grant naming `observation_evidence_links`, and no UPDATE or DELETE on it. The Phase 50 gate passed.

**Verifier.** `EXPECTED_ALEMBIC_HEAD` was moved to 024 only after the migration. The live run
returned `verified_safe_no_remediation_required`:
- head matches;
- 37 tables;
- 420/420 governed columns deterministic (409 + 11);
- 11/11 idempotency boundaries safe;
- 0 at risk.

**Not done.** No Render deploy or environment change, no Vercel action and no R2 action during the
schema cutover. No production data was created.

At the end of the schema cutover, the API deploy and the production checks were still to do. Both
were completed the same day (see the next section).

## Production cutover and closure (2026-10-29)

**Status: complete (2026-10-29). Phase 221 is CLOSED**, with one deferred acceptance item (below).
No production data was written.

- **Releases.** Both from `6c1fbfb` (*Advance verifier to Phase 221 schema*; the verifier pin is at
  `024_observation_evidence_links`):
  - Render API `peak-consultant-api`, deploy `dep-dbhov2g8v5cc73925ag0`, **Live**, at commit
    `6c1fbfbbed9749caccbedf1b3fa37ddcd5151cc9`;
  - Vercel web: the production deployment of `6c1fbfb`, successful.
- **Health.** `/healthz` returned 200.
- **Authenticated API check (existing Admin, read-only):**
  - logged out, the Phase 221 evidence route, the assessment, discovery and observation reads all
    return 401;
  - login 200, `/auth/me` 200 admin, `/engagements` 200;
  - signed in, the unknown-engagement evidence and assessment routes and an unknown observation
    return the application's 404 `not_found`. A route that does not exist returns FastAPI's
    `Not Found`, so the Phase 221 route is registered;
  - the engagement and its discovery read 200. Its evidence read returned 200, with 0 available
    captures and 0 linked observations;
  - the assessment route returns 404 for the existing engagement: it has no assessment yet. The
    route has returned 404 for this since Phase 206, so this is not a Phase 221 failure;
  - no storage key, file name or hash appears in any response;
  - logout 204, then `/auth/me` 401.
- **Web check (read-only):**
  - logged out, the engagement, assessment and observation-edit pages redirect to login;
  - signed in, the engagement page renders with no application error. The only production
    engagement is the legacy internal-test anchor. Its Discovery card shows the existing notice
    "Discovery is available for engagements created in the consultant workspace", so it has no
    Add observation form. That is why no evidence picker appears. The picker's empty state ("No
    photos or documents have been captured…") was verified in the local walkthrough, not in
    production;
  - the assessment page handles the API's 404 without an application error and shows no linked
    evidence;
  - an unknown observation's edit page shows the normal not-found page;
  - no raw ids, storage keys or file names appear in page text or HTML;
  - Phase 221 wording contains no audit or compliance terms. The only whole-page boundary term is
    the existing delete-card copy ("kept for audit"), as in Phase 220;
  - no non-GET request was made during page loads.
- **Responsive.** The engagement, assessment and unknown observation-edit pages were measured at
  1440×900, 820×1180 and 1180×820. Every result was `overflow_px=0`, `elements_past_edge=0` and
  `controls_under_40px=0`.
- **Runtime identity.** The API pool connects as `peak_prod_runtime` on `defaultdb`. No verify or
  migrate credential is in the runtime pool.
- **Preservation (read-only, after the checks):**
  - head `024_observation_evidence_links`, 37 base tables;
  - `observation_evidence_links` and `phase_task_evidence` 0 rows;
  - the four Phase 217 tables 0 rows;
  - the 30-table baseline unchanged at 133 rows, `changed_tables = []`;
  - the Phase 50 gate PASS: required grants present, no excess grants, no global privileges and no
    grant option;
  - the verifier `verified_safe_no_remediation_required`: head matches, 420/420 governed columns
    deterministic, 11/11 idempotency boundaries safe, 0 at risk.

**Deferred acceptance.** Production creation of the first observation→evidence link is deferred
until legitimate production evidence and a consultant-authored observation exist. No synthetic
production consulting workflow or evidence was created solely for acceptance. Phase 221 production
API, schema, zero-state behavior, authorization, persistence boundaries and assessment integration
paths were verified without production writes.

When the first real link is saved, confirm three things:
- the `observation_evidence_links` row names that observation and capture;
- the observation and the assessment show the link;
- nothing else changed.

No production evidence or link row was created during the cutover, and R2 was not touched.
