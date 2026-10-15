# Phase 213 — Release packages, two-stage approval and release

Phase 213 implements [`ARTIFACT_LIFECYCLE.md`](ARTIFACT_LIFECYCLE.md) §5–§7 and the new §9A for the
Final Report. **Human approval applies to the exact client-facing artifacts proposed for release**:

```
artifact version (Phase 212: immutable canonical business content and provenance)
  → release package
    → web rendition (static HTML bytes, stored)
    → DOCX rendition (DOCX bytes, stored)
      → Lead Consultant approval → Final Approver approval (a different, designated human) → release
```

It adds **no capsule publication, no proposal workflow, no client portal or delivery, no PDF, no new
report composition and no client-facing change to the live report**. Release is a governed internal
state, and the released files are the stored ones.

Baseline `70e5168` — *Add Phase 212 artifact version persistence*.
Authorities: [`PEAK_PROJECT_CONTRACT.md`](PEAK_PROJECT_CONTRACT.md) (C6, C7, C11–C14, C19),
[`ARTIFACT_LIFECYCLE.md`](ARTIFACT_LIFECYCLE.md). Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: built and validated locally. Not deployed, and migrations 018 and 019 are not applied to
production.** Production stays at Phase 207 with schema `017_discovery_workflow`. Render Auto-Deploy
remains **OFF**.

> **Open items, still open:**
> - Production Admin acceptance is pending provisioning of `admin@peakinventorysolutions.com`.
>   Authenticated production discovery, assessment and report acceptance are pending for the same
>   reason. No temporary Admin may be created.
> - Capsule publication is not implemented.
> - Proposal artifacts are not implemented.

## What was built

| Piece | Where |
|---|---|
| Lifecycle authority | `ARTIFACT_LIFECYCLE.md` §9A (AL41–AL51) and narrow cross-references in AL21, AL25 and AL35 |
| Models | `ArtifactReleasePackage`, `ArtifactRendition`, `ArtifactApproval`, `ArtifactFinalApproverDesignation`, `ArtifactRelease` in `peak/db/models.py` |
| Migration | `alembic/versions/019_artifact_approval_release.py` (additive, no data) |
| Web renderer | `peak/reports/final_report_html.py` — static HTML, same content as the DOCX |
| Release presentation | `peak/reports/release_presentation.py` — the client presentation of package renditions, and the client-presentation check |
| Version rebuild | `peak.workspace.artifacts.final_report_from_content` — a `FinalReport` from stored content |
| Service | `peak/workspace/approvals.py` |
| Lead assignment | `peak/workspace/service.py` — only an Admin sets or changes the assigned consultant |
| Write allowlist | five create-only pairs; `ARTIFACT_APPROVAL_TABLES` |
| API / UI | routes in `peak/consultant_api/app.py`; the internal "Review and release" panel and two rendition route handlers |
| Validation | `tests/validate_phase213_artifact_approval_release.py` (`make validate-phase213`) |

## Model

Five append-only tables. Each row records one fact. Nothing duplicates the version's canonical
content, and `artifact_versions` is not altered.

**`artifact_release_packages`**: what humans approve.
- Columns:
  - `artifact_version_id`;
  - that version's `content_hash`;
  - `package_hash`;
  - an internal `package_number`, unique per artifact;
  - `supersedes_package_id`, unique, so the history is a single line;
  - `created_by_consultant_id`.
- `package_hash` is sha256 over `peak.release_package.v1`, the version id, its content hash and
  every rendition hash, serialized canonically.

**`artifact_renditions`**: one per type (`web`, `docx`) per package.
- Columns:
  - `content_bytes`, which holds the exact rendered bytes (LONGBLOB on MySQL);
  - `rendition_hash`, the sha256 of those bytes;
  - `byte_length`, `media_type`, `rendered_by` (the renderer module), and `file_name` for the DOCX.

**`artifact_approvals`**: one decision per level per package.
- Columns:
  - `release_package_id`, `package_hash`, `artifact_version_id` and `content_hash`;
  - `approval_level` (`lead_consultant` / `final_approver`);
  - `decision` (`approved` / `rejected`);
  - the approver, `reviewed_rendition_type` (`web` / `docx`), an optional `decision_note`, and
    `created_at`;
  - for a final decision, the `designation_id` it was made under.
