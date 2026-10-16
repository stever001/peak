# Phase 215 — Internal test engagements

Phase 215 adds a supported `internal_test` engagement classification for testing, training and
acceptance. The normal consultant, report and artifact workflow can then be exercised without
creating fake real-client records. Baseline `5d517c1` — *Record Phase 214 deployment results*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: local only. Migration `020_internal_test_engagement_retirement` is added and not applied
to production. Nothing is deployed and no production data was written.**

Authorities:
- [`PEAK_PROJECT_CONTRACT.md`](PEAK_PROJECT_CONTRACT.md) is unchanged; no rule in it is contradicted
  (see "Authority documents").
- [`ARTIFACT_LIFECYCLE.md`](ARTIFACT_LIFECYCLE.md) gains a narrow exception in AL17 and §9B
  (AL52–AL54).

## Why

Phase 214's authenticated acceptance stopped because production had no supported path for test
material:
- **Workspace engagements were always real clients.** Every workspace engagement was born
  `real_client`, with real client data and client-accessible.
- **The internal anchor is refused.** The one internal record, the Phase 59 anchor, lacks the
  workspace stamp, so discovery and artifact writes refuse it.

## Policy

| | `real_client` | `internal_test` |
|---|---|---|
| `real_client_data` | true | **false** |
| `client_accessible` | true | **false** |
| Created by | any consultant | **any consultant (Admin or Consultant)**; classification server-forced |
| Client | ordinary client (`client_…`) | **internal test client** (reserved `internal_test_…` namespace, any consultant) |
| Approval stages | Lead → designation → Final → release | the same; neither may be skipped |
| Lead and Final Approver | **different humans** (AL17) | **may be the same human** (AL52) |
| Delete | **never** | **Admin, logical only** (AL53) |
| Internal UI | — | marked **Internal Test** |

There is one test classification, `internal_test`, used for testing, training and acceptance alike.

## Classification

**No new classification column.**
- The Phase 56 columns `engagement_category`, `real_client_data` and `client_accessible` already
  model this, and stay forbidden to every workspace write (`WORKSPACE_FORBIDDEN_COLUMNS`).
- A caller (Admin or Consultant) can only ask for the classification, with `internal_test: true`
  on `POST /clients` or `POST /engagements`. Creation is not restricted by role; deletion is.
- The server then applies the fixed constant `WORKSPACE_INTERNAL_TEST_CLASSIFICATION`
  (`peak/persistence/allowlist.py`), as it already does for the workspace stamp.
- `capsule_publication_authorized` keeps its default, false.

**The Phase 55 reserved-namespace rule is enforced at creation.**
`validate_engagement_classification` (`peak/persistence/governance.py`) requires:
- an `internal_test` engagement must belong to a reserved internal-test client;
- a `real_client` engagement must not belong to one.

So the consultant first creates an internal test client, whose id is `internal_test_<hex>`, and then
the engagement under it. Either mismatch is refused with `classification_mismatch`.

**Internal test engagements carry the workspace stamp** (`owner_id = peak_consultants`,
`authorization_scope = engagement_authorized`):
- So discovery, assessment, report, artifact versioning and release packaging accept them through
  the existing gates.
- A historical internal record without the stamp, such as the Phase 59 anchor, is still refused.
- The workflows are not widened to arbitrary internal records.

**Reads.** The consultant assessment and Final Report routes read through the Phase 57 visibility
primitive, whose default `client_facing` mode never shows `internal_test`.
- `workspace.service.assessment_read_options` uses the existing `internal_admin` mode with an
  explicit `include_internal_test = true`.
- It does so **only** for a stamped internal_test workspace engagement.
- Every other read is unchanged.

## Creation permissions

| Act | Admin | Consultant |
|---|---|---|
| Create an internal test client | yes | **yes** |
| Create an internal_test engagement (with `internal_test_confirmed`) | yes | **yes** |
| Create an internal_test engagement without the confirmation | **422** `internal_test_confirmation_required` | **422** |
| Switch an existing engagement's classification or client | **422** | **422** |
| Choose a client id | 422 | 422 |
| Create a real_client engagement under an internal test client, or `internal_test: false` there | **422** `classification_mismatch` | **422** |
| Create an internal_test engagement under a real client | **422** `classification_mismatch` | **422** |
| Send a classification, governance or retirement column on create or edit (`engagement_category`, `real_client_data`, `client_accessible`, `capsule_publication_authorized`, `owner_id`, `authorization_scope`, `deleted_at`) | 422 (schema forbids extra fields) | 422 |
| Lead on a real_client engagement: set on create or reassign | yes | **403** `admin_required` (unchanged, Phase 213) |
| Lead on an internal_test engagement, on create | assigns anyone, or leaves it unassigned | **the creator, server-set automatically**; naming anyone else is **403** |
| Reassign the Lead of any engagement afterwards | yes | **403** `admin_required` |
| Delete (retire) an internal_test engagement | yes | **403** `admin_required` |

