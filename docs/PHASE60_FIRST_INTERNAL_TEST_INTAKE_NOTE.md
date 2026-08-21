# Phase 60 — Intake Taxonomy V0, and the First Internal Test Intake Note

**Status:** production-sensitive phase — **one application record written**. Exactly **one durable
internal_test intake note was created in production**, attached to the Phase 59 anchor. No Client
record, no additional Engagement record, no downstream record, and no capsule.
**Baseline:** `1a3d75e5818724ce792410b6cea43032a39cd492`
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 60 adds no migration, no writer, and no allowlist pair
**Taxonomy:** [`PEAK_INTAKE_QUESTION_TAXONOMY_V0.md`](PEAK_INTAKE_QUESTION_TAXONOMY_V0.md)
**Writer:** [`peak/db/intake_note_writer.py`](../peak/db/intake_note_writer.py) (Phase 34, unchanged)
**Operator utility:** [`tools/create_internal_test_intake_note.py`](../tools/create_internal_test_intake_note.py)
**Harness:** [`tests/validate_phase60_first_internal_test_intake_note.py`](../tests/validate_phase60_first_internal_test_intake_note.py)
(`make validate-phase60`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. Intake questions are now grounded in the V0 taxonomy

The larger result of this phase is not the row — it is that **intake questions are now grounded in
the V0 taxonomy** rather than invented as form fields. The taxonomy's rule is that a question is
justified only when it supports a downstream decision, evidence need, report section, or readiness
judgment, and its fourteen categories are each mapped to what they feed: the operations assessment,
the prioritized improvement plan, the evidence map, the data/source quality review, the AI/AgentNet
readiness view, and future capsule/publication readiness.

**Future client-facing forms should be generated from the taxonomy, not guessed.** A form is a
rendering of the taxonomy for a particular engagement type and audience; a question that maps to no
category means either the taxonomy is missing a downstream need or the question should be cut.

**Future GeoSites intake should replicate the approach** — deriving its questions from website,
GEO/AEO, structured-data, and generative-discovery deliverables. The category list will differ
entirely; the derivation rule will not. No GeoSites code is built here.

## 2. What was written

One `intake_note_records` row, created through the unchanged Phase 34 controlled writer:

| Field | Value |
| --- | --- |
| `engagement_id` | `internal_test_001` (the Phase 59 anchor) |
| `client_id` | `99999` — reserved internal/test namespace, a visible marker only |
| `owner_id` / `requested_by` | `peak_internal_admin` |
| `requester_role` / `captured_role` | `internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `note_type` / `note_source` | `walkaround` / `internal_test` |
| `review_status` / `lifecycle_status` | `needs_review` / `draft` — review-gated and non-final |
| `idempotency_key` | `phase60_internal_test_intake_note_001` |

The note body exercises the V0 taxonomy categories — inventory accuracy, ERP plus spreadsheet
tracking, inconsistent location/bin discipline, irregular cycle counts, weak adjustment reason
codes, simultaneous stockouts and overstocks, available but un-normalized exports, incomplete SOPs,
and readiness for future AgentNet/capsule work — and states explicitly that it is internal test data
containing no real client data.

**The note body is not in this repository, and is not reproduced here.** The writer's standing rule
is that intake prose is acceptable only in the managed DB — never in Git, fixtures, examples, sample
packets, logs, receipts, or test data. The body was supplied at runtime from a file outside the
repository; only its length and SHA-256 appear in the operator's output.

## 3. The write is not client-facing, and is not smoke

The record is **not client-facing**: `client_facing_approved=false`, `publication_allowed=false`,
`capsule_candidate_ready=false`, `execution_allowed=false`, `financial_verified=false`, and
`requires_human_review=true`. Every intake note this writer produces is review-gated and non-final
by construction; the flags are server-stamped, not caller-chosen. Its parent engagement is
`internal_test`, holds no real client data, and is excluded from client-facing reads by the Phase 57
isolation primitive.

It is a **durable internal/admin record, not disposable smoke** data — retained on purpose for
development, live testing, training, and demonstration. Runtime holds `SELECT` + `INSERT` and no
`DELETE`, so it cannot be cleaned up and is not meant to be. Disposable production smoke records
remain disallowed, and no writer was enabled: this was one explicitly authorized invocation.

## 4. What was not written

- **No Client record.** `clients` remains on `NEVER_WRITABLE_TABLES`, unreachable by every path.
- **No additional Engagement record.** The Phase 59 anchor was loaded as the authorization subject
  and left untouched; no second anchor exists.
- **No downstream record** — no evidence reference, source ingestion, review, review bundle, report
  draft, review packet, agent run, or task queue row.
- **No capsule** was created or published; `capsule_publication_made=false`,
  `agentnet_publication_made=false`.
- **No client-facing output**, approval, or financial verification.
- **No UPDATE, DELETE, manual SQL, cleanup, or stamp.**
- **No app table scan, count, or probe** beyond the writer's own required work: loading the stored
  engagement by primary key and the idempotency lookup on
  `(owner_id, client_id, engagement_id, idempotency_key)`.

## 5. Authorization came from the stored engagement

The writer does not trust the caller's scope. At write time it loaded the stored `Engagement` row
and required `request.authorization_scope == engagement.authorization_scope` — identity matching
alone is explicitly not sufficient. The Phase 59 anchor's `internal_peak_only` scope is what
authorized this note; without that stored row, the write would have been denied as
`missing_subject`.

**Credential boundary.** The runtime credential was used only through the controlled writer path,
resolved by `create_session_factory` (`PEAK_RUNTIME_DATABASE_URL` only, no fallback). The
connectivity gate confirmed `SELECT` + `INSERT` with no excess grants, no global privileges, and no
`GRANT OPTION`. The read-only verifier credential was used for schema posture before and after; the
migration credential was not used and no migration ran. No credential, DSN, environment value, or
raw grant was printed or committed.

## 6. Replay is fingerprint-bound

The writer's payload fingerprint includes a SHA-256 of the note body, so replaying with the same
body is an idempotent success that writes nothing, and replaying with a changed body is an
`idempotency_conflict` denial that stops and modifies nothing. A practical consequence worth
recording: **a future replay requires the identical body**, which lives outside the repository. The
harness proves all three paths (create, identical replay, conflicting replay) against temporary
SQLite.

## 7. Still outstanding

- The V0 taxonomy is **not** the final client-facing questionnaire. Rendering it into a real form is
  future work.
- The first **client-facing read path** must call `apply_read_isolation`; internal test rows now
  exist in production at two levels (engagement and intake note).
- Any further production record remains separately approved.
