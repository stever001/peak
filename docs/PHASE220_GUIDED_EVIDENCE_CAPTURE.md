# Phase 220 — Guided Evidence Capture: Architecture and Foundation

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `c4c603e`.

## Purpose

Phase 218 tasks suggest photos and document photos ("Useful records"), but a consultant could only
write a note about them. Phase 220 lets a consultant add a **photo** or a **photo of a document** to
a task while doing it on an iPad, and keeps the original file with its provenance:

```
Engagement → phase → task (→ optionally one current task record) → captured evidence
```

Evidence is **captured material only**. It is kept apart from discovery answers, task records,
observations, findings, recommendations, governed assessment evidence (`evidence_references`) and
reports. Peak does not read, parse or interpret it: no OCR, recognition, metadata extraction,
scoring or synthesis. A task record is still how a consultant says what they found.

**Status: repository-complete; production schema applied (023); application not yet deployed;
OPEN.** The Cloudflare R2 adapter is built and was checked against the private development
bucket. Production still needs the Render variables and the API deploy (see *Production
sequencing* and *Production schema cutover record*).

## What it is not

There is no OCR, document parsing, image recognition, automatic observation / finding /
recommendation, report synthesis, evidence scoring, client upload or portal, bulk ingestion, file
manager, retention engine, legal hold, PDF, video or audio. There is no delete: a wrong capture is
replaced and both are kept.

## Data model (migration 023)

One new table, `phase_task_evidence`. It is insert-only (an ORM listener refuses update and delete),
and classified `append_only`, so the runtime role needs no UPDATE grant. No existing table changes.

| Column | Meaning |
|---|---|
| `id` | `ptevd_<16 hex>` |
| `client_id`, `engagement_id`, `phase_id`, `task_id` | Linkage, copied from the task |
| `task_record_id` | Optional: one **current** record of the same task |
| `evidence_kind` | `photo` or `document_photo` (CHECK) |
| `caption` | Optional, ≤ 500 characters, the consultant's own words |
| `media_type` | `image/jpeg`, `image/png`, `image/heic`, `image/heif` (CHECK), decided from the bytes |
| `byte_length` | > 0 (CHECK) |
| `content_hash` | sha256 of the stored bytes (indexed) |
| `storage_backend` | `r2` (production) or `filesystem` (local and tests only) (CHECK) |
| `storage_key` | Server-generated `evidence/<engagement id>/<evidence id>` (unique); never leaves the API |
| `file_name` | The device file name as a plain base name, for provenance only; never shown or used as a path |
| `supersedes_evidence_id` | The capture this one replaces (unique: replaced at most once) |
| `uploaded_by_consultant_id` | Who added it; `created_at` says when |

## Architecture

Photos are too large for the web tier. Vercel functions accept and return about 4.5 MB, and an
iPad photo can be larger. So the browser talks to the API directly for the bytes, using short-lived
signed grants. Nothing else changes: the Next.js server still makes every other call with the
session cookie.

```
Task page (Next.js server, session cookie)
  GET /tasks/{id}/evidence          → items + content_path per item + upload grant (30 min)
Browser
  <form method=post enctype=multipart action={API}/evidence-uploads>   grant, file, kind, caption,
                                                                        task_record_id?, supersedes?
  API: verify grant → sniff type → size → hash → store bytes → insert row
     → 303 {PEAK_WEB_BASE_URL}/phases/{p}/tasks/{t}?evidence=added#evidence
       (or ?evidence_error=<code>#evidence)
  <img src={API}/evidence-content/{token}>     signed, 15 min, no cookie
```

- **No CORS and no cookie across origins.** The upload is a plain HTML form navigation, and the
  view is an `<img>`. The grant, not a cookie, authenticates both.
- **Grants.** `itsdangerous` signatures from the API secret with their own salts. The upload grant
  names the consultant and the task (30 min). The content token names one evidence id (15 min). An
  expired upload grant still sends the browser back to its task to try again.
- **Capture rules** are the Phase 217 record rules: the phase must be authorized, and the task must
  be in the plan and unresolved. A linked record must be a current record of the same task. A
  replacement must replace evidence of the same task.
- **Order:** bytes are stored first, then the row is inserted. A row never points at missing bytes.
  If the insert fails, the stored bytes are unreferenced and harmless.