- Unique on (package, level).

**`artifact_final_approver_designations`**: per package. A reassignment adds a row that supersedes
the previous one, and nothing is overwritten.

**`artifact_releases`**: at most one per package. It records:
- the package, its version, `package_hash` and `content_hash`;
- the two approvals it rested on;
- who released it, and when.

All five tables:
- carry the governance and audit columns;
- are stamped `peak_consultants` / `engagement_authorized` under a stamped engagement;
- pin governed identifiers to `utf8mb4_bin`;
- are covered by the Phase 212 ORM listeners that refuse update and delete, single-row and bulk.

In production the runtime role holds only SELECT and INSERT on them, so **no grant change is
needed**.

### State is derived, not stored

A package's lifecycle state is derived from these records:

| State | When |
|---|---|
| `released` | a release record exists (still shown after a newer package supersedes it, AL14) |
| `superseded` | a newer package of the same artifact exists, and this one was never released |
| `rejected` | either level recorded a rejection |
| `final_approved` / `lead_approved` | that level recorded an approval |
| `prepared` | nothing yet |

**`artifact_versions` is never updated.** Its persisted `version_status` is the Phase 212
**creation-state marker**: it records the state a version was created in, always `versioned`.
**From Phase 213, the authoritative lifecycle state is the derived package state above.** It is
computed from packages, approvals, designations, releases and supersession. No UPDATE on
`artifact_versions` was added.

## Preparing a package

`POST /engagements/{id}/final-report/packages` is the only path. It is explicit; no read prepares
anything. It runs these steps:

1. Compose the live report, and fix it as a Phase 212 version. Identical content reuses the latest
   version.
2. **Rebuild a `FinalReport` from the version's stored canonical content.** This uses
   `final_report_from_content`, and is refused unless the rebuilt report has exactly the stored
   content.
3. Render the web rendition (`render_final_report_html`) and the DOCX
   (`render_final_report_docx`) **from that rebuilt report, in the client presentation**, so both
   derive from the stored version and from nothing else (AL34, AL44, AL50).
4. Hash both and compute the package hash. If the latest package already has that exact package
   hash, nothing is created (`created: false`). If that identical package was rejected, the
   request is refused (`package_rejected`): a rejected package is terminal and is never offered for
   another cycle. Otherwise, store the package and both renditions'
   bytes in one transaction. The new package supersedes the latest one.

A new package is therefore created when the content changes (a new version) **or** when either
rendition's bytes change, for example after a renderer change on the same version. Either way it
starts with no approvals (AL45).

### Web freezing

The web rendition is one static, self-contained HTML document:
- inline CSS, with no script, no external resource and no timestamps;
- the same sections and content as the DOCX.

**Its exact bytes are stored with the package.** Every later display serves those stored bytes:
- the review panel embeds them in a sandboxed `<iframe srcdoc>`;
- `GET /release-packages/{id}/web` serves them with a strict CSP;
- after release, the engagement's released package resolves to the same bytes.

Nothing re-renders a package, so later changes to the HTML renderer, the React UI or the composer
cannot alter what was approved or released (AL47). The harness swaps in a different renderer and
confirms the released bytes are unchanged.

### DOCX freezing

The DOCX bytes are stored with the package. `GET /release-packages/{id}/docx` returns exactly those
bytes as an attachment, with their hash in `X-Peak-Rendition-Hash`. It never regenerates the file
(AL48). The live Phase 209 export route is unchanged, and remains the internal draft export.

## Roles (unchanged from the earlier Phase 213 work)

- **Lead Consultant** is the engagement's assigned consultant, and **only an Admin may set or change
  that assignment**.
  - A consultant who creates with an assignee, or changes or clears one, is refused with
    `403 admin_required`.
  - Resending the unchanged value is allowed.
  - Consultants still view and work on every engagement. The assignment is workflow metadata, not
    an access boundary (C6), and no ACL was added.
  - The engagement form shows the assignment read-only to non-Admins.
- **Final Approver** is explicitly designated per package, after Lead approval.
  - The designation is made by the Lead approver or the assignee.
  - The designee is any existing consultant except the Lead approver.
  - It can be reassigned with history kept until the final decision. Only the current designee
    decides.
