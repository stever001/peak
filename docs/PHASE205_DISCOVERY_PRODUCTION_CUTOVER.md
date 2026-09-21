# Phase 205 — Discovery production cutover

Phase 204 built the discovery / interview workflow and migration `017_discovery_workflow` but
touched no managed database: it was pushed with `[skip render]` and production kept running
pre-Phase-204 code at head `016_client_engagement_workspace_fields`. Phase 205 is the cutover that
brings it live. Baseline `1a54c14` — *Add Phase 204 discovery interview workflow*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: Discovery is live in production. The production Admin account and authenticated live
acceptance remain pending provisioning of `admin@peakinventorysolutions.com` — the open Phase 203
item, carried forward unchanged.**

## Deployment safety: Render Auto-Deploy is OFF

Phase 203 left Render auto-deploying `peak-consultant-api` on every push to `main`, so a commit was
kept out of production only by writing `[skip render]` in its message. That is a convention, not a
control: one forgotten tag ships unreviewed code to a live service.

**Auto-Deploy is now disabled** on the Render service (Settings → Build & Deploy → Auto-Deploy →
Off), confirmed by the operator before any Phase 205 write. API deploys are **manual from the Render
dashboard from here on**, and `[skip render]` is no longer load-bearing. `render.yaml` is unchanged:
the setting lives in the dashboard, not the Blueprint.

**Future API deploys remain manual until a later phase explicitly decides otherwise.** Re-enabling
Auto-Deploy is a deliberate decision with its own approval, not a cleanup step.

## Production preflight (read-only, before any write)

Verified with the read-only credential, inspecting no client content:

| Check | Result |
|---|---|
| Alembic head | `016_client_engagement_workspace_fields`, single head |
| Migration 017 | pending |
| `discovery_questions` / `_sessions` / `_answers` / `_observations` | all absent |
| `engagements.north_star`, `north_star_context` | absent |
| Base tables | 20; 0 views, routines, triggers, events |
| Runtime grants | `SELECT, INSERT ON defaultdb.*`; `UPDATE` on `clients` and `engagements` — the Phase 203 state exactly |
| `consultants` rows | **0** — the Admin was not separately provisioned |
| `clients` rows | 0 |
| `engagements` rows | 1 — the Phase 59 internal-test anchor, pre-existing |
| Discovery rows | none (the tables did not exist) |

## Migration 017 review

Reviewed as source and rehearsed on a throwaway SQLite database (016 → 017) before production:

- **Additive only.** Four `create_table`, two `add_column`, 25 `create_index`. No drop, no alter of
  an existing column, no data rewrite.
- Adds `engagements.north_star` and `north_star_context`, both nullable `TEXT`.
- Creates `discovery_questions`, `discovery_sessions`, `discovery_answers`,
  `discovery_observations`.
- Indexes and constraints are exactly the reviewed set: `ix_discovery_questions_category`, the
  governed/identity indexes on the three governed tables, `uq_discovery_questions_seed_key`,
  `uq_discovery_answers_session_question`, and five `CHECK` constraints (answer type, branch
  operator, session status, observation effort, observation value).
- **Inserts nothing.** The migration contains no `op.bulk_insert` and no `op.execute`. The question
  pool is a separate, explicitly confirmed step — see below. The local rehearsal ended with all four
  tables at 0 rows.

## Applying migration 017

Applied with the migration credential through the Phase 84 guard, with every production
confirmation preserved:

```bash
set -a; . ~/.peak/peak-prod-migrate.env; set +a
PEAK_ALEMBIC_TARGET=production \
PEAK_PRODUCTION_MIGRATION_CONFIRM=1 \
PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb \
  .venv/bin/alembic upgrade 017_discovery_workflow
```

Verified read-only afterwards:

- a single head, **`017_discovery_workflow`**;
- `engagements.north_star` and `north_star_context` present, `text`, nullable;
- all four discovery tables present;
- **24 base tables** (23 application tables plus `alembic_version`), up from 20; still 0 views,
  routines, triggers and events;
- the 25 expected indexes, both unique constraints and all five `CHECK` constraints present, and no
  unexpected schema object;
- **0 rows in every discovery table** — the migration inserted nothing.

## Runtime grants

The runtime service (`peak/workspace/discovery.py`) reaches the four discovery tables through
`session.add(...)` and `update(...)` only. There is no `delete` call site, no delete action in
`WORKSPACE_WRITE_COLUMNS`, and no DELETE route in the consultant API. So each discovery table needs
`SELECT`, `INSERT` and `UPDATE`, and nothing more.

`SELECT` and `INSERT` were already covered by the schema-wide grant, so the whole Phase 205 change
is **four table-level `UPDATE` grants**:

```sql
GRANT UPDATE ON `defaultdb`.`discovery_questions`     TO `peak_prod_runtime`@`%`;
GRANT UPDATE ON `defaultdb`.`discovery_sessions`      TO `peak_prod_runtime`@`%`;
GRANT UPDATE ON `defaultdb`.`discovery_answers`       TO `peak_prod_runtime`@`%`;
GRANT UPDATE ON `defaultdb`.`discovery_observations`  TO `peak_prod_runtime`@`%`;
```