**Creation flow.**
- **Engagement type.** The new-engagement form always offers **Real Client** and **Internal Test /
  Training**. There is also an "Add internal test engagement" entry on the engagements list.
- **Real Client** uses the client the form was opened from, unchanged.
- **Internal Test / Training:**
  - It clears any real-client selection and replaces it with an **internal test client chooser**,
    `GET /clients?internal_test=true`, which lists only reserved `internal_test_` clients.
  - **"Create internal test client"** opens the client form with the option ticked, then returns to
    the engagement form with that client chosen.
  - It requires an explicit confirmation before save: *"This engagement is for internal testing,
    training, or practice only. It will be marked internal_test, will not be treated as real client
    data, and will not be client-accessible. Continue?"*
- **The server, not the form, is the protection.** `POST /engagements` with `internal_test: true`
  also needs `internal_test_confirmed: true`, or it is refused with
  `internal_test_confirmation_required`. The confirmation alone never makes an engagement
  internal_test. The classification is forced server-side and the Phase 55 namespace rule is
  checked either way.
- **No test engagement is ever filed under a real client.** There is no shared default test
  client.

**No classification switch after creation.** The edit schema accepts only the workflow fields. Any
attempt to change `internal_test`, the classification or governance columns, or the client is
refused (422) in both directions, and the row is unchanged. No edit path between real_client and
internal_test was added.

Whoever creates it, an internal_test engagement is always born `internal_test`, with no real
client data and not client-accessible. Real-client creation is unchanged.

**Lead on internal_test.**
- **Created by a Consultant:** the Consultant becomes its Lead (`assigned_consultant_id`), set by
  the server. The form says "You will be assigned as the Lead Consultant for this training
  engagement." So the training path needs no Admin: the Consultant can take the package through
  Lead approval, self-designation, final approval and release (AL52).
- **Created by an Admin:** the Admin assigns a Lead as before, or leaves it unassigned.
- **Afterwards:** reassigning is Admin-only for every engagement. Assignment remains workflow
  metadata, not an access boundary.

## Approval change

`peak/workspace/approvals.py` applies the different-human checks only when the engagement is not
`internal_test` (`_same_human_permitted`). The three checks are:
- designating the Lead approver as Final Approver;
- the Lead approver giving the final approval;
- release with one approver.

Nothing else changes:
- the Lead approval comes first;
- a Final Approver must be explicitly designated, and the Lead may designate themselves;
- the final approval is required;
- both decisions bind the same package and hash;
- each records the reviewed rendition;
- release needs both approvals;
- the Phase 213 engagement lock still serializes designation and the final decision.

## Deletion: logical retirement

Migration `020_internal_test_engagement_retirement` adds `engagements.deleted_at` and
`engagements.deleted_by_consultant_id`, both nullable, the second a governed identifier. Nothing
else changes.

`POST /engagements/{id}/internal-test-deletion` (Admin only, `require_admin`) with
`{"confirm_engagement_label": "<exact name>"}`:
- It refuses a `real_client` engagement (`not_internal_test`) and a mistyped name
  (`confirmation_required`).
- It sets the two columns through the allowlisted `retire_internal_test_engagement` action. The
  action name avoids the prohibited "delete" substring, and no row is deleted.
- The deleted engagement leaves `GET /engagements`, its client's engagement list and the client
  engagement counts.
- It stays readable by id for audit, with `source_status: deleted`. Its released package and stored
  renditions stay readable and unchanged.
- It accepts no new work, all refused `engagement_deleted`:
  - North Star, interviews, answers, observations and their edits;
  - engagement edits;
  - package preparation;
  - designation, approvals and release;
  - a second deletion.

**Preserved:**
- the engagement row;
- discovery history;
- artifact versions, packages, renditions, approvals, designations and releases, with their hashes
  and provenance;
