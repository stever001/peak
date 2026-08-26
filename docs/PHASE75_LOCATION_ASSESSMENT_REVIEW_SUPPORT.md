# Phase 75 — Location Assessment Review Support: Preferred Path Declined

**Status: no production writes.** This phase contacted **no production database**, sourced **no
environment file**, invoked **no writer**, and created **no production record of any kind** — no
`review_bundle_records` row, no `internal_assessment_report_drafts` row, no `review_records` row, no
source ingestion, no evidence reference, no Client, no Engagement, no intake note, no capsule, no
report, and no AgentNet or resolver publication. It adds one document.
**Baseline:** `9e23ef2` — Add Phase 74 location readiness internal assessment outline
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — **no migration, model, writer, allowlist pair, schema, operator, or harness added**

**The preferred path was available mechanically and declined on honesty grounds.** A
`review_bundle_records` writer exists and would have accepted a bundle for this engagement. Creating
one would have cleared `fnd_000`'s `blocked_no_review_support` state. It would also have made the
record less truthful than the block it removed.

---

## 1. The Phase 74 gap, restated

Phase 74's outline `iard_50814a78a44243c2` carries one finding candidate, `fnd_000`, anchored to the
location-readiness evidence `evid_f26c5f8fc0aa44d4` and marked
`readiness_state = blocked_no_review_support`.

The Phase 36 planner decides that state in one line: a finding candidate is an
`internal_draft_candidate` if `refs["review_bundle_record_ids"]` is non-empty, and
`blocked_no_review_support` otherwise. **`review_bundle_record_ids` is the only category the planner
accepts as finding support.** This chain's review artifacts are `review_records` rows
(`rev_9b6b0a67bae54a51`, `rev_d94d4711ac12420b`), which the planner does not model as support.

## 2. Why the preferred path was declined

### 2.1 A review bundle records that review has *not* happened

`review_bundle_records` is the persistence counterpart to the Phase 29 packet review orchestration
boundary. A bundle gathers subjects out of one processed packet and queues them **for** a human
reviewer. Its readiness state is `ready_for_human_review`, and the Phase 29 planner attaches this
warning to every one it builds:

> ready for human review does not mean approved; a human reviewer decides

The Phase 30 writer then hard-stamps every stored row `review_status=needs_review`,
`output_status=draft`, `lifecycle_status=draft`, `authoritative=false`, `approval_allowed=false`,
`requires_human_review=true`, and denies any draft that arrives with those flags raised.

So a bundle is an **inbox item, not an attestation**. Using one to satisfy a check named
"review support" would clear the block with a record whose own stored meaning is *nothing here has
been reviewed yet*. The block asks for corroboration; the bundle asserts the absence of it.

### 2.2 In this chain it would state the workflow backwards

The location-readiness material **has already been reviewed** — R10 at `rev_9b6b0a67bae54a51`, and
the evidence reference itself at `rev_d94d4711ac12420b`. Minting a fresh "awaiting human review"
bundle over that same material in Phase 75 would record the chain as moving *back* to queued-for-
review, after the review had already been recorded.

### 2.3 The bundle cannot carry the support that actually exists

`ReviewBundleDraft` has fields for `source_ingestion_record_ids`, `evidence_reference_ids`,
`agent_task_queue_record_ids`, and `subject_refs`. **It has no field for a review record id**, and
`review_bundle_records` has no such column. The model says so directly: safe references live in
`details_json` — "never raw payload/content **or a final review decision**."

The declared `subject_refs` vocabulary is `source_ingestion_record`, `evidence_reference`,
`agent_task_queue_record`, and `packet_processing_receipt`. There is no `review_record` subject
type. `subject_type` is a free string at the writer boundary, so `rev_d94d4711ac12420b` *could* have
been pushed through it — that is precisely the field misuse this phase forbids, and the exact
mirror of Phase 74's decision not to force that same id into `review_bundle_record_ids`.

The bundle would therefore have listed the evidence and source ids while carrying **none of the
actual review support**, and been read by the planner as full review corroboration anyway.

