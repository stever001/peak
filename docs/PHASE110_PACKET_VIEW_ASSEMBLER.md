# Phase 110 — Pure Packet-View Assembler with Target-Specific Review Association

**Baseline:** `026c479` — *Assess Phase 109 lab packet assembly*.

## 1. Status

**Small functionality phase.** Phase 110 added **one pure, read-only source module** —
`peak/reports/packet_view.py` — and **exactly one focused behavioural test** —
`tests/validate_phase110_packet_view.py`. It used **no database**, read **no env file**, invoked **no
writer**, and created **no record**. It did **not** connect to production, `peak_lab`, or
`peak_lab_scenario`. No migration `015`. No schema, model, enum, writer, allowlist, gate, prompt, or
Makefile change. Internal-only; not client-facing.

## 2. What it fixes

Phase 109 found that the existing planner counts **any** review as support for **every** finding, so
the Phase 94 review of `evid_f094cbe4b47d4048` makes the unreviewed Phase 107 finding
(`evid_8151dad609974ea0`) look reviewed. The planner receives record ids only, never a review's
target, so it cannot be made target-specific without changing its input contract. Phase 110 therefore
adds the smaller bridge Phase 109 specified: a packet view in which review association is
**target-specific by construction**.

## 3. The assembler

`assemble_packet_view(engagement, sources, evidence, reviews) -> PacketView`

**Input:** already-fetched, value-safe summaries (dicts or attribute objects) — ids, statuses,
reliability, types, source links, review target/decision/status, and an explicit `claim_scope` on
each evidence item. No ORM session, no row body; `summary` is passed through only if supplied.

**Output — `PacketView`:**

| Section | Content |
|---|---|
| `engagement` | Identity (`engagement_id`, `client_id`, `owner_id`, `authorization_scope`) and classification posture |
| `sources` | Source-ingestion ids, source reference, stored statuses |
| `evidence` | Per item: stored `review_status`, `output_status`, `lifecycle_status`, reliability, types, source link + whether it resolved, `claim_scope`, **`linked_review_ids`**, **`effective_review_status`**, `finding_candidate_allowed`, `client_facing_allowed=false`, and a strict-schema-shaped evidence item with no review field |
| `reviews` | Review id, target, subject type, decision, status, authoritative flag, and the evidence id it linked to (or none) |
| `finding_candidates` | Internal-draft-only slots, one evidence item each |
| `recommendations` | **Always empty; `recommendations_blocked=true`** |
| `strict_engagement_packet_valid` | **Always false**, with reasons |
| `missing_sections`, `unresolved_links`, `excluded_record_ids`, `warnings` | What is absent, what did not resolve, and what was refused |

**Rules:**

- **A review links to an evidence item only if its `target_id` is that item's id** and its
  `subject_record_type`, if given, is `evidence_reference`. A shared source, engagement, or phase
  never links. A review whose target is not in the view is reported as an unresolved link.
- **Stored and effective review status are separate fields.** The stored evidence row is never
  presented as changed.
- **`unreviewed` is the default.** `approved_internal` only when every linked review has decision
  `approve_internal` and status `approved_internal`. Any other linked review makes the item
  `reviewed_not_approved` — a review never upgrades status by being present.
- **Finding eligibility is separate from review status.** Only an item explicitly marked
  `claim_scope="operational_finding"`, active, and not `reviewed_not_approved` becomes a candidate.
  A source-availability or unmarked item never does. Unreviewed items can be candidates, internal
  draft only.
- **Records whose identity does not match the engagement are excluded** and reported.
- **No inference** of inventory accuracy, source-of-record truth, authority, or recommendations.
- **Pure:** no database, SQLAlchemy, `peak.db`, env, file, network, writer, LLM, or AgentNet access.
  Output is deterministic (sorted by id).

## 4. The behavioural proof

The test builds the documented Phase 109 chain in memory — ids, statuses, and posture only — and
asserts on the assembler's output. **21 checks, all passing**, on both the repo virtualenv and
system Python:

| Proven | Result |
|---|---|
| `rev_70b5da9f14d54488` links to `evid_f094cbe4b47d4048` only | yes |
| `evid_8151dad609974ea0` links no review | yes |
| `evid_8151dad609974ea0` effective status | **`unreviewed`** |
| `evid_8151dad609974ea0` stored status | **`needs_review`**, unchanged |
| `evid_8151dad609974ea0` as a finding candidate | yes — low reliability, unreviewed, **internal draft only, not client-facing** |
| `evid_f094cbe4b47d4048` treated as the R1 coverage finding | **no** — source availability only |
| Review support global | **no** — retargeting the review moves the link, and the untargeted item becomes `unreviewed` |
| Recommendations | absent and blocked |
| Client-facing output | disallowed on the view and every item |
| Strict `EngagementPacket` | reported not valid; `client_intake` missing; evidence items carry no review field |
| Module imports a database layer | no |

**So `evid_8151dad609974ea0` remains unreviewed in the packet view despite the Phase 94 review of
`evid_f094cbe4b47d4048`**, and the Phase 94 review is carried as its own record, joined to its own
target, without mutating anything.

## 5. What this does not change

- **The planner bug is avoided, not fixed.** `peak/reports/internal_assessment_planner.py` is
  unchanged and still applies review support at category level. The packet view is the safe path;
  nothing routes through it yet.
- **The strict `EngagementPacket` remains insufficient.** It requires `client_intake`, which the lab
  does not hold, and it has no place for source records, review records, or review status. The view
  does not try to satisfy it and says so.
- **Recommendations remain blocked.** Coverage is not accuracy; inventory accuracy remains unanswered.
- **`claim_scope` is a caller marking.** No stored column carries it; until a fetch step exists, it
  comes from the documented claim boundary of each evidence row (Phases 93 and 107).

## 6. Warnings and decisions needing review

1. **The test is not in `make validate`.** The `validate` target is an explicit list, and this phase
   forbids Makefile changes. The test was run directly and passes; wiring it into `make validate` is a
   one-line Makefile decision for a later approval.
2. **The planner still mis-associates reviews.** Either route reporting through the packet view, or
   give the planner target-aware input in a later phase.
3. **The effective-status rule is conservative** — all linked reviews must approve. Supersession
   ordering is not modelled.
4. **`tests/README.md`'s harness list is not updated**; it was already stale before this phase.

## 7. Next product step

**Phase 111: wire a value-safe read of the five lab records into `assemble_packet_view`** — a narrow
read-only fetch step, in its own approved phase — and **re-run the reporting workflow from the
resulting packet view** instead of from hand-assembled documents. A smaller preliminary option is
wiring the Phase 110 test into `make validate`, but not if that turns into harness cleanup. Review of
`evid_8151dad609974ea0` and new evidence wait until the packet-view path carries review status and
evidence posture end to end. After that, the planner's review support can consume
the view's per-evidence links, and a review of `evid_8151dad609974ea0` becomes a visible,
correctly-scoped change rather than one more record the read path misreads.

---

**Provenance.** Phase 110 added one pure module and one focused test, and updated `PHASE_INDEX.md` and
`IMPLEMENTATION_PLAN.md`. **No database was contacted; no env file was read; no writer was invoked; no
record was created; no production, `peak_lab`, or `peak_lab_scenario` connection was made; no
migration `015`; no schema, model, enum, writer, allowlist, gate, prompt, or Makefile change.** No
row body, secret, DSN, host, env value, SQL, fixture file, or sample packet was added; the test's
summaries are ids and statuses built in memory. `peak_lab` remains at 5 application rows by documented
Phase 109 state; this phase did not connect to verify it.
