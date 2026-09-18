# Phase 119 — One-Call Consultant Assessment Workflow

**Baseline:** `45eb914` — *Add Phase 118 bounded internal recommendation*. Back to the
[phase index](PHASE_INDEX.md).

## 1. Status

**Small orchestration phase. No database access, no persistence, no writer, no migration, no schema
change, no new business logic.** Peak now exposes **one operation** that produces an internal
consultant assessment from an engagement.

## 2. The operation

`build_consultant_internal_assessment` in `peak/workflows/consultant_assessment_workflow.py`:

```python
result = build_consultant_internal_assessment(
    connection, engagement_id,
    mode=None, include_internal_test=False, policy=None)
result.assessment   # InternalAssessment
result.markdown     # rendered Markdown
```

It composes the existing route unchanged: `fetch_engagement_packet_summaries` (Phase 113, read-only)
→ `build_persisted_report_inputs` (packet view → report inputs) → `build_internal_assessment` →
`render_internal_assessment_markdown`. `mode` / `include_internal_test` pass through to the reader
(`None` keeps its Phase 57 default); `policy` is only the legacy-row fallback. Visibility refusals
propagate unchanged.

## 3. What it inherits

Persisted claim scope, persisted finding statement, target-specific review support, Phase 117
eligibility, and Phase 118 bounded recommendations all apply automatically. An engagement with only
blocked findings still returns a useful assessment with no recommendation. The result is
`client_facing=False` and `requires_human_review=True`.

## 4. Boundaries

The caller owns the connection; the workflow opens none, reads no environment variable, and calls no
writer. The reader is imported lazily, so `peak.workflows` still imports without a database driver.

## 5. Proof

Extends the Phase 113 harness (97 → **101 checks, passing**) with the reader substituted in-process:
for the Phase 107 blocked case and the synthetic eligible case, the one-call result matches the
lower-level composition exactly, with zero and one recommendation respectively. No new test file and
no Makefile change.

## 6. Next

One realistic internal product-acceptance run. **Not approved by Phase 119.**
