# Reporting Workflow Exercise — Draft-Readiness Memo

**Status:** Internal Peak working document. DB-free and record-free. Non-authoritative. **Not
client-facing, not production evidence, not publication-ready.** The engagement is a synthetic
internal test scenario — no client, real or invented, is described, and no system, count, volume,
headcount, or financial figure has been supplied or inferred.

This is the fourth consulting workflow exercised end to end. It reads on its own.

---

## 1. Workflow selected

**Reporting / initial assessment draft**, which follows evidence normalization because a report is
where normalized evidence becomes something a manager reads.

| Piece | Status |
|---|---|
| Prompt contract (`prompts/reporting/draft-initial-assessment-report.prompt.md`) | Complete and usable |
| Agent registry (`initial_report_generation_agent`) | Present, points at that contract |
| Declared input | An `EngagementPacket`, plus *optionally* the findings from the evidence step |
| Declared output | Executive summary · current-state findings · risks · quick wins · priority recommendations · first-tranche value |

Worth noting: this is the first agent in the chain flagged
`client_facing_requires_human_approval=True`. The registry knows a report is the point where output
starts pointing at a client, and it will not let the agent make that call.

## 2. Input used

The intake brief, discovery plan, and evidence-normalization plan from the three previous exercises,
unchanged. **No evidence has been collected**, so there are no evidence references and no normalized
findings — only a request list and the rules for what each item would be allowed to support.

No company, system, SKU count, volume, headcount, site size, or financial figure was supplied, and
none was inferred. No finding was written that collected evidence does not support, and no
recommendation was written that a finding does not support.

## 3. Mock executor result

The reporting agent was run through the mock executor. It resolved the prompt contract
(`exists: True`), permitted the run, and returned `planned_mock_no_execution` at `draft` /
`needs_review`, with `llm_call_made`, `agentnet_call_made`, `database_write_made`,
`client_facing_output_created`, and `resolver_context_used` all **false**.

**The executor planned the run; it generated none of the content below.** This memo was written from
the prompt contract and the three prior artifacts by hand, as the previous exercises were.

---

## 4. Draft-readiness result

**The chain is contract-complete and evidence-empty.** Both halves matter.

**Contract-complete.** Four workflows — intake, discovery, evidence normalization, reporting — each
have a working prompt contract, a registry entry that resolves it, and a governed executor path.
Each hand-off carried. Nothing in the chain is missing a step.

**Evidence-empty.** The reporting contract requires every finding, risk, and quick win to cite
packet `evid_` ids inline, and recommendations to connect back to specific findings. With no
collected evidence there are no ids, so **findings, risks, and quick wins are blocked, and
recommendations are blocked transitively** — a recommendation needs a finding, and a finding needs
evidence.

What the current inputs support is a **report shell and this readiness memo**, not a substantive
assessment. That is the contract behaving correctly. A report generator that produced findings from
an empty packet would be the failure; refusing to is the feature.

**This is now confirmed three contracts running.** Evidence normalization would return zero findings
and a long Unsupported list; reporting would return a shell. The blockage is consistent, and it is
not in the contracts.

## 5. What the report can honestly say now

Narrowly, and about Peak rather than about a warehouse:

- **Intake identified the operational uncertainty areas** — inventory accuracy, item master,
  location model, receiving and putaway, system-of-record ownership — in the client's own framing,
  with a specific trigger.
- **Discovery identified what to ask and whom to ask**, by role, with an interview sequence and a
  nine-item evidence request list.
- **Evidence normalization fixed the terms of use in advance** — the source and as-of metadata each
  item needs, and the claim each could support once it arrives.
- **The chain demonstrates hand-off shape, not operational truth.** Four workflows passed material
  forward without the claim widening at any step. That is a statement about Peak's process.

## 6. What the report must not say

None of the following is supportable, and none may appear:

- No inventory accuracy conclusion.
- No item-master quality conclusion.
- No receiving or putaway performance conclusion.
- No location or bin reliability conclusion.
- No system-of-record truth conclusion.
- No root-cause finding — the three mechanisms the client volunteered remain untested hypotheses.
- No recommendation of any kind.
- No quick wins, no risk ratings, no severity.
- No client-facing statement.
- No capsule readiness and no AgentNet publication readiness.
- No ROI, savings, or financial figure — the contract forbids manufacturing these, and nothing has
  been measured in any case.

## 7. Evidence needed before a real draft

Summarized from the normalization plan; the full per-item detail lives there.

