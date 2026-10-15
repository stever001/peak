# Phase 212 — Artifact version persistence foundation

Phase 212 adds the minimum persistence for internally versioned engagement artifacts, as defined
in [`ARTIFACT_LIFECYCLE.md`](ARTIFACT_LIFECYCLE.md): an artifact's identity, immutable versions of
it, canonical content with a deterministic hash, engagement and phase association, source
references, and supersession. It adds **no approval, no release, no capsule, no proposal and no
client-facing change**, and changes nothing about the current web or DOCX report.

Baseline `596bafe` — *Add artifact lifecycle authority*.
Authorities: [`PEAK_PROJECT_CONTRACT.md`](PEAK_PROJECT_CONTRACT.md),
[`ARTIFACT_LIFECYCLE.md`](ARTIFACT_LIFECYCLE.md). Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: built and validated locally. Not deployed, and migration 018 is not applied to
production.** Production stays at Phase 207 with schema `017_discovery_workflow`. Render
Auto-Deploy remains **OFF**.

> **Open items, still open:**
> - Production Admin acceptance is pending provisioning of `admin@peakinventorysolutions.com`.
>   Authenticated production discovery, assessment and report acceptance are pending for the same
>   reason. No temporary Admin may be created.
> - Two-stage approval (Lead Consultant → Final Approver) is not implemented.
> - Capsule publication is not implemented.

## What was built

| Piece | Where |
|---|---|
| Models | `Artifact`, `ArtifactVersion` in `peak/db/models.py` |
| Migration | `alembic/versions/018_artifact_versions.py` (additive, no data) |
| Service | `peak/workspace/artifacts.py` — `create_artifact`, `create_final_report_version`, `get_artifact`, `get_artifact_version` |
| Write allowlist | two create-only pairs in `WORKSPACE_WRITE_COLUMNS`; `ARTIFACT_RECORD_TABLES` |
| Validation | `tests/validate_phase212_artifact_version_persistence.py` (`make validate-phase212`) |

## Schema

**`artifacts`** is the stable identity of one logical artifact. It holds:
- `id` (`art_<hex>`), `client_id` and `engagement_id`;
- `artifact_type` (only `final_report` so far, validated in the service);
- `engagement_phase_label`, a snapshot of the engagement's `current_phase` when the artifact is
  created. Peak has no engagement-phase entity, and this phase adds none. The label is the
  consulting stage (AL1);
- `created_by_consultant_id`.

**`artifact_versions`** holds one immutable snapshot per version:
- `id` (`artv_<hex>`), `artifact_id`, and `client_id` / `engagement_id` copied from the artifact;
- `version_number`, the internal sequence, unique per artifact and `>= 1`;
- `content_format`, `content_canonical` (LONGTEXT on MySQL) and `content_hash` (sha256 hex);
- `supersedes_version_id`, nullable and **unique**, so a version is superseded at most once and the
  history stays a single line;
- `version_status`, CHECK-constrained to the ARTIFACT_LIFECYCLE §4 states and starting at
  `versioned`;
- `created_by_consultant_id` and `source_references` (JSON).

Both tables carry the standard governance/audit columns, and governed identifiers are pinned to
`utf8mb4_bin`. Rows are created with the workspace stamp (`peak_consultants` /
`engagement_authorized`), and only under an engagement that carries it. An internal-test anchor or a
differently owned engagement is refused. The generic `review_status` and `lifecycle_status` columns
keep their defaults. **The artifact lifecycle is `version_status`, not those columns.**

## Canonical content and hash

- A Final Report version stores the **business content of the Phase 208 `FinalReport`**: all of
  `dataclasses.asdict(report)`, including the six sections, section order and titles, and the trace
  IDs inside findings. It stores no DOCX bytes, HTML or Markdown.
- Five draft-state fields are left out: `status`, `audience`, `client_facing`,
  `approved_for_client` and `requires_human_review`. They describe the live draft, not the content,
  and freezing `approved_for_client: false` into a version would contradict its later approval.
  Lifecycle state lives on the version.