- **Content responses** carry `X-Content-Type-Options: nosniff`,
  `Content-Security-Policy: default-src 'none'; sandbox`, `Cache-Control: private, max-age=300`,
  `Referrer-Policy: no-referrer` and `Content-Disposition: inline; filename="evidence-<id>.<ext>"`.
  The hash is re-checked on every read; a mismatch is refused.

### API

| Route | Auth | What it does |
|---|---|---|
| `GET /tasks/{id}/evidence` | session | The task's captures (oldest first), each with `content_path`; `upload` with grant, limits and types, or why capture is closed |
| `POST /evidence-uploads` | upload grant | Multipart. JSON 201, or `respond=redirect` → 303 to the task |
| `GET /evidence-content/{token}` | content token | The original bytes, unchanged |

Refusals: `invalid_grant` 401, `upload_expired` 401, `file_too_large` 413, `unsupported_type` 415,
`empty_file`, `invalid_field`, `invalid_link`, `already_replaced`, `phase_not_authorized`,
`phase_closed`, `task_resolved`, `task_not_accepted` (422), `storage_unavailable` 503. There is no
edit or delete route.

### Files and limits

- JPEG, PNG and HEIC/HEIF, decided from the leading bytes, never from the name or declared type.
  HEIC is kept as taken; Safari on iPad shows it. Other browsers may not render HEIC thumbnails;
  "Open full size" still serves the original.
- Up to 20 MB, checked in the browser, from `Content-Length` and from the bytes received.
- Embedded metadata (EXIF, including any location) is kept with the original and never read or
  shown. Peak makes no claim about where or when a photo was taken beyond who added it and when.

## Storage

`peak/workspace/evidence_storage.py` has three operations: `put` (refuses to overwrite), `read`
and `exists`. There is no delete, listing, copy or bucket call. Keys must match
`^evidence/[a-z0-9_]+/[a-z0-9_]+$`.