- any future published capsule.

**Unchanged:**
- no DELETE grant;
- no change to the ORM or Session immutability guards;
- no purge path;
- no generic delete endpoint.

The UI is a form on the engagement page, shown to an Admin only, for an active internal_test
engagement. It requires retyping the engagement name.

## Capsule propagation point

**`workspace.service.source_marker(engagement)`** returns
`{"engagement_classification": …, "source_status": "active" | "deleted"}`. It is included:
- in every engagement response;
- as `source` in every release package response.

A future capsule projection must take its classification and status from here (AL54). Phase 215
implements no publication:
- no capsule record is written;
- no route publishes;
- `capsule_publication_authorized` stays false.

## UI

An **Internal Test** badge appears on:
- the clients list and the client page;
- the engagement list;
- the engagement page (**Internal Test · Deleted** once deleted);
- the Final Report page;
- the review-and-release panel.

The badge is UI chrome only. It never enters a report rendition, so it cannot reach a real-client
artifact; the harness checks the stored web rendition.

The creation and review controls:
- **New client (any consultant):** an Internal test client checkbox, pre-ticked when opened from
  the engagement form.
- **New engagement:** the Real Client / Internal Test / Training choice, the internal test client
  chooser and the confirmation (see "Creation flow").
- **New engagement under an internal test client:** a required "Create as an Internal Test
  engagement" checkbox.
- **Review panel on internal_test:** the designation choices include the Lead.

## Authority documents

- **`ARTIFACT_LIFECYCLE.md`:**
  - AL17 gains a one-sentence exception pointing to AL52.
  - The new §9B adds:
    - **AL52**: one human may give both approvals on internal_test; neither stage is skipped.
    - **AL53**: deletion retires the source and never destroys issued artifact history.
    - **AL54**: capsules from internal_test data carry a machine-readable classification and source
      status, and are never silently deleted, rewritten or hidden when the source is deleted.
  - The rule range moves to AL1–AL54.
- **`PEAK_PROJECT_CONTRACT.md`:** unchanged. C12 requires sequential approval on the same version,
  not two different humans; that requirement lives only in AL17. C6 describes real workspace
  engagements' stamp and says internal test engagements are classified and isolated separately,
  which still holds: they carry the stamp but are classified and read-isolated.

## Schema and migration impact

- One migration, `020_internal_test_engagement_retirement`: two nullable `engagements` columns, no
  data, no artifact table touched.
- **No grant change will be needed in production.** The runtime role already holds UPDATE on
  `engagements`, and a retirement is an UPDATE.
- Production stays at `019_artifact_approval_release` until a separately approved cutover applies
  020. The verifier pin then moves with it, under the Phase 58 rule.

## Validation

- `tests/validate_phase215_internal_test_engagements.py` — **PASS**, in `make validate`. It covers
  migration 020 up and down, the 12 required proofs, the stamped-anchor refusal and the
  no-new-work rule.
- `tests/validate_phase215_internal_test_engagements.py` — 72 checks, 0 failures.
- `make PYTHON=.venv/bin/python validate` — **PASS**, exit 0, 0 failures, in a committed tree (a
  temporary detached worktree, since removed). In this uncommitted working tree, 12 older harnesses
  fail only their authoring-time "the allowlist was not modified" checks, because they diff the
  allowlist against HEAD. That clears on commit, exactly as for Phases 212/213, which also edited the
  allowlist.
- `tests/validate_phase214_mysql_artifact_concurrency.py` on the disposable MySQL 8.2.0 — **PASS**.
  Migration 020 applies on MySQL, and the concurrency and grant results are unchanged.
- `npm run lint`, `npm run build` (web) — clean.

**Harness drift fixed:**
- **Phases 206 and 208** built their temporary database at `017` while using current models. They
  now build at head, and Phase 209 reuses Phase 208's builder.
- **The Phase 214 MySQL check** pinned the head to `019`. It now accepts the repository head.

## Production

Untouched:
- no deploy;
- no migration;
- no grant change;
- no production test data.

Production authenticated acceptance (Phase 214) remains pending. It now has a supported path,
subject to these approvals:
- an approved cutover of migration 020 and this code;
- Admin bootstrap of `admin@peakinventorysolutions.com`;
- one internal test client and engagement.

A second real consultant is no longer required for an internal_test Final Approval.
