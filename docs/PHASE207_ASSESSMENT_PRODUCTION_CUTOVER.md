# Phase 207 — Assessment production cutover

Phase 206 built the discovery-to-assessment integration and pushed it with `[skip render]`, so
production kept running Phase 205 code. Phase 207 is the deploy that brings it live. Baseline
`a29e1e0` — *Add Phase 206 discovery assessment integration*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: the Phase 206 assessment is live in production. No schema, grant or data change was made.
The production Admin account and authenticated live acceptance remain pending provisioning of
`admin@peakinventorysolutions.com` — the open Phase 203 item, carried forward unchanged.**

## Scope

Deployment only. No product work, **no migration, no grant change and no production data write.**
Phase 206 added no migration 018 and no table, so this cutover has no database step at all: unlike
Phase 205 it is a code deploy on both tiers and nothing else. The production verifier pin stays at
`017_discovery_workflow` — the rule since Phase 58 is that the pin moves only when a migration is
genuinely applied, and none was.

Render Auto-Deploy remains **Off**, confirmed by the operator before the deploy. API deploys stay
manual from the Render dashboard; re-enabling Auto-Deploy is still a separate approved decision.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at `a29e1e0` |
| Production Alembic head | `017_discovery_workflow`, single head — unchanged |
| Migration 018 | absent in the repository and in production |
| Render Auto-Deploy | **Off**, confirmed at the dashboard before the deploy |
| `GET /engagements/x/assessment` | **404** — Phase 206 routing not yet live |
| `GET /questions`, `/auth/me` | 401 — Phase 205 code live as expected |

## Validation

Only the three checks this phase authorized, all from the baseline tree:

- `tests/validate_phase206_discovery_assessment_integration.py` — **PASS**, 0 failures.
- `npm run build` from `web/` — clean; `/engagements/[id]/assessment` present in the route table.
- `npm run lint` from `web/` — clean.

No further suite was run, because none of the three failed.

One operational note, not a code defect: `make` defaults to `PYTHON ?= python3`, which on this
machine resolves to a Homebrew interpreter without the project dependencies, so
`make validate-phase206` fails at the harness's Alembic subprocess. Run it as
`make PYTHON=.venv/bin/python validate-phase206`. The harness itself is unchanged and passes.

## Render deploy (manual)

Deployed by hand from the Render dashboard (Manual Deploy → Deploy latest commit, `a29e1e0`).
Auto-Deploy was left **Off**.

| Check | Before deploy | After deploy |
|---|---|---|
| `GET /healthz` | 200 `{"status":"ok"}` | 200 `{"status":"ok"}` |
| `GET /engagements/x/assessment` | **404** (route did not exist) | **401** `{"detail":"not_authenticated"}` |
| `GET /questions`, `/auth/me`, `/clients`, `/consultants` | 401 | 401 |
| `/docs`, `/openapi.json` | 404 | 404 |
| Forged `peak_session` cookie on the assessment path | — | 401 |
| Wrong-password login | — | 401 `invalid_credentials`, not 500 |

The assessment path's move from **404 to 401** is the routing-layer evidence that Phase 206 code is
live: the route exists and is protected. The wrong-password 401 shows the API still reads the
production database through the models without unknown-column errors, so nothing in the Phase 206
reader broke startup or query paths. No migration ran at startup — the head was still
`017_discovery_workflow` afterwards.

No authenticated request was made, so the discovery reader and the assessment projection have not
executed against production data. That is the pending-acceptance item below, not a deploy result.

## Vercel deploy

Deployed manually with the CLI from `web/` against the already-linked `peak-web` project
(`vercel --prod`). GitHub was **not** reconnected; the frontend still does not deploy on push.

- Deployment `READY`, target `production`, aliased to **https://peak-web-five.vercel.app**.
- `/login` returns 200 with HSTS (`max-age=63072000; includeSubDomains; preload`).
- Signed out, `/engagements/x/assessment` returns **307 to `/login`** — the new route is present and
  protected. `/dashboard`, `/engagements` and `/questions` redirect the same way.

## Production check (read-only)

Taken before and after both deploys with the read-only credential. The two snapshots are identical:

| Property | Value |
|---|---|
| Alembic head | `017_discovery_workflow`, single head |
| Migration 018 | none |
| Base tables | 24 |
| `discovery_questions` | 29 (Phase 205 configuration) |
| `discovery_sessions` / `_answers` / `_observations` | **0 / 0 / 0** |
| `clients` / `consultants` | 0 / 0 |
| `engagements` | 1 (Phase 59 internal-test anchor) |
| Runtime grants | `SELECT, INSERT ON defaultdb.*`; `UPDATE` on `clients`, `engagements` and the four discovery tables; **no DELETE** — byte-identical to Phase 205 |

`tools/production_mysql_collation_verify.py` green against production: 24 base tables, head matches,
249/249 governed columns deterministic, 11/11 idempotency boundaries safe,
`schema_mutation_made: False`, `data_write_made: False`, `migration_executed: False`.

**No discovery session, answer, observation, client or engagement row was created.**

## Open item carried forward: production Admin acceptance

**Unchanged from Phase 203 and still open.** Production Admin acceptance is pending provisioning of
`admin@peakinventorysolutions.com`, and **no temporary Admin may be created in its place.**

Authenticated production acceptance of Phase 204/205 discovery **and** of the Phase 206 assessment
is blocked on the same mailbox. The assessment endpoint and page are now live and correctly refuse
unauthenticated callers, but no one has yet signed in to exercise them, so the derived document has
never been produced against production data.

## Final production state

| Property | Value |
|---|---|
| Alembic head | `017_discovery_workflow`, single head — **unchanged by this phase** |
| Runtime grants | unchanged from Phase 205 |
| Application rows | unchanged: 1 `engagements` anchor, 29 `discovery_questions`, everything else 0 |
| Render Auto-Deploy | **Off** |
| API | https://peak-consultant-api.onrender.com — healthy, Phase 206 code live |
| Frontend | https://peak-web-five.vercel.app — healthy, assessment route live |

## Accepted risks

Carried from Phase 205 unchanged — the read-only verifier user's admin grants, the runtime's
schema-wide `INSERT`, the unrestricted Aiven IP surface and unverified server certificate, the
publicly reachable API with an in-memory per-email login limiter, and the standing trade that a
manual-deploy service can be left behind the repository. This phase added no new risk: it changed no
schema, no grant and no data.

**Rollback:** redeploy the previous Render commit by hand and roll back to the previous Vercel
deployment. There is nothing else to undo — no migration to downgrade, no grant to revoke and no row
to remove.