**`engagements.north_star` / `north_star_context` needed no new grant.** MySQL `UPDATE` is a
table-level privilege here, and the existing `UPDATE ON defaultdb.engagements` from Phase 203
already covers the new columns. This was confirmed against the live grants rather than assumed.

No `DELETE`, no `ALTER`, no `CREATE`, no `DROP`, no `GRANT OPTION`, no schema-wide broadening, and no
UPDATE on any unrelated table. Verified with `SHOW GRANTS`, the Phase 203 grants on `clients` and
`engagements` unchanged:

```
GRANT USAGE ON *.* TO "peak_prod_runtime"@"%"
GRANT SELECT, INSERT ON "defaultdb".* TO "peak_prod_runtime"@"%"
GRANT UPDATE ON "defaultdb"."clients" TO "peak_prod_runtime"@"%"
GRANT UPDATE ON "defaultdb"."discovery_answers" TO "peak_prod_runtime"@"%"
GRANT UPDATE ON "defaultdb"."discovery_observations" TO "peak_prod_runtime"@"%"
GRANT UPDATE ON "defaultdb"."discovery_questions" TO "peak_prod_runtime"@"%"
GRANT UPDATE ON "defaultdb"."discovery_sessions" TO "peak_prod_runtime"@"%"
GRANT UPDATE ON "defaultdb"."engagements" TO "peak_prod_runtime"@"%"
```

## Initializing the question pool

The pool is application configuration, not client data, and it is created **only** by the explicit,
idempotent `tools/init_discovery_questions.py` — never by a migration and never at application
startup. Production requires `--production`, `PEAK_PRODUCTION_DISCOVERY_INIT_CONFIRM=1` and a
production-marked runtime URL. Phase 204 wrote the tool but did not authorize the production run;
Phase 205 authorizes it and ran it once.

```bash
set -a; . ~/.peak/peak-prod-runtime.env; set +a
PEAK_PRODUCTION_DISCOVERY_INIT_CONFIRM=1 \
  .venv/bin/python tools/init_discovery_questions.py --production             # dry run
PEAK_PRODUCTION_DISCOVERY_INIT_CONFIRM=1 \
  .venv/bin/python tools/init_discovery_questions.py --production --execute
```

The dry run reported `would create 29 question(s); 0 already present` — exactly the intended
inserts, and nothing else — before anything was written. The execute run reported
`created 29 question(s); 0 already present (left unchanged)`.

Verified read-only afterwards:

| Check | Result |
|---|---|
| `discovery_questions` rows | **29** |
| Distinct `seed_key` values | 29, none null — every seed key unique |
| Categories | 10 |
| Branch follow-up questions | 7 |
| Active | all 29 |
| Answer types | 17 `long_text`, 7 `yes_no`, 3 `short_text`, 2 `single_choice` |
| `discovery_sessions` / `_answers` / `_observations` | **0 / 0 / 0** |
| `clients` rows | 0 |

**No sample client, engagement, interview, answer or observation was created.** Re-running the tool
skips every existing seed key, so a question a consultant later edits or deactivates is never
re-imposed.

## Production verifier

`tools/production_mysql_collation_verify.py` pinned the expected **live** production head at 016.
Phase 205 moves that pin to `017_discovery_workflow` — after the migration was genuinely applied,
which is the rule the pin has followed since Phase 58. Following the Phase 121 principles, nothing
else changed: the expected table set is still derived from the declared models, the 014-era tables
are still a required subset, no table count is frozen, and the governed-column collation validation
is untouched.

Run against production, read-only:

```
[ok] verified_safe_no_remediation_required
  base tables found     : 24 (expected 23 + alembic_version)
  alembic head matches  : True
  governed columns      : 249 checked, 249 deterministic, 0 at risk
  idempotency boundaries: 11 checked, 0 at risk
  schema_mutation_made  : False    data_write_made : False    migration_executed : False
```

249 governed columns, up from 217 in Phase 203: the new discovery governed identifiers are pinned to
the governed collation at creation, so they arrived deterministic rather than needing remediation.

Committed and pushed as `d569e77` *Update production verifier for Phase 205 [skip render]*, which
triggered no deployment — Auto-Deploy was already off.

## Render deploy (manual)

Deployed by hand from the Render dashboard (Manual Deploy → Deploy latest commit, `d569e77`) only
after the database was ready: migration applied, grants correct, pool initialized, verifier green.
Auto-Deploy was left **Off**.

| Check | Before deploy | After deploy |
|---|---|---|
| `GET /healthz` | 200 `{"status":"ok"}` | 200 `{"status":"ok"}` |
| `GET /questions` | **404** (route did not exist) | **401** — routing exists, unauthenticated rejected |
| `GET /auth/me`, `/clients`, `/consultants` | 401 | 401 |
| `/docs`, `/openapi.json` | 404 | 404 |
| Forged `peak_session` cookie on `/questions` | — | 401 |
| Wrong-password login | — | 401, not 500 |