- **Different humans:**
  - the Lead approver can't be designated;
  - the Lead approver's final decision is refused;
  - release re-checks that the approvers differ.
- **Release** may be performed by either approver of the package.

## Approval binding

- **Each decision binds to the package hash the approver was shown.** That hash covers the version's
  content hash and both rendition hashes.
- **Each decision records the rendition the human reviewed** (`reviewed_rendition`: `web` or
  `docx`, required, AL51).
  - A reviewer may review either one, and the two reviewers may review different ones.
  - The rendition must belong to the package and pass its stored hash check.
  - The decision still covers the whole package.
- **The service re-verifies everything stored at every act:**
  - the version's content re-hashes to its content hash, and that hash matches the package;
  - each rendition's bytes re-hash to their rendition hash;
  - the recomputed package hash matches.
- **Final approval:** also requires the Lead approval's package hash to match.
- **Release:** requires both approvals' package hashes to match.
- **Refusal:** any mismatch, whether a wrong submitted hash or tampered stored bytes or content, is
  refused with `hash_mismatch`, and a tampered rendition is not served.
- **Live draft changes:** the existing package stays reviewable and approvable exactly as prepared.
  It doesn't change. The panel says the live draft has moved on and offers a new package for the
  current content.
- **Note:** this replaces the earlier interim rule that refused approval while the live draft
  differed. That rule existed only because approvers were then looking at the live draft. They now
  review the stored package itself.

| Act | Refused when |
|---|---|
| Lead decision | not the assigned consultant; no assignee; already decided; hash mismatch; renditions not client-facing; no or unknown reviewed rendition; package superseded or released |
| Designate Final Approver | no Lead approval (or a Lead rejection); final decision exists; actor is neither Lead approver nor assignee; unknown consultant; designee is the Lead approver; already the current designee |
| Final decision | no Lead approval; no current designation; actor is the Lead approver; actor is not the current designee; already decided; hash mismatch; renditions not client-facing; no or unknown reviewed rendition |
| Release | not both approved; approvers not distinct; actor approved neither level; hash mismatch; renditions not client-facing; already released; package superseded |

### Designation and final decision at commit time

Final Approver designation and the final decision each run in **one transaction whose first
statement is `SELECT … FROM engagements WHERE id = ? FOR UPDATE`** on the package's engagement:
- the engagement id is immutable and is read beforehand in its own short transaction;
- the lock modifies nothing;
- the production runtime role already holds UPDATE on `engagements`, which a MySQL locking read
  requires, so **no grant change** is needed.

Because the lock is the transaction's first statement, InnoDB takes its read snapshot only once the
lock is held. That snapshot therefore includes anything a competing designation or final decision
committed while it held the lock. Three guarantees follow:
- a final decision checks the designation that is current at its commit, and is recorded with that
  designation;
- once a final decision commits, a later or waiting designation sees it and is refused
  (`final_decision_recorded`);
- if a reassignment commits first, the waiting final decision sees the new designee, and only that
  consultant can decide.

SQLite (local and test) ignores the clause and serializes writers itself.

**Rejection applies to the package, and a rejected package is terminal:**
- **Lead rejection** blocks designation, the final decision and release.
- **Final rejection** blocks release and any reassignment.
- **On record:** the package and the note are kept.
- **What changing the content does:**
  - re-preparing the identical package is refused (`package_rejected`);
  - it creates a new version and a new package;
  - the old package becomes `superseded` and keeps its decisions;
  - approvals never carry over.

## API

All routes are authenticated. There is no DELETE, PATCH or PUT, and no generic status endpoint.

| Route | Purpose |
|---|---|
| `GET /engagements/{id}/final-report/packages` | packages newest first with their chains; whether the live draft matches the latest |
| `POST /engagements/{id}/final-report/packages` | prepare a package from the report as composed now |
| `GET /engagements/{id}/final-report/released` | the package current for client delivery (most recently released); 404 if none |
| `GET /release-packages/{id}` | one package's chain and rendition metadata |
| `GET /release-packages/{id}/web` · `/docx` | the stored rendition bytes, never re-rendered |
| `POST /release-packages/{id}/lead-approval` | `{decision, package_hash, reviewed_rendition, note?}` |
| `POST /release-packages/{id}/final-approver` | `{consultant_id}`, designate or reassign |
| `POST /release-packages/{id}/final-approval` | `{decision, package_hash, reviewed_rendition, note?}` |
| `POST /release-packages/{id}/release` | `{package_hash}` |