- Serialization: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False,
  allow_nan=False)`. The text is stored exactly as hashed. The hash is sha256 of its UTF-8 bytes,
  named by `content_format = peak.final_report.canonical_json.v1`.
- The report contains no timestamps, so identical working state always yields an identical hash.
  Rendering Markdown or DOCX does not affect it (AL35).
- On every read, `get_artifact_version` re-hashes the stored text and returns `hash_verified`.

## Creating versions

`create_final_report_version(session_factory, artifact_id, report, consultant_id)` is the only path,
and it must be called explicitly:
- The report routes don't call it, the API has no artifact endpoint, and reading a report versions
  nothing.
- It checks that the artifact is a final report under a stamped engagement and that the report
  belongs to that engagement.
- **Identical content creates no version.** If the canonical hash equals the latest version's, it
  returns that version with `created: false`.
- Otherwise it inserts version *n + 1*, which supersedes the latest version.
- A concurrent create collides on `(artifact_id, version_number)` or on `supersedes_version_id`, and
  is refused as `version_conflict`.

## Immutability

There is no update path, enforced in four layers:
1. **Service:** no update, edit or delete function exists.
2. **Allowlist:** only `create_artifact` and `create_artifact_version`. An import-time assertion
   keeps every artifact-table action a create.
3. **ORM:** `before_update` / `before_delete` listeners on both models, plus a `do_orm_execute`
   listener that refuses bulk `UPDATE` / `DELETE` statements aimed at them. All raise
   `PermissionError`.
4. **Production database:** the runtime role holds `SELECT, INSERT` schema-wide and `UPDATE` only on
   named tables (Phase 205). The new tables get **no UPDATE or DELETE grant**, so the database
   itself refuses changes. No grant change is needed for these tables.

All updates are refused for now, including `version_status`. The approval phase will open exactly
the status transition it needs, explicitly.

> **Phase 213:** no status transition was opened. Persisted `version_status` remains the creation-state
> marker. The authoritative lifecycle state is derived from release-package, approval, designation, release and
> supersession records. See [`PHASE213_ARTIFACT_APPROVAL_RELEASE.md`](PHASE213_ARTIFACT_APPROVAL_RELEASE.md).

## Supersession

A new version records `supersedes_version_id`, and the earlier row is never touched. Nothing is
overwritten or deleted. "Superseded" is **derived** from a newer version pointing at the old one:
`get_artifact_version` returns `superseded_by_version_id`. It is never written as a status, because
that would mean updating the old row. ARTIFACT_LIFECYCLE §4 defines the meaning; this stores it
without mutation.

## Provenance captured

| Question | Answered by |
|---|---|
| Client, engagement | `client_id`, `engagement_id` on both rows |
| Engagement phase | `artifacts.engagement_phase_label` |
| Artifact, version | `artifact_id`, `id`, `version_number` |
| Who created it, when | `created_by_consultant_id`, `created_at` |
| Captured content and hash | `content_canonical`, `content_hash`, `content_format` |
| Prior version | `supersedes_version_id` |
| Source state | `source_references`: the composer (`peak.reports.final_report.compose_final_report`), report kind, and the sorted evidence, source-reference, review, recommendation, discovery-observation, session and answer IDs the report referenced |

Working-state records stay mutable (AL4). A version doesn't depend on them for reconstruction,
because it holds the content verbatim (AL8).

## Not built

- approval;
- release;
- client-facing display of versions, or any version number on a page;
- capsule binding or publication;
- proposals or any other artifact type;
- API endpoints and UI;
- event sourcing or a provenance framework;
- production migration or deploy.

## Harness changes

- Phase 11 lists the two new tables.
- The collation policy (`tools/governed_mysql_collation_audit.py`) classifies `content_format` as a
  closed-vocabulary enum. `artifact_type` and `content_format` are plain strings; identifiers and
  the hash are governed.
- Phases 206, 208 and 209 gated their "no migration 018" claim with `phase_never_committed`
  (Phase 121 convention), since that claim was about each phase's own work. Each now also asserts
  the migration history is still one linear chain.
- Thirteen older harnesses (Phases 55, 62–70, 72, 89 and 90) assert
  `git diff HEAD -- peak/persistence/allowlist.py` is empty, without a gate. They fail while
  any allowlist change is uncommitted, and pass once it is committed, as for Phase 204. They were
  left unchanged.

## Validation

- `tests/validate_phase212_artifact_version_persistence.py` — **34 checks, PASS**. It covers:
  - migration 018 up/down with no data;
  - artifact creation and its refusals (unknown type, unknown engagement, non-workspace engagement);
  - version 1 holding the canonical content of a report composed from a real workspace engagement;
  - hash stability across compositions and renderings;
  - identical content creating no version;
  - changed content creating version 2 with a new hash;
  - version 1 unchanged afterwards;
  - supersession links, and the database refusing a second successor;
  - ORM edit, bulk update and delete all refused;
  - no version field on `FinalReport`, no IDs or hash in the rendered report, and no artifact
    reference in the API or web app.
- `make validate` in the working tree: everything passes except the 13 allowlist-diff checks above.
  In a throwaway scratch clone with these changes committed, **exit 0, 83 harness runs, all PASS**.
  The clone was deleted afterwards.
- No frontend change, so no web build was needed.

## Production

No production contact. A future cutover needs:
- migration 018;
- the production verifier pin moved to `018_artifact_versions`;
- no grant change (INSERT and SELECT are already schema-wide, and the absence of UPDATE/DELETE is
  intended).

That cutover is its own approved phase.
