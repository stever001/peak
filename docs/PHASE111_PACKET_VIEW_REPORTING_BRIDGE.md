# Phase 111 — Packet-View Reporting Bridge

**Baseline:** `e1bcf08` — *Add Phase 110 packet view assembler*.

## 1. Status

**Small functionality phase: this adds a working path, not more tests.** Phase 110 built a safe
packet view that nothing used. Phase 111 connects it to reporting. Already-fetched, value-safe
record summaries now flow through the Phase 110 packet view into reporting inputs, and on to the
existing reporting agent, with review support linked to the right evidence at every step.

It used **no database**, read **no env file**, invoked **no writer**, and created **no record**. It
did **not** connect to production, `peak_lab`, or `peak_lab_scenario`. No migration `015`. No schema,
model, enum, writer, allowlist, gate, or prompt change. **One Makefile change, reported explicitly:**
the Phase 110 and Phase 111 checks were added to `make validate`. Internal-only; not client-facing.

## 2. The route

```
value-safe summaries -> assemble_packet_view (Phase 110)
                     -> build_report_inputs_from_packet_view (Phase 111)
                     -> AgentTaskRequest for initial_report_generation_agent
                     -> existing mock executor (governs and plans; generates nothing)
```

**Bridge point chosen: a small adapter in `peak/reports` (Option 1).** The planner was bypassed, not
changed. Its review references carry record ids only, never a target, and Phases 36 and 96 define its
review support as applying to every finding. Making it target-aware would change its input contract.
The adapter does not import the planner or call `_review_support`.

## 3. What the bridge produces

`build_report_inputs_from_packet_view(view) -> PacketViewReportInputs`, in
`peak/reports/packet_view_report.py`:

| Output | Content |
|---|---|
| `finding_inputs` | One per packet-view finding candidate: cited evidence id, source reference, **stored review status**, **effective review status**, **`review_support_refs` (only reviews linked to the cited evidence)**, reliability, claim scope, readiness `internal_draft_candidate`, `client_facing_allowed=false`, `recommendation_eligible=false` with reasons |
| `excluded_evidence` | Every evidence item that backs no finding, with the reason |
| `evidence_trace` | Cited evidence → source reference, whether it resolved, and its review refs |
| `recommendations` | **Always empty; blocked**, with reasons |
| `client_facing_allowed` | **Always false**; audience `internal` |
| `strict_engagement_packet_valid` | **Always false**; the Phase 110 reasons and missing sections are carried through |
| `report_task_request` | An `AgentTaskRequest` for the existing `initial_report_generation_agent` and its existing prompt contract. `input_record_ids` covers only the cited evidence, its source, and reviews linked to that evidence. `client_facing_output_requested` and `llm_execution_allowed` are both false. It is built, never run, by the bridge |

**Rules:** unreviewed evidence may back an internal-draft finding only; source-availability or
unmarked evidence never becomes a finding; a finding is recommendation-eligible never in this bridge.
A reviewed, low-reliability finding is still blocked. Output is deterministic. The module is pure, with
no database, SQLAlchemy, `peak.db`, env, file, network, or writer access.

## 4. Functional proof

`tests/validate_phase111_packet_view_reporting_bridge.py` runs the whole route on the documented
Phase 109 chain, built in memory from ids, statuses, and posture only. **29 checks, all passing**, on
the repo virtualenv and system Python:

| Proven | Result |
|---|---|
| Finding inputs | **exactly one**, citing `evid_8151dad609974ea0` |
| Its review support | **empty** — the Phase 94 review supports no finding |
| Its status | stored `needs_review`, effective **`unreviewed`**, reliability `low`, internal draft only |
| `evid_f094cbe4b47d4048` | excluded: source availability only, not an operational finding |
| Recommendations | empty and blocked (unreviewed; low reliability; no recommendation input) |
| Client-facing output | blocked on the finding and the inputs |
| Strict `EngagementPacket` | not valid; `client_intake` named and missing |
| Reporting agent input | only `evid_8151dad609974ea0` and `ing_d67b76327aba4add` — **not** `rev_70b5da9f14d54488`, **not** `evid_f094cbe4b47d4048` |
| Existing executor | permits and plans the run; no DB write, LLM call, or client-facing output |
| Review retargeted to `evid_8151dad609974ea0` | the finding gains that review and `approved_internal`; the review then reaches the agent; still not recommendation-eligible or client-facing |
| Determinism / purity | same input, same output; no planner use; no `sqlalchemy` or `peak.db` loaded |

**The Phase 94 review can no longer support the Phase 107 finding on this path.** One internal-draft
finding candidate is allowed from `evid_8151dad609974ea0`; recommendations and client-facing output
stay blocked; strict `EngagementPacket` insufficiency stays explicit.

## 5. Standard validation

**The new behaviour is in standard validation.** `make validate` now runs `validate-phase110` and
`validate-phase111`. This follows the existing pattern: two names on the `.PHONY` and `validate:`
lines, plus two two-line targets. It changes no Makefile behaviour. `make validate` reported **76
PASS, 0 FAIL** (previously 74). This closes the Phase 110 note that its test sat outside
`make validate`. `tests/README.md` remains stale and was not swept.

## 6. What remains

- **The planner bug is avoided, not fixed.** `internal_assessment_planner.py` is unchanged, and its
  category-level review support is still unsafe for packet-view evidence. **Reporting should use this
  bridge**, not the planner path.
- **The input summaries are still hand-supplied.** No fetch step feeds the assembler, and
  `claim_scope` still comes from the documented claim limits of Phases 93 and 107.
- **The executor still generates no content.** The bridge produces governed, correctly scoped inputs;
  drafting remains a consultant or future agent step.
- Coverage is not accuracy; inventory accuracy, source-of-record truth, and recommendations remain
  unanswered or blocked.

## 7. Next product step

**Phase 112: a narrow read-only fetch step** that produces the value-safe summaries from the five
`peak_lab` records and feeds them into this route, in its own approved phase with read-only lab
access. Then reporting can be exercised from stored records end to end, instead of from summaries
typed from docs. Review of `evid_8151dad609974ea0` and new evidence still wait for that path. When
they do happen, the effect will be visible, with no leakage.

---

**Provenance.** Phase 111 added `peak/reports/packet_view_report.py` and
`tests/validate_phase111_packet_view_reporting_bridge.py`, wired the Phase 110 and 111 checks into
`make validate`, and updated `PHASE_INDEX.md` and `IMPLEMENTATION_PLAN.md`. **No database was
contacted; no env file was read; no writer was invoked; no record was created; no production,
`peak_lab`, or `peak_lab_scenario` connection was made; no migration `015`; no schema, model, enum,
writer, allowlist, gate, or prompt change.** No row body, secret, DSN, host, env value, SQL, fixture
file, or sample packet was added. `peak_lab` remains at 5 application rows by documented state; this
phase did not connect to verify it.