The `/questions` move from 404 to 401 is the routing-layer evidence that Phase 204 code is live. The
wrong-password 401 shows the API reads the production database through the new models without
unknown-column errors. No migration ran at startup: the head was still `017_discovery_workflow`
afterwards, the question count still 29, and the three interview tables still empty. No secret
appears in the logs or in any response body.

## Vercel deploy

Deployed manually with the CLI from `web/` against the already-linked project (`vercel --prod`).
GitHub was **not** reconnected; the frontend still does not deploy on push.

- Build and lint clean; deployment `READY`, aliased to **https://peak-web-five.vercel.app**.
- All discovery routes built: `/questions`, `/questions/new`, `/questions/[id]/edit`,
  `/engagements/[id]/interviews/new`, `/interviews/[id]`, `/observations/[id]/edit`.
- `/login` returns 200 with HSTS (`max-age=63072000; includeSubDomains; preload`) and carries a
  viewport meta tag — no horizontal breakage on the basic smoke check.
- Server-side connectivity to Render works: a forged cookie on a protected page is rejected by the
  API and redirected, which only happens if Next.js reached Render.
- `/login` and all nine of its JavaScript chunks contain no `PEAK_*` name, no API address, no
  `defaultdb`, no database host or driver string, and no cookie name.

## Live discovery checks without an Admin

The production Admin does not exist yet and **no temporary credential was created**, so only
unauthenticated checks were possible:

- signed out, `/`, `/dashboard`, `/clients`, `/engagements`, `/consultants`, `/questions`,
  `/questions/new`, `/interviews/[id]`, `/engagements/[id]/interviews/new` and
  `/observations/[id]/edit` all 307 to `/login`;
- a forged session cookie is rejected on both the frontend and the API;
- the API's discovery endpoints reject unauthenticated access with 401 rather than 404, so the
  routes exist and are protected;
- the health check is green and the frontend reaches Render.

**No client row, engagement row, discovery session, answer or observation was created.**

## Open item carried forward: production Admin acceptance

**Unchanged from Phase 203 and still open.** Production Admin acceptance is pending provisioning of
`admin@peakinventorysolutions.com`. **Phase 203 authenticated acceptance is not complete**, and no
temporary Admin may be created in its place.

Once that mailbox exists, still required:

1. bootstrap the production Admin (`tools/bootstrap_admin.py --production`, password typed at a
   no-echo prompt, run by the operator in their own terminal);
2. sign in;
3. verify the Dashboard;
4. verify Consultants;
5. sign out;
6. sign back in;
7. record authenticated acceptance complete.

Discovery's authenticated behaviour in production — starting an interview, answering, branching,
observations, editing the pool — is unverified live for the same reason, and joins that queue.

## Final production state

| Property | Value |
|---|---|
| Alembic head | `017_discovery_workflow`, single head |
| Base tables | 24 (23 application + `alembic_version`) |
| Verifier | green — 249/249 governed columns deterministic |
| Runtime grants | `SELECT, INSERT ON defaultdb.*`; `UPDATE` on `clients`, `engagements` and the four discovery tables; **no DELETE** |
| `discovery_questions` | 29 |
| `discovery_sessions` / `_answers` / `_observations` | 0 / 0 / 0 |
| `clients` / `consultants` | 0 / 0 |
| `engagements` | 1 (Phase 59 internal-test anchor) |
| Render Auto-Deploy | **Off** |
| API | https://peak-consultant-api.onrender.com — healthy |
| Frontend | https://peak-web-five.vercel.app — healthy |

Local validation: `tests/validate_phase204_discovery_workflow.py` PASS, `make validate` PASS (81
harnesses, exit 0), `npm run build` and `npm run lint` clean. The repository contains no secret —
every DSN in tracked files is a `localhost` or `.invalid` placeholder.

## Accepted risks

Carried from Phase 203 unless noted:

- The production read-only verifier user `peak_prod_verify_ro` holds full admin grants; it is
  read-only only by tool code.
- The runtime's schema-wide `INSERT` also covers `alembic_version` and the two prohibited tables.
  Per-table narrowing is still a separate change — and the four new tables inherited that
  schema-wide `INSERT` rather than a narrow one.
- The Aiven service accepts connections from any IP; the connection is encrypted and
  password-protected, but the server certificate is not verified.
- The API is publicly reachable; the login limiter is per email, in memory, and resets on restart.
- **Changed:** Render no longer auto-deploys. The risk moves from "an untagged push ships" to "a
  deploy can be forgotten" — the repository can now run ahead of production, which is the trade
  this phase chose deliberately.

**Rollback:**

- Code: redeploy the previous Render commit by hand; redeploy the previous Vercel deployment.
- Question pool: no automated path — the runtime has no `DELETE`. Removing the 29 rows is a
  separately approved operation with the migration credential.
- Grants: `REVOKE UPDATE` on the four discovery tables.
- Migration: downgrade 017 with the migration credential. This drops the four discovery tables and
  the two North Star columns, losing anything stored in them.
