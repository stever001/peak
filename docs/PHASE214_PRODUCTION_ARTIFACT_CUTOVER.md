# Phase 214 — Production artifact workflow cutover

Phase 214 prepares the Phase 212/213 artifact workflow for production. It is a cutover phase, not a
feature phase: **no product functionality is added**, and migrations 018 and 019 are unchanged.
Baseline `4df89ff` — *Add Phase 213 artifact approval and release*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: the Phase 212/213 artifact workflow is live in production (2026-10-15).**
- Migrations 018/019 are applied: production is at `019_artifact_approval_release`, the verifier pin
  is at 019 and the verifier is green.
- The Render API runs `230a12a` (manual deploy, Auto-Deploy confirmed **Off**), and the Vercel web is
  deployed.
- Every logged-out check passes.
- **Authenticated acceptance remains pending provisioning of `admin@peakinventorysolutions.com`.**

## Baseline

| Check | Result |
|---|---|
| HEAD | `4df89ff`, clean working tree |
| Migrations | `017_discovery_workflow` → `018_artifact_versions` → `019_artifact_approval_release` |
| Alembic heads | `019_artifact_approval_release`, single head |
| Migrations 018/019 | unmodified; no defect found |

## Concurrency prerequisite: passed on a live MySQL server

The Phase 213 cutover prerequisite asked for Final Approver reassignment to be raced against the
final decision on two concurrent connections against a real MySQL instance. Phase 214 adds
`tests/validate_phase214_mysql_artifact_concurrency.py` (`make validate-phase214-mysql`; **not part
of `make validate`**, because it needs a live server).

**Environment.** A disposable MySQL **8.2.0** Community Server (the official build in
`/usr/local/mysql`), started on a fresh scratch data directory, bound to `127.0.0.1` only, then
stopped and discarded. No managed database, lab or production server was used. The script refuses
any non-loopback URL and any server where the schema already exists, and drops everything it
created when it finishes.

**Setup on that server.** The script:
- applies the real migrations with `alembic upgrade head`, so `017 → 018 → 019` itself ran on MySQL;
- gives the runtime user exactly the production runtime grants: `SELECT, INSERT` on the schema;
  `UPDATE` on `clients`, `engagements` and the four discovery tables; no `DELETE`;
- builds each fixture through the authenticated API: a package prepared, Lead-approved, and Fran
  designated Final Approver.

The schema is `peak_lab` and the migration user is `peak_lab_migrate`, because that is the only
non-production identity the Phase 84 migration target guard accepts. The loopback check is what
keeps the run off the managed lab.

**Method.**
- Two independent engines, one connection each, run the real `peak.workspace.approvals` functions
  on two threads.
- Transaction 1 is paused in `before_commit`: after its lock-first `SELECT … FOR UPDATE` and its
  checks, before its commit.
- Transaction 2 is then started.
- A third connection polls `performance_schema.data_lock_waits`. The pause is released only once
  that table shows transaction 2's connection waiting on transaction 1's connection for an
  exclusive lock on the `engagements` row.
- So the blocking is observed in InnoDB, not inferred from rendered SQL.

| Scenario | Result |
|---|---|
| **A** — final decision (approve, and separately reject) holds the lock; reassignment to Sam waits | InnoDB showed the wait (X lock on `engagements`); the reassignment stayed blocked while the lock was held, resumed after the decision committed, and was refused `final_decision_recorded`. Stored: one final decision by Fran bound to Fran's designation; no second designation |
| **B** — reassignment to Sam holds the lock; Fran's final decision (approve, and separately reject) waits | InnoDB showed the wait; Fran's decision resumed after the reassignment committed and was refused `not_designated_final_approver`. Stored: the reassignment, no final decision. Afterwards Fran is still refused, and Sam's decision is accepted and recorded against Sam's designation, so Sam is the only valid Final Approver |
| Grants | `SELECT … FOR UPDATE` on `engagements` succeeds with the production runtime grants; the database itself refuses `UPDATE` and `DELETE` (error 1142) on all seven artifact tables |

43 checks, 0 failures.

**Negative control.** The same script was run with `_lock_engagement` patched to a no-op, in
process only and with no code change. Every blocking check failed: no lock wait appeared, the
reassignment succeeded after a final decision, and the old designee's decision was accepted. The
test therefore detects a missing lock, and the passing result is evidence of the lock rather than of
timing.

## Production pre-cutover state (read-only, verified 2026-10-15)

The checks ran in a subshell with the existing read-only production credential and no other `PEAK_`
database variable. Only SELECT, `SHOW GRANTS` and metadata queries were issued, and no connection
value was printed. The checks were:
- a one-off probe (head, tables, row counts, grants);
- `tools/production_mysql_collation_verify.py`.

