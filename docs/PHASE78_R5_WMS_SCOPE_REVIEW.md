# Phase 78 — the R5 WMS Scope Clarification Review and the R4 Scope Correction

**Baseline:** `d830bd8` — "Add Phase 77 parallel prep for R8 R5 blockers". Branch `main`, clean tree
at baseline, Alembic head `014_engagement_classification`, 14 migrations, 18 tables, 12 writers.

Phase 78 creates **one** row in production — a single `review_records` row
(`rev_e283136f679a46dd`) reviewing the R5 WMS scope clarification source ingestion
(`ing_f7a4cc20f1f148c7`) through the unchanged Phase 22 writer, under the stored
`internal_test_001` / `99999` / `internal_peak_only` anchor. **No migration, model, writer,
allowlist pair, schema, operator, or harness** — head stays `014_engagement_classification`.

---

## 1. The R4 scope correction

Phase 77 stated that "the full required source set is R1, R2, R4, and R8" and that "within R3–R7, R4
is required". That **overstated R4 as automatically required**. Corrected here, in three places
(`PHASE77_PARALLEL_PREP_R8_R5.md`, `IMPLEMENTATION_PLAN.md`, `DATABASE_SCAFFOLD.md`):

- R4 is the **only item inside R3–R7 that Phase 62 marks *required*** rather than *important*. That is
  a **priority marking in the original request plan**, not a dependency of the current track.
- R4 is **conditionally required — scope-dependent, not automatic.** It becomes required only if a
  refreshed assessment's scope **includes count or variance reconciliation**.
- R4 must **not** be treated as required for the next refreshed location-readiness assessment unless
  that assessment is explicitly scoped that way.
- For the current narrow **location-dimension data-readiness** track, R4 is **not** required, and
  pulling it in would widen the finding into inventory accuracy, variance analysis, or quantity
  correctness — which this chain does not claim and is not authorized to claim.

**R3, R4, R6, R7, and the Phase 64 R5 receiving/putaway export all remain deferred** for Internal MVP
unless later evidence changes that.

---

## 2. R8 prerequisite content — read, and the Phase 77 inference was wrong

Phase 77 could not name R8's two authority-precedence confirmation prerequisites and reconstructed
them by inference from downstream blocked items. Phase 78 read them from the local R8 artifact after
a safety screen, and records them as **sanitized concepts only**.

**Method.** The two strings were screened *before* being read — length, token count, and pattern
tests for digits, all-caps codes, SKU-like, location-like, URL-like, and quantity-like content. All
tests were negative and both entries proved to be single-token concept slugs (21 and 27 characters),
so reading them exposed no instance data. **No artifact body was printed, copied into the
repository, committed, or stored in the database.**

**The two prerequisites, sanitized:**

1. **Quantitative findings.**
2. **An evidence reliability rating.**

**The Phase 77 inference was incorrect** — not partially accurate, incorrect in kind. Phase 77
inferred (a) a system-of-record designation per data domain and (b) a conflict/tie-break rule between
candidate systems plus an inter-system boundary. Neither is what the artifact records. The
precedence rule **already states a direction** — in sanitized terms, an ERP-class source taking
precedence over a spreadsheet-class source for item-master and balance data. What is missing is not
the rule's *content* but its *confirmation*, and the two things gating that confirmation are
**evidentiary-quality gates**, not designation questions.

**Why this matters more than a wording correction.** Confirming R8 precedence is **not** a cheap
documentation step. It requires quantitative findings and an evidence reliability rating — that is,
measurement work this engagement currently has no data for. Two consequences follow:

- Any future plan that treats "address R8's two prerequisites" as a documentation task is
  mis-scoped. It is a measurement task.
- The quantitative-findings prerequisite is precisely the kind of work that **would** pull R4 into
  scope — which is exactly the conditional trigger named in §1. This is a genuine dependency between
  the two, and it points the same way: **R4 becomes required when, and only when, quantitative or
  variance work enters scope.** It has not.

**Unchanged by this read.** R8's rule status is still `provisional_unconfirmed`. **R8 authority
precedence remains unresolved**, **R8 remains non-authoritative**, and no integrity or hash
verification of R8 is claimed. **No production row was read** to obtain any of this — the source was
the local artifact, not the database.

---

## 3. The review

**Decision: `approve_internal`, `authoritative=false`** — approved for internal reliance as a
**scope-blocker enumeration only**.

| field | value |
| --- | --- |
| record | `rev_e283136f679a46dd` |
| reviewed target | `ing_f7a4cc20f1f148c7` (`source_ingestion_record`) |
| source reference | `pkt_internal_test_r5_wms_scope_clarification_001` |
| decision | `approve_internal` |
| review status | `approved_internal` |
| output status | `draft` |
| lifecycle status | `active` |
| authoritative | `false` |
| client-facing approved | `false` |
| capsule candidate ready | `false` |
| idempotency key | `phase78_internal_test_r5_wms_scope_review_001` |

`authoritative=false` is a **reviewer decision, not a writer constraint** — the writer's
`approve_internal` validation never inspects the field and would have permitted `true`. It was
declined because the artifact resolves nothing.

**The artifact as registered:** 15 scope items, **0 favourable** — 0 `answered_yes`, 1 `answered_no`,
3 `unknown`, 9 `not_measured`, 2 `blocked_by_r8`. The nine unmeasured items are unmeasured **by
necessity**: this engagement has no live warehouse management, ERP, production, or client system, and
the artifact asserts no system landscape.

**Registration integrity: not claimed.** The review writer has no path that reads or compares
`packet_hash`, and no `packet_hash` is committed to the repo. The review therefore evaluates the R5
WMS scope clarification **as registered**, and **makes no hash or integrity confirmation**.