The earlier `/final-report/versions` and `/artifact-versions/...` routes from this phase's first
draft were replaced. Versions are now reached through packages. The Phase 208/209 report and DOCX
routes are unchanged, still read-only, and never create a version or package.

## UI

The internal **Review and release** panel sits on the Final Report page, marked *Internal only*,
above the live draft, which is now headed "Live draft (working state)". For the latest package it
shows:
- **the stored web page**, embedded and sandboxed, plus *Open web page*;
- **the stored DOCX**, via *Download DOCX*;
- its state, report version, fingerprint (the first 16 hex digits of the package hash) and creator;
- the Lead decision, designation history, final decision and release, with who, when and notes;
- the controls each signed-in consultant may use.

Earlier packages are listed with their rendition links. Two route handlers proxy the stored bytes,
`/release-packages/[id]/web` and `/release-packages/[id]/docx`, and the session cookie never leaves
the server.

Package and version numbers appear only in this internal panel. No rendition contains a package or
version id, a hash, or a version number.

## Client-facing release renditions (AL36, AL37, AL50)

**Package renditions are client-facing.** They are rendered through
`peak/reports/release_presentation.py`, a **presentation layer, not a composer**. Both renderers take
a `presentation`:
- the default, `INTERNAL`, is exactly the Phase 209 presentation. The internal DOCX export is
  byte-identical to before;
- a release package passes the client presentation.

The client presentation keeps the canonical content: every section in order, with every finding,
recommendation, statement and limitation. It changes only how that content is presented:

| Internal draft | Client rendition |
|---|---|
| title "Final report", subtitle client · engagement | the engagement's name as title, the client as subtitle |
| status table (status, client-facing, approved for client use, requires human review) and draft notice | omitted |
| footer "Internal draft · Not client-facing · Requires consultant review" | client · engagement · page numbers |
| engagement and client ids in the overview | names only |
| "Finding *n* — *finding id*"; evidence, source and review ids in the evidence tables | "Finding *n*"; "Evidence item *n*"; source and review **counts** |
| trace lines ending in observation, session, question and answer ids | the person, the question and the recorder only |
| "For finding *id*; evidence *id*" and "Internal only; requires human review" under each recommendation | "For Finding *n*; evidence item *n*" |
| ids inside composer sentences, e.g. evidence-limitation lines | the same sentence with the id replaced by its position label |
| section title "Internal recommendations (evidence-backed only)" | "Recommendations (evidence-backed only)" |
| the two composer count lines naming "internal recommendation(s)" | the same counts without "internal" |
| boundary statement "Internal recommendations appear only for … Phase 117/118 rules." | "Recommendations appear only for evidence-backed findings that meet the recommendation eligibility rules." |
| boundary statement "This report is internal. It has not been approved for client use …" | omitted |
| DOCX file name `final-report-…` | `<client>-<engagement>.docx` |

The rewordings are listed exhaustively in `CLIENT_TEXT`, `_CLIENT_PATTERNS` and
`CLIENT_SECTION_TITLES`. All of them are fixed composer sentences about the draft's internal status.
Consultant-entered and evidence text is never reworded; ids in it are only relabelled.

**The check is a gate.** `client_presentation_problems` reads the stored bytes of both renditions
(the HTML text, and the DOCX document and footer text). It reports **Peak-owned internal material
only**:
- the exact internal status text, footer and recommendation line, and the two composer sentences
  the client presentation rewords (`PEAK_INTERNAL_MARKERS`);
- the composer's internal-recommendation count templates (`PEAK_INTERNAL_PATTERNS`);
- the internal title "Final report" as the document's title element (the HTML `<h1>`, or the DOCX
  `Title` paragraph), unless that is the engagement's own name;
- any Peak-generated identifier, meaning every id-like value in the version content plus the
  package, artifact and version ids and hashes.

It never searches business content for words. A North Star, finding, observation or
recommendation that says "final report", "internal" or "not client-facing" doesn't make a package
not client-ready, and is never reworded to pass. The harness proves this with exactly such content.

