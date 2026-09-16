# Phase 117 — Recommendation Eligibility

**Baseline:** `1057da6` — *Add Phase 116 consultant internal assessment*. Back to the
[phase index](PHASE_INDEX.md).

## 1. Status

**Small product-functionality phase. No database access, no persistence, no writer, no migration, no
LLM, no recommendation prose.** Each finding now carries a **deterministic recommendation-eligibility
decision**: `recommendation_eligible` plus stable `recommendation_blocked_reasons`.

## 2. Data path — nothing new was persisted

Everything the decision needs already reached the Phase 111 bridge through the Phase 110 packet view:

| Input | Existing source |
|---|---|
| Review target | `EvidenceView.linked_review_ids` — target-specific links only (Phase 110/113) |
| Review decision | `effective_review_status`, derived from each linked review's `decision` + `review_status` |
| Reliability | `EvidenceView.reliability` (evidence-reference schema enum `low` / `medium` / `high`) |
| Claim scope | `EvidenceView.claim_scope` (Phase 114 persisted) |
| Finding statement | `schema_item["summary"]` (Phase 115 persisted) |
| Statement provenance | `EvidenceView.finding_statement_persisted` — set by the persisted-state adapter only |

The existing `ReportFindingInput.recommendation_eligible` / `recommendation_blocked_reasons` fields were
reused; before this phase they were hard-wired to false with an unconditional blocker.

## 3. Rule

`recommendation_block_reasons(evidence)` in `peak/reports/packet_view_report.py` — empty means
eligible. A finding is eligible only when **all** hold:

1. **a review targets the cited evidence** — else `cited evidence is not internally approved: no review targets it`;
2. **every targeting review is an internal approval** (`approve_internal` → `approved_internal`, the
   existing Phase 110 vocabulary) — else `... a review targeting it is not an internal approval`;
3. **reliability is `medium` or `high`** — else `cited evidence reliability is low` /
   `... unspecified or unrecognised`;
4. **claim scope is `operational_finding`** and **a finding statement from persisted evidence state
   is present** — else `cited evidence carries no persisted finding statement`, or, for a legacy
   `ClaimScopePolicy.summaries` fallback, `finding statement is not persisted`;
5. **the source resolves** — the only other posture blocker; inactive lifecycle and non-approving
   reviews already exclude evidence from finding candidacy upstream (Phase 110).

**Review presence alone is insufficient; the decision matters; reliability matters.** No new enum value
was introduced.

## 4. Results

- **Phase 107 finding (`evid_8151dad609974ea0`) stays blocked**: no targeted review, reliability `low`.
  The Phase 94 review still targets only the Phase 93 evidence and supports nothing.
- **Synthetic in-memory case** — targeted `approve_internal` review, reliability `medium`,
  `operational_finding`, persisted statement — is **eligible** with no blockers.
- **Same posture with a legacy caller-fallback statement** is **blocked** (`finding statement is not
  persisted`); with no statement it is blocked too.
- **Targeted but non-approving review** (`keep_needs_review` / `needs_review`) does not qualify: the
  evidence is excluded from finding candidacy, and the rule itself returns the non-approving blocker.

Eligibility generates nothing: `recommendations` stay empty, `recommendations_blocked` stays true, and
nothing is client-facing.

## 5. Internal assessment

Each finding renders `Recommendation eligibility: eligible | blocked` with its blocker reasons. The
Recommendations section still reports **Blocked** and "none was drafted".

## 6. Proof

The Phase 113 harness was extended again, 78 → **88 checks, passing**. No new test file, no Makefile
change. Phase 111 and 112 checks still pass unchanged.

## 7. Statement provenance

**Recommendation eligibility requires persisted finding text.** The persisted-state adapter
(`apply_claim_scope_policy`) marks `finding_statement_persisted` true only when the fetched row carried
the statement; `EvidenceView` and `ReportFindingInput` carry it. A **legacy caller fallback remains
readable internally** — it still appears as the finding statement — **but is not recommendation-grade**.
Summaries passed straight to `assemble_packet_view` default to not persisted. No DB field, writer,
migration, or persistence contract changed.

## 8. Next product step

**Bounded internal recommendation generation for eligible findings only** — internal, reviewable,
never client-facing. Not approved by Phase 117.