### 2.4 It would have been the first bundle with no packet behind it

Every bundle path in the system is packet-derived: the Phase 31 orchestrator gathers safe refs from
processing one packet and mints a `pktproc::<idempotency_key>` receipt ref so a bundle always has at
least one subject. There is no packet-processing run behind a Phase 75 bundle. Hand-building one
straight against the Phase 30 writer would bypass Phase 29 entirely and establish a new pattern —
infrastructure by precedent, even with no code added.

### 2.5 What the trade actually was

An accurate `blocked_no_review_support` would have become a permissive `internal_draft_candidate`,
bought with a record attesting to nothing. The gain is one string in a JSON column; the cost is that
the outline would no longer say truthfully why its finding may be drafted.

## 3. Part B conditions, assessed

| condition | result |
| --- | --- |
| an existing `review_bundle_records` writer exists | **yes** — Phase 30, `peak/db/review_bundle_writer.py` |
| it can create a bundle tied to `internal_test_001` / `99999` / `internal_peak_only` | **yes** |
| it can reference the reviewed evidence chain without pretending to be client-facing | **partly** — evidence and source ingestion ids only |
| it can include `evid_f26c5f8fc0aa44d4` **and** `rev_d94d4711ac12420b`, or otherwise honestly represent the reviewed evidence support | **no** — no typed home for a review record id, and no review-decision column by design |
| the planner can consume the bundle id without field misuse | **mechanically yes, semantically no** — a not-yet-reviewed inbox item would be read as completed review support |
| no schema, writer, migration, allowlist, or new infrastructure required | yes |

Two conditions fail, so the fallback path applies: **no production rows created.** No substitute
`review_records` row was created to appear to progress either.

## 4. What `blocked_no_review_support` actually is

It is a **false negative produced by a vocabulary gap, not a governance block.** The corroboration
the state asks for exists in this chain; it is simply typed `review_records` rather than
`review_bundle_records`, and the Phase 36 planner has no category for the former.

That distinction matters for what gets fixed. The state is not telling us the finding is
under-supported. It is telling us the planner cannot see the support that is there.

## 5. Posture after Phase 75 — unchanged

Nothing moved, because nothing was written.

- **Phase 74 outline** — `iard_50814a78a44243c2`, still `plan_persisted` / `needs_review` / `draft`,
  internal audience, not client-facing, not capsule-ready. `fnd_000` remains
  `blocked_no_review_support`.
- **The finding is unchanged and stays narrow:** R1's location dimension is not currently readable
  or reliable enough to carry location-attributed evidence under the predefined thresholds. It is a
  **data-readiness / reliability finding**, and **must not be restated as an inventory accuracy
  finding**. No inventory accuracy conclusion, no quantity-correctness conclusion, and no item or
  location balance validation exists or is supported.
- **R1 remains provisional. R8 authority precedence and R5 WMS scope remain unresolved. R3–R7 remain
  deferred.**
- **No client-facing output, no final report, no capsule publication, and no AgentNet resolver
  publication** was created or authorized. The public resolver is live, which is why those gates stay
  shut rather than relaxed.
- **No artifact body** was read, printed, committed, or stored.

## 6. Smallest next step

**Recommended: leave the block in place.** It is accurate and informative as written, and the
outline already carries the finding. Nothing downstream is waiting on it.

**If the state should be cleared, the honest fix is a Phase 36 planner change, not a production
row** — teach `_finding_candidates` to accept `review_records` support alongside
`review_bundle_record_ids`, which means adding a reference category to
`REF_CATEGORY_RECORD_TYPES` and a matching request field. That is a contract change to an existing
DB-free planner: no new table, writer, migration, or operator, but it alters what the planner treats
as support and therefore **requires its own approved phase**, its own validation, and a fresh
outline row written afterwards.

**The only step that changes the finding itself remains R8 authority precedence or R5 WMS scope** —
four of R10's fifteen items are blocked on exactly those two. Neither more source collection nor any
review-support bookkeeping will move the answer.

Each remains a **separately approved phase**, as do report finalization, capsule publication, and
AgentNet resolver publication.