**What the review does not do** — recorded on the record itself, not only here. It does **not**
resolve R5 WMS scope; does **not** resolve or confirm R8 authority precedence; does **not** validate
inventory quantities or any item or location balance; asserts **no inventory accuracy conclusion**;
does **not** lift R1's provisional status or make R1 evidence-ready; does **not** make the R5 WMS
scope clarification favourable evidence; does **not** collect or unblock R3–R7; and authorizes **no**
report drafting or finalization, **no** client-facing output, **no** capsule publication, and **no**
AgentNet resolver publication.

**It also does not clear `fnd_000`.** The Phase 36 planner accepts only `review_bundle_record_ids` as
finding support, so a `review_records` row stays invisible to it and `fnd_000` remains
`blocked_no_review_support`. The Phase 74 outline is unmodified.

---

## 4. Execution

**Idempotency was rehearsed off-production first**, against a temporary SQLite database outside the
repository, and it was rehearsed **correctly** — varying a field that the payload fingerprint
actually covers:

| rehearsal step | outcome |
| --- | --- |
| first write | `created` |
| identical replay | `idempotent_replay` |
| replay with changed `reasons` (**fingerprinted**) | `denied` / `idempotency_conflict` |
| replay with changed `source_phase` only (**not fingerprinted**) | `idempotent_replay` |

The last row is the Phase 77 QA point demonstrated rather than asserted: `_payload_fingerprint`
(`peak/db/review_writer.py:87-109`) excludes `source_phase`, so varying it proves nothing about
conflict detection. One row existed in the rehearsal database at the end; the rehearsal database was
then deleted.

**Production execution** used the unchanged writer from a temporary scratchpad executor outside the
repository. **No persistent Phase 78 operator or harness was added.** The pre-DB governance path was
run as a dry-run first and passed. The write returned `created`; a subsequent replay with the
identical payload returned `idempotent_replay` with `database_write_made=false` and
`existing_record_returned=true`, confirming **exactly one row**.

Both production pre-checks passed before the write — the read-only verifier
(`readonly_queries_only=true`, head matches `014`, 212/212 governed columns deterministic) and the
runtime connectivity gate (`required_grants_present=true`, `excess_grants_present=false`,
`app_table_read_made=false`). The read-only verifier was re-run after the write and returned
`verified_safe_no_remediation_required` unchanged.

---

## 5. Non-claims and boundaries

- **One production row**, in `review_records`. **No** `source_ingestion_records`, evidence reference,
  `internal_assessment_report_drafts`, `review_bundle_records`, Client, Engagement, intake note,
  capsule, final report, client-facing output, or AgentNet publication record was created.
- **No new infrastructure** — no migration, model, writer, allowlist pair, schema, table, operator,
  or harness.
- **No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp`** was issued. **No application
  table was scanned, counted, or probed** beyond the writer's own stored-engagement load and
  idempotency lookup. The reviewed source ingestion row was **not modified** — this writer has no
  `UPDATE` path.
- **No artifact body** was printed, copied into the repository, committed, or stored in the database.
  The stored row carries posture flags, answer-state counts, non-claims, and record ids only — no
  organisation or system name, site, warehouse, location, bin, aisle, rack, item or SKU identifier,
  and no quantity or row value.
- **No secrets or environment values** were printed or committed; every gate reported
  `secrets_printed=false`.
- **No real client data.** `internal_test` only.
- The AgentNet resolver gate stays **shut rather than relaxed**, precisely because the public
  resolver is live.

---

## 6. Posture after Phase 78

- **R1 remains provisional.** The standing location finding is **data-readiness and reliability only,
  never inventory accuracy.**
- **R8 authority precedence remains unresolved** and R8 remains non-authoritative. Its two
  prerequisites are now **known rather than inferred** — quantitative findings, and an evidence
  reliability rating — and both are unconfirmed.
- **The R5 WMS scope clarification is now `approved_internal` / `draft` / `authoritative=false`**,
  approved as a scope-blocker enumeration only. **R5 WMS scope itself remains unresolved**, 0 of 15
  items favourable.
- **The Phase 64 R5 receiving/putaway export remains uncollected.**
- **R3, R4, R6, and R7 remain deferred**, with **R4 conditionally required / scope-dependent** per §1.
- **The Phase 74 outline is unmodified** and `fnd_000` remains `blocked_no_review_support`.
- **Report finalization, client-facing output, capsule publication, and AgentNet resolver publication
  remain unauthorized.**

**Next, separately approved:** because R8's prerequisites are measurement work rather than
documentation, the honest next question is whether this scenario can produce quantitative findings
and an evidence reliability rating at all. If it cannot, the correct outcome is to record that
negatively — closing the precedence question rather than leaving it open indefinitely.

---

## 7. Answered by Phase 79 (forward note)

§6 named the next honest question: whether this scenario can produce the quantitative findings and
the evidence reliability rating that R8 confirmation requires. **Phase 79 answered it: it cannot.**

Both prerequisites are recorded `blocked_by_missing_measurement` in a registered
measurement-feasibility assessment (`ing_0d671226f2ba4760`, `needs_review` / `draft` /
`authoritative=false`). Every collected source in this engagement records its basis as registered
artifact descriptions only, with no live system access, so there is nothing to measure and nothing to
rate. This is a **measurement gap, not a collection gap** — collecting the remaining uncollected
requests would not resolve it.

**R8 authority precedence still remains unresolved**, and R8 remains non-authoritative: recording
that a question cannot be answered in this scenario is not the same as closing it. A **reviewed
negative closure** is recommended in a later separately approved phase. See
[`PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md`](PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md).
