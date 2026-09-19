# Phase 203 — First live deployment

The consultant application runs live: Next.js on Vercel, the FastAPI consultant API on Render, and
the existing managed production MySQL (Aiven, schema `defaultdb`). Baseline `9db696f`.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: infrastructure live and healthy. The production Admin account and authenticated live
acceptance are pending provisioning of `admin@peakinventorysolutions.com`.**

## Live URLs

| Component | URL |
|---|---|
| Frontend (Vercel project `peak-web`, root `web/`) | https://peak-web-five.vercel.app |
| Consultant API (Render service `peak-consultant-api`) | https://peak-consultant-api.onrender.com |

The browser talks only to the Vercel frontend. Next.js server code calls the API at
`PEAK_API_BASE_URL` (a server-only Vercel variable, never `NEXT_PUBLIC_`), forwarding the HttpOnly
`peak_session` cookie (Secure, `SameSite=Lax`, 8 hours). There is no CORS. The API has no
docs/OpenAPI routes.

## Code and configuration (commits)

- `5651164` *Prepare Phase 203 deployment*:
  - `GET /healthz`: liveness only, with no database, configuration or secrets.
  - Per-email login rate limiting: 5 failures in 15 minutes gives a 429 even with the right
    password; a success clears the count. It is in memory, per process, and not per IP (behind
    Next.js every browser shares one upstream address, and forwarding headers can be forged).
  - `tools/bootstrap_admin.py --production`.
  - `render.yaml`, which holds no values (the repository is public).
- `2e81a2b` *Allow explicitly confirmed production default schema*: the Phase 84 guard refused
  `defaultdb` for production, but production genuinely lives there (014 was applied there in
  Phase 58). Production may now use `defaultdb` only when
  `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb` names that exact schema. Every other production check
  still applies, the MySQL system schemas stay refused, and the lab branch is unchanged.
- `ced9cb6` *Update production verifier for Phase 203 schema*: the verifier's live-production head
  moves to 016, its table expectation is derived from the models (with the 014-era tables as a
  required subset), and harnesses assert "014 or a later head" instead of one literal.

**Render** (`render.yaml`, Blueprint, starter plan, virginia, Python 3.12.8):
`pip install -r requirements-web.txt`, then
`uvicorn --factory peak.consultant_api.app:create_app --host 0.0.0.0 --port $PORT`, with health
check `/healthz`. `PEAK_RUNTIME_DATABASE_URL` was entered in the Render dashboard by the operator;
Render generated `PEAK_WEB_SECRET_KEY`. No migration runs at startup.
**Vercel:** project `peak-web`, deployed with the CLI from `web/` (not git-connected, so a push does
not deploy the frontend). Its only variable is `PEAK_API_BASE_URL`.

## Production database

- **Migrations:** `015_consultants` and `016_client_engagement_workspace_fields` were applied with
  the migration credential through the guard (`PEAK_ALEMBIC_TARGET=production`,
  `PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`). Verified
  read-only afterwards:
  - a single head, `016_client_engagement_workspace_fields`;
  - 20 tables (19 application tables plus `alembic_version`), with no views, routines, triggers or
    events;
  - `consultants` with its PK, unique email and role CHECK;
  - all Phase 202 columns plus `ix_engagements_assigned_consultant_id`;
  - **0 consultant rows**, and no client or engagement rows created;
  - the production collation verifier reports 217 of 217 governed columns deterministic.
- **Runtime grants (`peak_prod_runtime`):** `SELECT, INSERT ON defaultdb.*`, plus `UPDATE` on
  `defaultdb.clients` and `defaultdb.engagements` only. The two table-level UPDATE grants are the
  whole Phase 203 change, applied with the migration credential. There is no DELETE, no other
  UPDATE, and no schema or grant rights.

## Live verification (no Admin yet)

- **API:** `/healthz` returns 200. `/auth/me`, `/consultants` and `/clients` return 401 when
  signed out. `/docs` and `/openapi.json` return 404. A wrong-password login returns 401 rather
  than 500, which shows the API reads the production database.
- **Frontend:**
  - `/login` returns 200 with HSTS.
  - `/`, `/dashboard`, `/clients`, `/clients/new`, `/engagements` and `/consultants` redirect to
    `/login` when signed out.
  - A forged session cookie is rejected by the API and redirected, which shows Vercel reaches
    Render.
  - The real sign-in form rejects an unknown account and sets no cookie.
  - No browser JavaScript chunk or page contains the API address, any `PEAK_*` name, or database
    identifiers.

## Pending: production Admin and authenticated acceptance

The Admin is `admin@peakinventorysolutions.com` (name Steve Rouse), bootstrapped only after that
mailbox is provisioned. The operator runs it in their own terminal. The password is typed at a
no-echo prompt and is never shared in chat or logged:

```bash
cd ~/projects/peak
set -a; . ~/.peak/peak-prod-runtime.env; set +a
PEAK_PRODUCTION_ADMIN_BOOTSTRAP_CONFIRM=1 .venv/bin/python tools/bootstrap_admin.py \
    --production --email admin@peakinventorysolutions.com            # dry run
PEAK_PRODUCTION_ADMIN_BOOTSTRAP_CONFIRM=1 .venv/bin/python tools/bootstrap_admin.py \
    --production --email admin@peakinventorysolutions.com --execute  # prompts twice, no echo
```

Then sign in, check the Dashboard and Consultants, sign out, and sign back in. **Live
client/engagement create/edit acceptance is deliberately skipped:** workspace clients have no
internal-test classification, so a test client would be indistinguishable from a real one. It
needs that classification path first.

## Accepted risks (pre-existing unless noted)

- The production "read-only verifier" user `peak_prod_verify_ro` holds full admin grants. It is
  read-only only by tool code.
- The runtime's schema-wide INSERT also covers `alembic_version` and the two prohibited tables.
  Per-table narrowing is a separate change.
- The Aiven service accepts connections from any IP (`0.0.0.0/0`). The connection is encrypted and
  password-protected, but the server certificate is not verified (the driver default).
- **New:** the API is publicly reachable. The login limiter is per email and resets when the
  process restarts, so a known email can be locked out for 15 minutes.
- Render auto-deploys the API on pushes to `main`.

**Rollback:**
- Migrations: downgrade 016 then 015 with the migration credential. This loses any data in the new
  columns.
- Grants: `REVOKE UPDATE` on the two tables.
- Providers: suspend or delete the Render service or the Vercel project.
