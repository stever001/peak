# Phase 201 — Consultant web shell and authentication

First consultant-facing web application surface: email/password sign-in, Admin and Consultant
roles, Admin-only consultant accounts, and a responsive authenticated shell. Baseline `d430d4f`.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

## Phase numbering

Phase 201 starts the **200 series: consultant-facing web application** phases. The 100 series
continues for backend/core/internal-workflow work. Historical phases are not renumbered.

## Stack

| Layer | Choice | Location |
|---|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, npm | `web/` |
| Design tokens | CSS custom properties exposed as Tailwind theme utilities | `web/app/tokens.css`, `web/app/globals.css` |
| HTTP adapter | FastAPI — **thin transport only** | `peak/consultant_api/app.py` |
| Accounts | Account functions + signed session tokens | `peak/accounts/` |
| Schema | `consultants` table, migration `015_consultants` | `peak/db/models.py`, `alembic/versions/015_consultants.py` |
| Bootstrap | Initial Admin CLI | `tools/bootstrap_admin.py` |
| Python deps | `fastapi`, `uvicorn`, `argon2-cffi`, `itsdangerous`, `httpx` (test client) | `requirements-web.txt` |

No component library, state-management package, or UI framework was added.

**Design tokens.** `tokens.css` holds the brand palette (`--peak-yale-blue`, `--peak-baltic-blue`,
`--peak-sky-aqua`, `--peak-mustard`, `--peak-deep-saffron`), neutrals, and **semantic roles**
(`--peak-color-brand`, `-accent`, `-highlight`, `-attention`, `-canvas`, `-surface`, `-line`,
`-ink`, …) plus radius, touch-target and sidebar sizes. `globals.css` maps the semantic roles into
Tailwind (`bg-brand`, `text-ink`, `border-line`, `min-h-touch`, `rounded-peak`, …). Components use
only those utilities, never raw hex, so a site-wide change is a one-file edit.

**FastAPI is transport only.** It validates input, calls `peak.accounts`, returns minimal JSON,
and enforces the Admin role. No business logic lives there. Endpoints: `POST /auth/login`,
`POST /auth/logout`, `GET /auth/me`, `GET /consultants`, `POST /consultants`. OpenAPI/docs routes
are disabled. The package is named `consultant_api` because it is consultant-facing: there is no
client login and no client-facing read path (the Phase 55 guard on `peak/api*` still holds).

## Consultants table (migration 015)

`id` (`cons_<hex>`), `name`, `email` (normalized: trimmed + lower-cased, **unique**),
`password_hash` (Argon2id), `role` (`admin` | `consultant`, CHECK constraint), `created_at`.
`id`, `email`, `password_hash` and `role` are governed (`utf8mb4_bin` on MySQL); the collation
audit classifies `name` as ordinary text, `email` as a governed identifier and `role` as a governed
scope. It is **not a governed engagement record**: no governance/audit mixins (Phase 11 lists it in
`NON_GOVERNED_TABLES`), no client relation, no assignment ACL, no profile fields. Additive, no data.

Account writes are one `INSERT` per consultant and every read is a `SELECT`, so the runtime
credential's existing `SELECT` + `INSERT` grant is sufficient.

## Authentication

- Passwords hashed with **Argon2id** (`argon2-cffi` defaults); minimum 12 characters. No
  plaintext is stored, returned, or logged. Unknown emails are verified against a dummy hash so
  both failure paths cost the same.