**Production: a private Cloudflare R2 bucket, reached only by the API** (`R2EvidenceStore`,
`boto3` against R2's S3-compatible endpoint):
- endpoint `https://<account id>.r2.cloudflarestorage.com`, derived from the account id (32 hex
  characters, checked, so the endpoint cannot be redirected); region `auto`;
- `put` is a conditional write (`If-None-Match: *`): the bucket itself refuses a key that
  exists (412), so an overwrite fails closed even between two API instances;
- `exists` is true or false only on 200 or 404; any other error raises, never "false";
- every error becomes a fixed message. No endpoint, bucket, key or credential reaches a response,
  a log line or a traceback chain;
- checksums only where the S3 API requires them; the row's sha256 is re-checked on every read;
- the bucket is private, with no public access or `r2.dev` URL. Credentials are bucket-scoped
  Object Read & Write tokens. R2 encrypts at rest.

| Variable | Where | Secret | Meaning |
|---|---|---|---|
| `PEAK_EVIDENCE_STORAGE_BACKEND` | API | no | `r2` in production, `filesystem` locally; unset means capture is off (the page says so) |
| `PEAK_R2_ACCOUNT_ID` | API | no | Cloudflare account id; the endpoint is derived from it |
| `PEAK_R2_BUCKET` | API | no | `peak-evidence-prod` in production, `peak-evidence-dev` for development |
| `PEAK_R2_ACCESS_KEY_ID` | API | yes | Bucket-scoped R2 token key id |
| `PEAK_R2_SECRET_ACCESS_KEY` | API | yes | Bucket-scoped R2 token secret |
| `PEAK_EVIDENCE_FS_ROOT` | API (local) | no | Local store directory. **Refused with a MySQL runtime database** |
| `PEAK_WEB_BASE_URL` | API | no | Web origin a browser upload is sent back to |
| `PEAK_API_PUBLIC_URL` | Web (server) | no | API origin the browser posts to and loads images from (defaults to `PEAK_API_BASE_URL`) |

The R2 variables go to the Render API service only, never to Vercel or the browser.

**Fail closed.** Unset, unknown, or `r2` with any variable missing or the account id malformed:
the store is `None`, and the API logs the reason by variable name only. The API still starts and
every other route works. The listing says capture is unavailable, an upload is refused
(`storage_unavailable`, 503) and content cannot be read. Nothing falls back to the local disk.

**Object keys** are `evidence/<engagement id>/<evidence id>`, for example
`evidence/eng_<16 hex>/ptevd_<16 hex>`. They are built by the server from opaque ids, and the
evidence id carries 64 random bits. They never contain a client, consultant, email, file name or
caption, and never leave the API.

**Retrieval: the API streams the bytes after authorization.** The signed-in task listing issues a
15-minute content token per item. `GET /evidence-content/{token}` reads the object from R2,
re-checks its sha256 and returns it with the headers above. There is no signed R2 URL and no
browser access to the bucket. At ≤ 20 MB this stays within one Render response.

Cost: a few gigabytes per engagement (an iPad photo is 2–5 MB). On R2 that is cents per month,
with no egress charge.

Recovery: the row holds the hash, so every read is verified. Keys are deterministic per evidence
id, so bytes can be found from a row. Database backups do not include the bytes. Bucket-level
protection (R2 bucket locks or lifecycle rules) is configured at Cloudflare, outside Peak.

## Web

The task page (`/phases/{id}/tasks/{taskId}`) has a **Photos and documents** section
(`#evidence`), after *Your records*:
- what was captured, with a thumbnail, its kind, the caption, the related record, who added it and
  when, its size, and "Open full size";
- "Replace this photo" (earlier versions under "Replaced versions", muted);
- **Add a photo or document**:
  - *Photo* or *Photo of a document*;
  - a file input (`accept` the four types, no forced `capture`, so iPad offers the camera or the
    library);
  - an optional caption;
  - an optional related record;
  - "Uploading…" while the browser sends the file.

  The result comes back as `?evidence=added` or a plain-language message for the refusal code.

Evidence is optional on the page. `getTaskEvidence` (`web/lib/api.ts`) returns null when the
evidence route is absent (an API deployed before Phase 220), failing or unreachable. The section
then says "Photos and documents are currently unavailable." and the rest of the task page is
unchanged. `apiGet` keeps its 404 → not-found behaviour everywhere else.

The guidance's "Useful records" note now points to this section when capture is on. When capture is
off, the section shows the API's reason, and the note still suggests recording a note. Files:
`web/lib/evidence.ts`, `web/components/evidence-capture.tsx` (client form),
`web/components/evidence-list.tsx`, and types in `web/lib/api.ts`.

## Boundary

Contract C21 is unchanged. An upload creates one `phase_task_evidence` row and nothing else. It
creates no observation, finding, recommendation, assessment evidence, task record or artifact. It
does not change task status or readiness, and it does not satisfy a task's "needs a record"
requirement. The UI text passes the advisory-boundary scan. Captions are the consultant's source
material, like task records, and are not framing-filtered. The Phase 217 refusal of `photo` /
`document_photo` / `document` **record** kinds stays (`evidence_capture_not_available`), and its
message now points to "Add photo or document".

## Validation

`tests/validate_phase220_guided_evidence_capture.py` (in `make validate`) covers:
- **migration 023:** upgrade, column parity, CHECK/UNIQUE, downgrade, no data;
- **persistence policy:** `append_only`, single create action;
- **the store:** traversal, overwrite, no delete, refused against MySQL;
- **grants:** 401, forged, expired, unknown consultant;
- **uploads:** byte-sniffed types (renamed GIF refused, JPEG declared PNG stored as JPEG, HEIC),
  empty and oversize files, unknown field;
- **links:** a current record of the same task only, across engagements too;
- **replacement:** supersession once;
- **storage:** hash and key recorded; listings never expose the key or file name;
- **content:** served unchanged, with headers; tampered, expired and unknown tokens; hash mismatch
  refused;
- **browser:** redirects;
- **closed capture:** planned phase and resolved task;
- **no edit or delete route**, and the ORM refuses update and delete;
- **capture off** with no store;
- **boundary:** only the evidence table changes; status, readiness and the record requirement are
  unchanged;
- **static UI:** multipart form to the API, accepted types, no forced camera, no storage key in the
  web app, the boundary scan, and Phase 218 files still free of file inputs.

The Phase 218 and 219 "no migration" checks now assert that *that phase* added none, since 023
belongs to Phase 220.

## Production sequencing (in progress: steps 1–3 done)

The one ordering rule: **the Phase 220 API must not run against production before migration 023
exists** (its evidence listing would fail). The web may go first: without the API's evidence
route, the task page shows the section as unavailable.

Changing a Render service's environment variables redeploys it. Add them only once 023 is applied,
so whichever commit that deploy builds is safe.

1. Commit Phase 220 with `[skip render]`. Vercel may build the web; it degrades cleanly.
2. Apply migration 023 with the migrate role (`peak_prod_migrate`). The runtime role needs no
   new grant (SELECT/INSERT are schema-wide; the table is append-only).
3. Move the verifier pin (`tools/production_mysql_collation_verify.py`, `EXPECTED_ALEMBIC_HEAD`)
   to `023_phase_task_evidence` in a follow-up commit, then run the verifier and the Phase 50 gate.
4. Add the Render variables to `peak-consultant-api`.
5. Deploy the API (installs `boto3` and `python-multipart` from `requirements-web.txt`). Check
   `/healthz` and that a task's evidence listing reports capture available.
6. Confirm the Vercel web deployment. No new Vercel variable when `PEAK_API_BASE_URL` is already
   the public API origin.
7. Read-only checks, then one approved synthetic upload, then confirm the R2 object, the row, and
   that nothing else changed.

## Production schema cutover record (2026-10-28)

**Commits.** Implementation `6164f11` `[skip render]`; Vercel deployed the web, which shows evidence
as unavailable until the API has it. The verifier pin is moved to 023 in the commit that adds this
record, `[skip render]`.

**Preflight (read-only).** Repository at `6164f11`, clean; one Alembic head, 023 the only pending
step. As `peak_prod_verify_ro`:
- head `022_engagement_roadmap_work_plan`;
- 35 base tables (34 application + `alembic_version`), `phase_task_evidence` absent;
- the 30-table `COUNT(*)` + `CHECKSUM TABLE` baseline (133 rows) identical to the Phase 219 final
  snapshot;
- verifier `verified_safe_no_remediation_required` (394/394, 11/11).

The Phase 50 gate passed as `peak_prod_runtime`.

**Migration.** Migration 023 was re-read just before it ran, identical to the reviewed file. As
`peak_prod_migrate`, with the target guard (`PEAK_ALEMBIC_TARGET=production`,
`PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`):
`alembic upgrade 023_phase_task_evidence` ran `022 → 023` only.

**Schema check afterwards (read-only):**

| Property | After |
|---|---|
| Alembic head | `023_phase_task_evidence`, single row |
| Base tables | 36 (35 application + `alembic_version`), matching the models |
| `phase_task_evidence` | InnoDB, 0 rows; 26 columns, nullability and collation as the model; 15 governed columns `utf8mb4_bin` |
| Constraints | CHECK `ck_phase_task_evidence_{kind,media_type,storage_backend,byte_length}`; UNIQUE `uq_phase_task_evidence_storage_key`, `uq_phase_task_evidence_supersedes`; 11 `ix_*`; no foreign keys |
| Existing tables | no `CREATE_TIME` changed (no rebuild); the 30-table baseline (133 rows) unchanged |
| Phase 217 tables | `roadmap_items`, `engagement_phases`, `phase_tasks`, `phase_task_records` all 0 rows |

**Grants.** None changed. `SHOW GRANTS` for `peak_prod_runtime` was identical before and after:
- USAGE on `*.*`;
- `SELECT, INSERT` on `defaultdb.*`, which covers append-only evidence creation;
- table-level UPDATE on the nine Phase 217 tables.

There is no grant on `phase_task_evidence` and no UPDATE on it. The live Phase 50 gate passed.

**Verifier.** `EXPECTED_ALEMBIC_HEAD` was moved to 023 only after the migration. The live run
returned `verified_safe_no_remediation_required`:
- head matches;
- 36 tables;
- 409/409 governed columns deterministic (394 + 15);
- 11/11 idempotency boundaries safe;
- 0 at risk.

**Not done.** No Render deploy or environment change, and no Vercel action during the cutover.
`peak-evidence-prod` was not touched, and no production evidence record was created.

**Phase 220 is not closed and not fully deployed.** Remaining:
- the Render R2 environment variables;
- the Phase 220 API deploy;
- read-only production checks;
- one approved synthetic upload;
- the preservation check;
- closure.