| Evidence | Why needed for the report | Metadata required | Claim it could then support |
|---|---|---|---|
| Item master export | Tests split-ownership and contradictory data | Source system, as-of | Item-master completeness and internal consistency |
| On-hand by item and location | The core artefact everything reads against | Source system, as-of | How much of the on-hand picture is attributable |
| Receiving history | Front of the flow; sets downstream timing | Source, defined window | Receipt-recording discipline in that window |
| Putaway history | Tests the timing mechanism directly | Source, same window | Putaway lag and completeness |
| Location / bin master (+ map) | Tests model against physical layout | Source, as-of | Location-model completeness and structure |
| Cycle-count results (incl. the audit) | The only artefact speaking to accuracy | Source, period, counted population | Measured variance within the counted population |
| Adjustment history | Where corrections already happen | Source, same window | Where and how often the record is corrected |
| System-of-record ownership, in writing | Makes every other item interpretable | Author and date | The stated authority map |
| SOPs / work instructions | Separates intended from actual | Last review date | Gap between documented and observed process |

**Minimum to make a report worth drafting:** the on-hand extract, the system-of-record explanation,
and the cycle-count results. Without the second, the first cannot be interpreted; without the third,
nothing addresses the question that prompted the engagement.

## 8. Report shell

Structure a consultant can open and fill, with each section's honest state today.

| Section | State | Note |
|---|---|---|
| Executive summary | **Blocked** | Derived from findings; nothing to summarize |
| Scope and basis | **Ready** | One site under discussion, assessment-only, boundaries known |
| Evidence received | **Ready (empty)** | Correctly records that nothing has been received |
| Source authority questions | **Ready** | The authority map is unresolved and that is stateable now |
| Findings | **Blocked** | Requires `evid_` citations that do not exist |
| Risks and unknowns | **Limited** | Unknowns are stateable; risk *ratings* are not |
| Recommendations | **Blocked** | Requires findings |
| Next evidence requests | **Ready** | The nine-item list with metadata requirements |
| Appendix / evidence trace | **Ready (empty)** | The trace structure exists; it has nothing to trace yet |

Four sections are usable today, two are limited, three are blocked. **The blocked three are the ones
a client would care about**, which is the accurate summary of where this engagement stands.

## 9. Product observations

**What worked.** The reporting contract's refusal to manufacture ROI or benchmarks is the right
instinct, and the requirement that quick wins and recommendations connect back to specific findings
is what makes the blockage clean rather than partial — there is no path by which a plausible
recommendation slips in unbacked. The registry's `client_facing_requires_human_approval` flag on
this agent alone is a genuinely good detail.

**What was awkward.** Nothing in the contract, and that is the finding. Four contracts have now run
without needing a change, and each has ended at the same wall.

**Whether the chain is contract-complete but evidence-empty:** yes, and this phase settles it. That
question is now answered and does not need asking again.

**Smallest suggested improvement:** none in the reporting contract. The two carried-forward prompt
notes from earlier exercises still stand and should still be taken as one batch if and when they are
taken at all — but no further prompt work is the bottleneck now.

## 10. Recommended next decision

**The chain has been exercised as far as it can go without evidence.** A fifth docs-only exercise
over the same empty condition would produce another document saying what this one says. The next
step should be a decision, and there are two honest options.

**Option A — produce collected evidence for the synthetic lab chain, through approved durable
records.** This is what actually unblocks findings, and it would let reporting run for real rather
than describing itself. It creates records, so it needs its own phase approval, writer enablement
decision, and cleanup posture decided in advance — the same discipline Phases 92–94 used. It is the
larger step and the one that produces real product learning.

**Option B — stay DB-free and build the packet bridge.** Nothing currently produces an
`EngagementPacket`, which is the input every downstream contract names. A small bridge from the
existing prose artifacts to a packet shape would smooth every hand-off at once. This is smaller and
carries no record risk, but it improves plumbing rather than answering the open question.

**Recommendation: A.** The plumbing has now been demonstrated four times; what has not been
demonstrated is that the chain does anything useful with real material. B is worth doing eventually
and is not what the chain is waiting on.

## 11. Stop conditions

- **No findings without collected evidence.** No exceptions, including "obvious" ones.
- **No recommendations without evidence-backed findings.**
- Do not create records to make the report look complete — records for their own sake are the
  failure mode this whole sequence has been avoiding.
- No migration `015`, no new harness, no new gate.
- Do not use any of this with a client.
- **Stop if an unknown starts being repeated as a fact** — the systems, the site count, or the three
  volunteered mechanisms.

---

**Provenance.** Produced by exercising Peak's existing reporting prompt contract, agent registry
entry, and mock executor against the intake brief, discovery plan, and evidence-normalization plan
from the three previous exercises. **No database was contacted. No env file was read. No writer was
invoked. No record was created. No migration `015` was created. No schema, model, enum, writer,
allowlist, gate, or harness changed, and no prompt or source file was modified.** `peak_lab` remains
at four application rows by documented state only; this phase did not connect to verify that. No
real or pseudo-client data was used, and no model transcript, fixture, packet, or data extract is
reproduced here.