- Session: an **`itsdangerous` signed, timestamped token** carrying only the consultant id, signed
  with `PEAK_WEB_SECRET_KEY` (≥ 32 chars, environment only, never printed) and valid **8 hours**.
  Cookie `peak_session`: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age=28800`, `Secure` by
  default. `PEAK_WEB_INSECURE_COOKIE=1` drops `Secure` for local plain-HTTP development only.
- Role and existence are **re-read from the database on every request**; the token never grants
  a role by itself.
- Stateless: sign-out clears the cookie; a copied token remains valid until expiry. There is no
  refresh token, recovery, OAuth, SSO, MFA, or passwordless flow.

**Frontend/API connection.** The browser talks only to Next.js. Server Actions (sign-in, sign-out,
add consultant) and server components call FastAPI at `PEAK_API_BASE_URL` (server-only; not a
`NEXT_PUBLIC_` variable), forwarding the `peak_session` cookie. On sign-in Next.js sets the same
signed token as its own HttpOnly cookie, so no token reaches browser JavaScript and no CORS is
needed. `web/proxy.ts` only redirects cookie-less requests to `/login` (optimistic); every page
verifies the session through `GET /auth/me`, and the Consultants page relies on the API's 403.

## Access model

- No client login and no self-registration. An Admin creates every account.
- `admin`: everything a consultant can do, plus consultant-account administration.
- `consultant`: every workspace area. All consultants will be able to view and edit all clients
  and engagements; assignment will be metadata, not an authorization boundary.
- No granular RBAC.

## Admin bootstrap

`tools/bootstrap_admin.py --email <email> [--name "Steve Rouse"] [--execute]` creates the initial
Admin. It is a dry run unless `--execute` is passed; it prompts for the password twice without echo,
never prints the password or hash, has no hard-coded credential, and **refuses if any Admin already
exists**. It uses the normal runtime session and accepts only local SQLite or the `peak_lab`
schema — any other MySQL schema is refused before connecting. **No production consultant-account
write is authorized.**

## Consultant management (Admin only)

The Consultants page lists name, email and role, and an Add Consultant form takes name, email, role,
initial password and confirmation. The new consultant can sign in immediately. Non-Admins don't
see the navigation item, and the API returns 403 for both endpoints. There is no edit, deactivate,
reset, delete, invitation, or email sending.

## Responsive shell

Priority: iPad/tablet → desktop → phone. From `md` (768 px, iPad portrait) up, a persistent brand
sidebar shows the navigation, the signed-in name, a role badge and Sign out. Below `md`, there's a
compact top bar (name, Sign out) and a fixed bottom tab bar. Every touch target is at least 48 px,
inputs use 16 px text (no iOS zoom), there are no dense tables, and nothing scrolls horizontally at
360–390 px. Navigation: Dashboard, Clients, Engagements, and Consultants (Admin only). Clients and
Engagements are placeholders.

## Local run

```bash
python3 -m pip install -r requirements-web.txt
# Runtime DB: set PEAK_RUNTIME_DATABASE_URL to a local SQLite file (migrate it with alembic
# upgrade head using PEAK_DATABASE_URL) or to peak_lab once 015 is applied there.
# Set PEAK_WEB_SECRET_KEY (python3 -c 'import secrets; print(secrets.token_urlsafe(48))').
python3 tools/bootstrap_admin.py --email <admin email> --execute
PEAK_WEB_INSECURE_COOKIE=1 uvicorn --factory peak.consultant_api.app:create_app --port 8000
cd web && npm install && PEAK_WEB_INSECURE_COOKIE=1 npm run dev   # PEAK_API_BASE_URL defaults to 127.0.0.1:8000
```

## Validation

- `tests/validate_phase201_consultant_web_auth.py` (`make validate-phase201`), offline on temporary
  SQLite: migration 015 upgrades and downgrades; unauthenticated and forged-session requests get
  401; login normalizes email and sets the cookie flags; Admin can list and create (duplicate
  email 409, short password 422); a created consultant can sign in and gets 403 on consultant
  administration; `/auth/me` returns the shell identity; logout clears the session; the bootstrap
  tool refuses non-lab MySQL and a second Admin, and never prints secrets.
- `npm run build` and `npm run lint` in `web/`.
- A local end-to-end smoke run (uvicorn + `next start` on throwaway SQLite): cookie-less and
  forged-cookie redirects to `/login`, Server Action sign-in / add consultant / sign-out, and
  the Consultant redirect away from `/consultants`, checked visually at 390, 820, 1180 and 1440 px.

## Posture

Local and lab only. Migration 015 is **not applied to `peak_lab` or production**. Applying it to
`peak_lab` needs an explicit Phase 84-guarded migration decision. No production migration,
consultant account, write enablement, or deployment. `peak_lab_scenario` untouched. Production
deployment topology is deferred.

## Next: Phase 202

Client and Engagement CRUD in the workspace (multiple engagements per client), open to every
consultant, with assignment as metadata. Decisions it needs first: `clients` and `engagements` are
governed records written only through create-only controlled writers, and the runtime credential
holds `SELECT` + `INSERT` only, so **edit** requires an approved `UPDATE` path (writer, allowlist,
grant).