| Property | Verified |
|---|---|
| Server | MySQL **8.4.8**, `REPEATABLE-READ` (same isolation as the concurrency run) |
| Alembic head | `017_discovery_workflow`, single row |
| Base tables | **24**, including `alembic_version` |
| Artifact tables (018/019) | **none present** |
| Application rows | `engagements` 1 (Phase 59 anchor), `discovery_questions` 29; `clients`, `consultants`, `discovery_sessions`, `discovery_answers`, `discovery_observations` all **0**, as in Phase 207 |
| Runtime grants | `USAGE ON *.*`; `SELECT, INSERT ON defaultdb.*`; `UPDATE` on `clients`, `engagements`, `discovery_questions`, `discovery_sessions`, `discovery_answers`, `discovery_observations`; **no DELETE**. Identical to Phase 205/207, and identical to the grants reproduced in the concurrency run |
| Collation verifier | `verified_safe_no_remediation_required`, exit 0. Head matches; 249/249 governed columns deterministic; 11/11 idempotency boundaries safe; no schema mutation, data write or migration. One warning, expected before cutover: the seven artifact tables are absent |
| Render Auto-Deploy | **Pending.** No Render CLI or API credential exists in this environment, so it cannot be checked programmatically. The operator must confirm it is Off at the dashboard before the deploy step. It was last confirmed Off in Phase 207 |

Unauthenticated probes, GET only:
- `GET /healthz` returns 200.
- `GET /release-packages/x` and `GET /engagements/x/final-report/packages` both return **404**, so
  the Phase 213 routes are not live.
- `/login` on the web returns 200.

**Grant sufficiency.** No grant change is needed:
- the schema-wide `SELECT, INSERT` covers all seven new tables once they exist;
- the artifact tables are append-only by design, so the absence of `UPDATE`/`DELETE` on them is
  intended and gives the fourth immutability layer;
- `UPDATE ON engagements`, held since Phase 203, satisfies MySQL's privilege requirement for
  `SELECT … FOR UPDATE`.

The grant point is now proven on MySQL with identical grants, not just argued.

## Production migration (approved, applied 2026-10-15)

`alembic upgrade 019_artifact_approval_release` was run with the production migration credential
in a subshell, with `PEAK_ALEMBIC_TARGET=production`, `PEAK_PRODUCTION_MIGRATION_CONFIRM=1` and
`PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`. Before the run, `alembic current` returned
`017_discovery_workflow`. Alembic ran `017 → 018_artifact_versions → 019_artifact_approval_release`,
exited 0, and `alembic current` then returned `019_artifact_approval_release (head)`.

Read-only check afterwards:

| Property | After |
|---|---|
| Alembic head | `019_artifact_approval_release`, single row |
| Base tables | **31**, including `alembic_version` (24 + 7) |
| New tables | `artifacts`, `artifact_versions`, `artifact_release_packages`, `artifact_renditions`, `artifact_approvals`, `artifact_final_approver_designations`, `artifact_releases` — **all 0 rows** |
| Existing rows | unchanged: `engagements` 1, `discovery_questions` 29; `clients`, `consultants` and discovery sessions/answers/observations 0 |
| Runtime grants | unchanged, byte-identical `SHOW GRANTS` to the pre-cutover read |

No data was seeded, no grant was changed and no existing row was modified.

**Verifier.**
- `EXPECTED_ALEMBIC_HEAD` in `tools/production_mysql_collation_verify.py` moved to
  `019_artifact_approval_release`. The move happened only after the migration was applied, under the
  Phase 58 rule.
- The stale "expected at 014_engagement_classification" footer and docstring now name the pinned
  head.
- Validation semantics are unchanged.
- The run against production returned `verified_safe_no_remediation_required`, exit 0:
  - head matches;
  - 31 base tables, with no missing or extra tables;
  - **341/341** governed columns deterministic (249 before; the new tables add 92);
  - 11/11 idempotency boundaries safe;
  - no warnings.

## Cutover sequence (approved)

1. **Migrate production** `017 → 018 → 019` with the production migration credential
   (`PEAK_ALEMBIC_TARGET=production`, `PEAK_PRODUCTION_MIGRATION_CONFIRM=1`): `alembic upgrade head`.
2. **Verify the schema and head.**
   - `alembic current` returns `019_artifact_approval_release`, single head.
   - The seven artifact tables are present (31 base tables).
   - Row counts are unchanged and the runtime grants are unchanged.
   - Move the verifier pin `EXPECTED_ALEMBIC_HEAD` in `tools/production_mysql_collation_verify.py`
     to `019_artifact_approval_release`. Under the Phase 58 rule it moves only after the migration
     has genuinely been applied.
   - Run the verifier against production: head matches, governed columns deterministic, no missing
     or extra tables.
3. **Deploy the Render API** by hand from the dashboard at the current baseline. Auto-Deploy stays
   **Off**.
