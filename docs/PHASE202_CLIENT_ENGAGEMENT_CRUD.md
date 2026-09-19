# Phase 202 — Client and engagement CRUD

The consultant web app becomes useful for day-to-day engagement setup: clients, several
engagements per client, assignment, status and current phase. Baseline `37d7912`.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

## Governance change: the consultant workspace write path

Before this phase `clients` was "never writable by any path" and `engagements` could be created
only by the Phase 54 anchor writer. Phase 202 changes that **explicitly** in
`peak/persistence/allowlist.py` instead of routing around it:

- `NEVER_WRITABLE_TABLES` became `WORKSPACE_ONLY_TABLES = {"clients"}`. `clients` is still
  unreachable by every controlled writer (generic allowlist and anchor path). Its only approved
  write path is the consultant workspace service, `peak/workspace` (placed like `peak/accounts`,
  called only by the consultant API).
- `WORKSPACE_WRITE_COLUMNS` lists the only four workspace `(table, action)` pairs and the exact
  columns each may write:

| Pair | Columns |
|---|---|
| `clients` / `create_client_profile` | `id` + client profile columns |
| `clients` / `update_client_profile` | client profile columns |
| `engagements` / `create_workspace_engagement` | `id`, `client_id` + engagement workflow columns |
| `engagements` / `update_engagement_workspace_fields` | engagement workflow columns |

- `is_allowed_workspace_write` checks every write pair-wise and column-wise, and the service
  refuses anything it rejects. `WORKSPACE_FORBIDDEN_COLUMNS` (owner, authorization scope,
  review/lifecycle state, audit columns, `details_json`, `engagement_category`,
  `real_client_data`, `client_accessible`, `capsule_publication_authorized`) is asserted disjoint
  from every workspace column set.
- There is no delete action and no generic update helper: each table has one explicit
  `UPDATE … WHERE id = ?` over its own column dict. `engagements` stays in `PROHIBITED_TABLES`,
  and the generic allowlist, anchor pair and every controlled writer are unchanged.
- **Authorization decision.** Every real-client engagement created through the workspace is born
  with `owner_id = peak_consultants` and `authorization_scope = engagement_authorized`
  (`WORKSPACE_ENGAGEMENT_CREATION_STAMP`). The service applies these fixed constants after the
  caller's columns pass the allowlist check. They are never read from the request (a caller who
  sends either field gets a 422) and never editable: both columns stay in
  `WORKSPACE_FORBIDDEN_COLUMNS`. Downstream controlled writers can then match the engagement
  exactly, and the unchanged request-vs-stored owner and scope checks still reject any mismatch.
  - `engagement_authorized` means work records belonging to an authorized real-client Peak
    engagement, usable by Peak consultants for internal engagement work. It does not itself
    authorize client-facing disclosure, methodology publication, or AgentNet publication.
  - `peak_consultants` is the organizational owner of consultant-workspace real-client
    engagements: organizational authority over the engagement. `assigned_consultant_id` is
    workflow assignment only. The creating consultant is never the owner, and every authenticated
    consultant can still work across engagements.
- Every other governance column keeps the model defaults: `review_status=draft`,
  `engagement_category=real_client`, and the `client_accessible` / `real_client_data` /
  `capsule_publication_authorized` defaults. The model's `updated_at` `onupdate` still fires on
  edits; that is the model's audit mechanism.

The 18 harnesses that asserted "clients never writable" now assert the replacement rule through
`tests/_workspace_write_path.py`: the workspace path is the only client write path, it is exactly
create + update of the profile columns, and every other path is denied.

## Fields

**Client:** company name (the existing `organization_label`), description, structured address
(`address_line1`, `address_line2`, `city`, `region`, `postal_code`, `country`), main contact
(`contact_name`, `contact_title`, `contact_email`, `contact_phone`), and `key_personnel`: a JSON
list of `{name, role, email, phone}` with name required and at most 25 people. There is
deliberately no personnel table.

**Engagement:** name (the existing `engagement_label`), client (set on create, never changed),
`objective`, `assigned_consultant_id`, `status`, `current_phase`.

**Assignment:** one consultant, referencing `consultants.id` (checked to exist). Assignment is
workflow metadata, never authorization: every authenticated consultant can view and edit every
client and engagement. No teams.

**Status vocabulary:** the stored vocabulary is unchanged. The workspace sets `active`,
`on_hold` or `closed`, shown as Active / Paused / Closed; "Paused" is the existing `on_hold`.
Existing `prospective` and `complete` values still display. New engagements default to `active`.

**Current phase:** a free-text label (≤128 characters), for example "Discovery". There are no
phase records, phase billing, deliverables or workflow.

## Migration 016

`016_client_engagement_workspace_fields`: nullable columns only — the client profile columns
above plus `engagements.objective`, `assigned_consultant_id` (governed, indexed) and
`current_phase`. No table is created or dropped and no data is written. Tested with
upgrade/downgrade on temporary SQLite. **Not applied to `peak_lab` or production.**

## API and UI

Consultant API (any authenticated consultant): `GET/POST /clients` (`?q=` search),
`GET/PATCH /clients/{id}` (with the client's engagements), `GET/POST /engagements`,
`GET/PATCH /engagements/{id}`, and `GET /consultant-options` (id and name only, for the
assignment picker). Request models forbid unknown fields, so any governance field is a 422.

Pages: `/clients` (search, Add client, large tappable cards), `/clients/new`, `/clients/[id]`
(profile, key personnel, the client's engagements, Add engagement), `/clients/[id]/edit`,
`/engagements` (every engagement with client, consultant, status and phase),
`/engagements/new?client=…`, `/engagements/[id]`, `/engagements/[id]/edit`. Everything uses the
Phase 201 shell and tokens. Cards are one column on phone and iPad portrait and two on wide
screens. Forms stack on phone, use two columns from 640 px, and keep 48 px controls.

## Validation

- `tests/validate_phase202_client_engagement_crud.py` (`make validate-phase202`), offline:
  migration 016 up/down; workspace allowlist narrowness; a non-Admin consultant creates and edits
  a client (with governance fields refused); two engagements under one client; engagement
  create/edit with assignment, status and phase persisted; bad status/consultant/client-change
  refused; owner `peak_consultants` and scope `engagement_authorized` stamped at creation, not
  settable on create or edit, and unchanged by edits; the unchanged Phase 34 intake-note writer
  creates a record against a workspace engagement with the matching owner and scope, and still
  rejects a mismatched owner or scope.
- `npm run build` and `npm run lint`. A local end-to-end smoke run of the real forms as a
  Consultant, with screenshots at 390, 820 and 1440 px.

## Posture and next step

Local only. No `peak_lab` or production migration, UPDATE grant, account, write enablement or
deployment. Next: deploy the consultant shell and the client/engagement workflow to a live URL.
That needs a hosting decision, migrations 015 and 016 in the target database, and a runtime
credential with `UPDATE` on `clients` and `engagements` only.