The result is shown on each package as `client_problems`. A package with problems is refused at
the Lead decision, the final decision and the release (`not_client_ready`), and release re-checks
it at that moment.

## Harness changes

- **Phase 11:** lists the five new tables.
- **Collation policy:** classifies `approval_level`, `decision`, `media_type` and `rendered_by` as
  closed vocabularies, and `file_name` as text. Hashes and identifiers classify by pattern.
- **Phase 202:** its assignment steps run as an Admin.
- **Phase 209:** its "renderer imports only the stdlib and its sibling report modules" check now
  also allows `.release_presentation`, a sibling report module that is itself stdlib-only.
- **Phase 212:**
  - its "no artifact reference in API/web" checks are gated with `phase_never_committed`;
  - a durable check asserts that the report and DOCX read routes never create a version.
- **Phases 55, 62–70, 72, 89 and 90:** these 13 older harnesses still assert that
  `peak/persistence/allowlist.py` has no uncommitted diff. They fail until the allowlist change is
  committed, as in Phases 204 and 212.

## Validation

- **`tests/validate_phase213_artifact_approval_release.py`: 127 checks, PASS.** Through the
  authenticated API with three synthetic consultants and one synthetic Admin, it covers:
  - the ten required properties;
  - migration 019 up and down;
  - Admin-only assignment;
  - designation;
  - rejection;
  - tampering of rendition bytes and of version content;
  - append-only immutability;
  - no package data in the live report;
  - client-facing renditions: no Peak internal status text, no internal ids, a business title, the
    same statements and sections in order, and the internal draft export unchanged;
  - business content containing "final report", "internal" and "not client-facing" still producing a
    client-ready, approvable package with that wording verbatim, and an engagement named "Final
    report" keeping its name as the title;
  - a non-client-facing package refused at approval, and at release under a stricter check;
  - the reviewed rendition required and recorded, with Lead and Final reviewing different ones;
  - the lock as the first statement of both the designation and the final-decision transactions,
    and `FOR UPDATE` on MySQL;
  - terminal rejection;
  - the HTML renderer and the presentation layer import only the stdlib and sibling report modules.

  For property 9, the harness replaces both renderers at runtime and confirms that the released web
  and DOCX are still the approved bytes. For property 7, a renderer change on unchanged content
  produces package 2 on the same version, with new hashes and no approvals.
- **Phases 202, 212, 11, 42 and 44:** PASS.
- **`make validate`:** results are in the phase report. Only the 13 allowlist-diff checks fail
  before commit.
- **Web:** `npm run build`, `tsc --noEmit` and `npm run lint` are clean.
- **Local smoke test:** a scratch API with `next start` rendered the panel with no package, a
  prepared package, after designation, and after the live draft changed. It served the stored web
  and DOCX through the Next routes with matching hashes. Everything was removed afterwards.

## Known limits

- **Admins and the Lead role.** An Admin can assign anyone as Lead, including themselves. The
  different-humans rule still holds.
- **Accounts versus humans.** Distinctness is enforced per consultant account.
- **Concurrent writes.** Unique constraints refuse a duplicate decision, release or package number
  (`decision_conflict`). Designation and final decisions are serialized by the engagement lock.
  The lock ordering is verified in the harness, but the race itself has not been exercised against
  a live MySQL server: the local MySQL install is broken.
- **What the client check covers.** It catches Peak's own internal presentation material and
  Peak-generated ids. It is not a general content filter. Business content is the reviewers'
  responsibility (AL43).
- **Storage.** Each package stores two files, a few tens of kilobytes for a typical report. Nothing
  is pruned (§14: no retention policy yet).

## Production

No production contact. A future cutover needs:
- migrations 018 and 019;
- the verifier pin moved to `019_artifact_approval_release`;
- the web and API deploys;
- **no grant change**, because every artifact table is insert-only;
- **a prerequisite live concurrency test:** before applying migrations 018/019 to production, test Final Approver reassignment against the final decision using two concurrent connections on a real MySQL instance, and confirm the intended serialization behaviour. Specifically:
  - a final decision that commits first refuses a waiting reassignment;
  - a reassignment that commits first leaves only the new designee able to decide.

That cutover is its own approved phase.