4. **Deploy the Vercel web** by hand (`vercel --prod` from `web/`) at the current baseline.
5. **Run unauthenticated checks.**
   - `/healthz` returns 200.
   - `/release-packages/x`, `/release-packages/x/web` and `/engagements/x/final-report/packages`
     move from **404 to 401**.
   - `/auth/me` returns 401, and a wrong-password login returns 401, not 500.
   - Signed out, the web's protected routes redirect 307 to `/login`.
6. **Authenticated acceptance stays pending** until `admin@peakinventorysolutions.com` is
   provisioned. No temporary Admin may be created. No artifact, package, approval or release data is
   seeded.

**Rollback.**
- Redeploy the previous Render commit and the previous Vercel deployment.
- `alembic downgrade 017_discovery_workflow` drops only the seven empty artifact tables.
- There is no grant to revoke and no row to remove.

## Render deploy (manual)

- **Auto-Deploy** was confirmed **Off** by the operator at the Render dashboard before the deploy,
  and was not changed.
- **Deploy:** a manual deploy of `peak-consultant-api` at commit `230a12a` succeeded and is live.

Logged-out API checks against https://peak-consultant-api.onrender.com:

| Request | Before deploy | After deploy |
|---|---|---|
| `GET /healthz` | 200 | 200 `{"status":"ok"}` |
| `GET /auth/me`, `GET /clients` | 401 | 401 `not_authenticated` |
| `GET /release-packages/x` | **404** | **401** |
| `GET /release-packages/x/web`, `/docx` | — | 401 |
| `GET /engagements/x/final-report/packages` | **404** | **401** |
| `GET /engagements/x/final-report/released` | — | 401 |
| `POST /release-packages/x/release` | — | 401 |
| Forged `peak_session` cookie on `/release-packages/x` | — | 401 |
| Wrong-password login | 401 | 401 `invalid_credentials`, not 500 |
| `/docs`, `/openapi.json` | 404 | 404 |

What the results show:
- **The new code is live:** the Phase 213 routes moving from 404 to 401 shows they now exist and
  are protected.
- **The schema is readable:** the wrong-password 401 shows the API reads the migrated database
  without errors.
- **The checks were taken after the migration too:** between the migration and the deploy, the
  Phase 207 code still served `/healthz` 200 and a wrong-password login 401 on the migrated
  schema.

## Vercel deploy (manual)

- **How:** `vercel --prod` from `web/`, against the already-linked `peak-web` project, at `230a12a`.
  No environment variable was changed, and GitHub was not reconnected.
- **Result:** deployment `dpl_DX4gdjJ3TGXgrhLA7wmuLJavgpJw`, target `production`, **Ready**,
  aliased to **https://peak-web-five.vercel.app**.

Logged-out web checks:

| Path | Result |
|---|---|
| `/login` | 200, HSTS `max-age=63072000; includeSubDomains; preload`; no package, approval or report content in the page |
| `/`, `/dashboard`, `/engagements`, `/engagements/x`, `/clients`, `/engagements/x/assessment` | 307 → `/login` |
| `/engagements/x/final-report` (Final Report and the release review panel) | 307 → `/login`, also with a forged cookie |
| `/release-packages/x/web`, `/release-packages/x/docx` (stored renditions) | 307 → `/login`, also with a forged cookie |
| `/release-packages/x` | 404: no page exists at that path, and nothing is served |

**How the rendition routes are protected.** They are not in the web proxy's optimistic cookie
matcher. They are protected one layer down: each route handler calls the API and redirects to
`/login` on its 401, so the API's authentication is what guards them, as with every other route.
No artifact content is reachable without authentication.

## Validation

- `tests/validate_phase214_mysql_artifact_concurrency.py` against MySQL 8.2.0: **PASS**, 43 checks,
  0 failures. The negative control fails as it should.
- `tests/validate_phase213_artifact_approval_release.py`: **PASS**, 127 checks, 0 failures.
- `alembic heads` / `history`: single head `019_artifact_approval_release`, chain `017 → 018 → 019`.
- `make PYTHON=.venv/bin/python validate`: run because the Makefile gained a target, and run again
  after the verifier pin moved. **PASS** both times, exit 0, 0 failures. The new target is not part
  of the suite.

## Notes

- **Server version.** The concurrency run used MySQL 8.2.0, and production runs 8.4.8. Both use
  InnoDB under `REPEATABLE-READ`. The behaviour relied on is the same across 8.x: exclusive
  record locks from `SELECT … FOR UPDATE`, and a read view created at a transaction's first
  consistent read. No 8.4 build was available locally.
- **Stale verifier footer.** The verifier's closing text said production was "expected at
  014_engagement_classification". This was wording only, and it now names the pinned head.

## Open items

- **Render Auto-Deploy** remains **Off**; API deploys stay manual.

- **Authenticated production acceptance** is pending provisioning of
  `admin@peakinventorysolutions.com`. This is the Phase 203 item, carried forward; no temporary
  Admin may be created.
- **The Phase 213 concurrency prerequisite is closed** by this phase.
