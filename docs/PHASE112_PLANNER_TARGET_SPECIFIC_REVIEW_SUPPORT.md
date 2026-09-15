# Phase 112 — Planner Target-Specific Review Support

**Baseline:** `7b8ef41` — *Add Phase 111 packet view reporting bridge*.

## 1. Status

**Small correctness phase. It fixes the planner global-review bug.** Phases 109–111 found that
`internal_assessment_planner.py` gave every review to every finding. Phase 111 avoided the bug with a
separate route. Phase 112 fixes the planner itself.

It used **no database**, read **no env file**, invoked **no writer**, and created **no record**. It
did **not** connect to production, `peak_lab`, or `peak_lab_scenario`. No migration `015`. No schema,
model, enum, writer, allowlist, DB or writer gate, or prompt change. The packet-view assembler and
reporting bridge (Phases 110–111) are **unchanged**.

## 2. The bug and the fix

**Before:** `_review_support()` returned every review id supplied in the request, and every finding
and recommendation slot received that whole list. Planner input carried record ids only, so a review
of `evid_f094cbe4b47d4048` made the finding citing `evid_8151dad609974ea0` look review-supported.

**After:** support is target-specific.

- `GovernedRecordReference` gains two optional fields: **`target_record_ids`** (which records a review
  reference reviews) and **`claim_scope`** (an evidence reference's declared scope,
  `operational_finding` or `source_availability_only`).
- A review supports a **finding** only if it names that finding's evidence id as a target.
- A **recommendation** reaches internal draft only if **every** operational evidence item it cites is
  named by a review; otherwise it is blocked, and the reason gives the count of unreviewed items.
- A plain review id, or a typed review reference with no target, **supports nothing**. The plan says
  so in its reasons.
- Evidence declared `source_availability_only` gets **no finding slot** and supports no recommendation
  slot.
- Review targets and claim scopes join the plan fingerprint, but only when present. A request without
  them keeps its previous fingerprint.
- The `review_status` *section* still reports that review references were supplied. That is
  presence, not support.

**Governance:** target ids are validated like any other reference id. Unsafe values are denied as
prohibited content. A claim scope outside the allowed set, targets on a non-review reference, and a
claim scope on a non-evidence reference are all denied as identity mismatches.

The planner still reads no stored decision, review status, subject type, or authoritative flag. A
review never approves or mutates its target.

## 3. Source and test changes (exact)

| File | Change |
|---|---|
| `peak/reports/contracts.py` | Two optional `GovernedRecordReference` fields; `CLAIM_SCOPE_*` / `ALLOWED_CLAIM_SCOPES` constants; comment and `REVIEW_RECORD_SUPPORT_CAVEAT` now say **target-specific** |
| `peak/reports/governance.py` | Report-planning request validation for the two new fields (not a DB or writer gate) |
| `peak/reports/internal_assessment_planner.py` | `_review_support` replaced by `_review_targets`, `_source_availability_evidence`, `_review_support_for`; finding and recommendation slots use them; two plan reasons; fingerprint material; docstring |
| `tests/validate_phase112_planner_target_specific_review_support.py` | New focused test (27 checks) |
| `tests/validate_phase36_internal_assessment_report_planning.py` | **Behavioural correction** — six checks that encoded category-level support now assert untargeted references support nothing and targeted references still do |
| `tests/validate_phase37_internal_assessment_report_draft_writer.py` | Plan builder's review bundle now names the evidence it reviews, so its stored plan still has a review-supported recommendation |
| `Makefile` | `validate-phase112` added to `.PHONY`, `validate:`, and one two-line target |

## 4. Behavioural proof

The new test plans the documented Phase 109 chain in memory, using ids, claim scopes, and review
targets only. **27 checks, all passing**, on both the repo virtualenv and system Python:

| Proven | Result |
|---|---|
| Finding slots | **exactly one**, citing `evid_8151dad609974ea0` |
| Its review support | **empty**; blocked for want of a review that targets it |
| The Phase 94 review `rev_70b5da9f14d54488` | supports **no** finding |
| `evid_f094cbe4b47d4048` | **no finding slot**; exclusion recorded in the plan reasons |
| Recommendations | none without a reviewer decision; with one, it cites only `evid_8151dad609974ea0` and is **blocked** (unreviewed) |
| Review retargeted to `evid_8151dad609974ea0` | the finding gains it and reaches internal draft; still no recommendation, still not client-facing |
| Plain or untargeted review reference | supports nothing; recorded in the plan reasons |
| New-field governance | unsafe target, unknown claim scope, and misplaced fields all denied |
| Determinism | same request → same fingerprint; different target → different fingerprint |
| Agreement with the packet-view bridge | both paths give the Phase 107 finding no review support, and both move support when retargeted |

**So, in planner behaviour, the Phase 94 review no longer supports the Phase 107 finding.**

## 5. Regression

Phases 36, 37, 38, 39, and 40 (every planner consumer) and the Phase 110 and 111 packet-view checks
all pass. `make validate`: **77 PASS, 0 FAIL** (previously 76). Phases 37–40 needed no other change:
they persist and review plans without asserting review readiness, except the one Phase 37 builder
noted above.

## 6. What this does not change

- **Recommendations and client-facing output remain blocked and are not made safe.** Every slot stays internal,
  human-reviewed, not client-facing, not publishable, and not financially verified. A review-supported
  recommendation slot is a structural placeholder, not an operational recommendation.
- **The planner still does not read decisions or reliability.** A targeted review counts as support
  whatever its decision, and low reliability is invisible to the planner. The packet-view route
  (Phases 110–111) is the path that reads decisions, effective review status, and reliability, and
  remains the preferred reporting route.
- **Strict `EngagementPacket` remains insufficient**, as in Phases 109–111.
- Coverage is not accuracy; inventory accuracy and source-of-record truth remain unanswered.

## 7. Warnings and decisions needing review

1. **Intentional behaviour change:** any caller passing plain review ids now gets no finding or
   recommendation support until it supplies targets.
2. **Unmarked evidence still gets finding slots.** Only a declared `source_availability_only` scope
   excludes one.
3. **Stale descriptions, not edited:** `docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`,
   `docs/PHASE96_PLANNER_REVIEW_RECORD_PATH.md`, and the `packet_view_report.py` docstring still
   describe category-level planner support. This document supersedes them.
4. `tests/README.md` remains stale.

## 8. Next product step

**Phase 113: a narrow read-only fetch** of the five `peak_lab` records into value-safe summaries,
feeding the packet-view route and able to supply typed, targeted references to the planner, in its
own approved phase with read-only lab access. Then both reporting paths can run from stored records
rather than hand-supplied summaries.

---

**Provenance.** Phase 112 changed `peak/reports/contracts.py`, `peak/reports/governance.py`, and
`peak/reports/internal_assessment_planner.py`. It added one focused test, narrowly updated the
Phase 36 and Phase 37 harnesses, wired the new test into `make validate`, and updated `PHASE_INDEX.md`
and `IMPLEMENTATION_PLAN.md`. **No database was contacted; no env file was read; no writer was
invoked; no record was created; no production, `peak_lab`, or `peak_lab_scenario` connection was
made; no migration `015`; no schema, model, enum, writer, allowlist, DB or writer gate, or prompt
change.** No row body, secret, DSN, host, env value, SQL, fixture file, or planner dump was added.
`peak_lab` remains at 5 application rows by documented state; this phase did not connect to verify
it.
