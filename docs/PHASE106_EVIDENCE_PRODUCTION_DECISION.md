# Phase 106 — Evidence Production Decision for the Synthetic Lab Chain

**Baseline:** `8e14070` — *Exercise Phase 105 reporting workflow*.

**Type:** Product decision phase. **DB-free, record-free, internal-only. No write was performed.**
No database was contacted, no env file was read, no writer was invoked, no record was created, no
migration `015` was created, and no schema, model, enum, writer, allowlist, gate, or harness changed.
`peak_lab` remains at **four application rows by documented state only** — this phase did not connect
to verify that. `peak_lab_scenario` was not opened, read, or written.

---

## 1. Decision

**Option A — produce collected evidence through approved durable lab records — with a corrected
evidence set.**

The correction matters and is the main finding of this phase. **The Phase 105 three-item minimum is
not producible.** One of the three items does not exist anywhere Peak can honestly reach it, and
manufacturing it is exactly the failure mode this sequence has been avoiding. Option A survives, but
it produces less than Phase 105 assumed, and the reduced version answers a narrower question.

Rationale in one paragraph: every mechanism Option A needs already exists and none needs changing.
The three writer/action pairs the chain uses are already inside the Phase 89 lab gate's enableable
set, all three were exercised once each in Phases 92–94, and no migration, writer, schema, model,
enum, allowlist, or gate change is required. What is *not* available is the evidence content Phase
105 named. So Phase 107 should write the one evidence claim the lab can actually support, and the
report it enables must be described accurately as a Peak-process test rather than an assessment.

**Option B is deferred, not rejected** — see §6.4. **Option C is rejected**: one honest product
question remains open and is cheaply answerable.

## 2. Why this decision is needed

Phase 105 settled that the chain is **contract-complete and evidence-empty**. Four consulting
workflows — intake, discovery, evidence normalization, reporting — each resolved their prompt
contract, each hand-off carried, and none needed a change. Reporting is blocked because findings must
cite `evid_` ids and none exist that says anything about warehouse operations.

A fifth docs-only exercise over the same empty condition would restate Phase 105. The next move is a
decision, which is this document.

## 3. The minimum evidence Phase 105 named — and what is actually reachable

Phase 105 §7 named three items as the minimum to make a report worth drafting: **the on-hand extract,
the system-of-record explanation, and the cycle-count results**. Its reasoning was sound — without the
second the first cannot be interpreted, and without the third nothing addresses the question that
prompted the engagement.

Checked against what the lab actually holds, that set does **not** map cleanly.

| Phase 105 minimum item | Lab source | Reachable? |
|---|---|---|
| On-hand extract | `r1_inventory_snapshot`, 32 rows, measured in Phase 88 §4.4 | **Yes** — coverage figures are measured, reproducible, and control-total verified |
| System-of-record explanation | `r8_system_record_map`, 10 domains, measured in Phase 88 §4.1 | **Partial** — 4 of 10 domains resolved; **R8 authority precedence remains unconfirmed and R8 remains non-authoritative** |
| Cycle-count results | **none** | **No** — the scenario has eight tables and **no cycle-count or accuracy-variance population exists in any of them** |

**The third item cannot be produced.** Reaching it would require either seeding new scenario content
(a `peak_lab_scenario` write, out of scope and separately unauthorized) or inventing evidence
contents (forbidden, and manufactured evidence besides). Neither is acceptable, so the item stays
unproduced and the accuracy question stays unanswered.

**Consequence, stated plainly.** Phase 107 does **not** produce the Phase 105 minimum, and the report
it enables is **still not worth drafting as an assessment**. What it enables is narrower: a test of
whether Peak's reporting path can carry *one* evidence-backed finding at all. That is a question
about Peak's process, not about a warehouse, and it is worth answering.

## 4. Existing writer and gate fit

Everything needed exists and nothing needs changing.

| Question | Answer |
|---|---|
| Lab gate supports the needed pair? | **Yes.** `evidence_references/create_draft` is in `LAB_ENABLEABLE_WRITER_TARGETS`, alongside `source_ingestion_records/create_source_ingestion_record` and `review_records/create_review_record` |
| Existing writer available? | **Yes** — `peak/db/evidence_writer.py`, the Phase 21 writer, used as-is in Phase 93 |
| Migration `015` required? | **No** |
| New writer required? | **No** |
| Schema / model / enum change required? | **No** |
| Gate, allowlist, or harness change required? | **No** |
| Can this be done within existing lab discipline? | **Yes** — the Phase 92/93/94 pattern applies unchanged |

Three limits carry forward from Phase 93 and are **accepted, not worked around**: `evidence_type` and
`source_type` are closed vocabularies; there is no typed link column, so the link to the source row is
carried redundantly in free-form fields; and `evidence_references` has no stored `authoritative`
column, so that posture is enforced at write time and stated in the summary rather than being readable
as a flag.

## 5. Proposed Phase 107 write plan

### 5.1 Exactly one record

**One `evidence_references` row. No source-ingestion row, and no review record.**

The reason there is no new source row is that the source already exists. Phase 92's
`source_ingestion_records` row (`ing_d67b76327aba4add`) represents the Phase 88 scenario measurement
**in full**, including the §4.4 R1 figures. A second source row scoped to R1 would restate what is
already ingested — a record created for breadth, which Phase 99 §4 names directly as something to
stop. Phase 107 therefore adds the one thing genuinely missing: an evidence reference carrying a
**substantive** claim rather than a record-existence claim.

That distinction is the whole point of the phase. Phase 93's evidence row is real and durable, but it
supports exactly one statement — *that a Phase 88 measurement exists as a controlled Peak record*.
Nothing in it says anything about inventory. That is why the chain still reads as evidence-empty from
the report's side.

### 5.2 Field plan

| Field | Value |
|---|---|
| `owner_id` / `client_id` / `engagement_id` | `peak_internal_admin` / `99999` / `lab_internal_test_001` |
| `authorization_scope` | `internal_peak_only` |
| `source_reference_id` | `ing_d67b76327aba4add` — the Phase 92 source-ingestion record |
| `source_location` | the Phase 88 logical measurement locator (logical reference, not a filesystem path) |
| `evidence_type` | `other` |
| `source_type` | `other` |
| `reliability` / `confidence_level` | `low` |
| `operational_area` / `inventory_process_area` | `inventory` / `on_hand_attribution` (both free-form; not enum-constrained) |
| `review_status` / `output_status` / `lifecycle_status` | `needs_review` / `draft` / `active` |
| `authoritative` / `client_facing_approved` / `capsule_candidate_ready` | false / false / false |
| `sensitive_data_flag` | false |
| `idempotency_key` | `phase107_lab_evidence_reference_phase88_r1_coverage_001` |

**A note on the type pair.** `measurement`/`system` was considered and **declined**. It is arguably
more accurate — this genuinely is a measurement taken from a system — but `source_type=system` risks
being read as a client system export and so as an implicit authority claim, which is precisely what
this row must not carry. The closed vocabularies admit `other`/`other` cleanly, Phase 93 set that
precedent for the same reason, and the descriptive intent belongs in the title and summary instead.
**Conservative `other`/`other` is the plan.**

### 5.3 The claim, and its boundary

The row would support **one** statement, and it must be worded so it cannot be read as more:

> In the internal synthetic lab scenario `internal_test_inventory_ops_v1` version `v1`, on-hand rows
> are attributable to both a resolvable item and a resolvable location in **14 of 32 cases**, with the
> shortfall attributable to named structural blockers — unresolvable locations, item-master gaps, and
> absent quantities.

It must explicitly **not** claim: any inventory accuracy conclusion (**coverage is not accuracy**);
any statement about a real client, real warehouse, or real source system; any benchmark, projection,
or rate to be carried outside the lab; source-system truth or R8 authority; reviewed status;
authoritative status; client-facing approval; capsule candidacy; or AgentNet publication readiness.

**Content rule, carried from Phase 93.** The row stores aggregate figures, record ids, posture flags,
and logical locators only. **No scenario row body, item or SKU value, location identifier, quantity
value, or SQL/JSON/CSV extract** may be stored on it.

### 5.4 Validation before and after

Before: evaluate the Phase 89 gate before any connection exists; verify the credential
**value-free** and structurally; confirm `peak_lab` at head `014_engagement_classification`, 18
controlled tables, exactly four application rows; verify `ing_d67b76327aba4add` exists and is
unchanged. After: confirm the new row landed in `peak_lab`, that the count moved four → five, that
every other table is unchanged, and that the receipt reads `outcome=created`. Idempotency should be
verified **structurally**, not by a second invocation.

### 5.5 What remains blocked after Phase 107

- **Inventory accuracy.** No cycle-count population exists; the question that prompted the engagement
  stays unanswered, and no later phase may answer it from this evidence.
- **R8 authority precedence.** Unconfirmed since Phase 85; Phase 107 does not reopen it.
- **The automated packet path.** `peak/ingestion/packet_mapper.py` maps *packet → drafts*, one
  direction only. **Nothing produces an `EngagementPacket`, and nothing reads DB rows into one.** A
  Phase 108 report citing this evidence would be drafted **by hand**, exactly as Phases 101–105 were,
  citing a real durable record id. That is honest and it is worth doing — but it must not be described
  as an automated chain.
- **Everything client-facing** — client-facing approval, capsule candidacy, AgentNet publication,
  production evidence, any real engagement.

## 6. Options considered

**6.1 Option A — durable lab evidence record. Chosen.** Every mechanism exists, nothing needs
changing, and it answers the open question. Cost: one durable, non-removable internal record.

**6.2 Option A as Phase 105 imagined it — three evidence items. Not possible.** See §3. Rejected
because one of the three would have to be invented.

**6.3 Option C — stop the lab chain here. Rejected.** The chain has taught a great deal about
governance and hand-off shape, but one question stays open: *can Peak's reporting path carry an
evidence-backed finding, or only describe why it cannot?* Five phases have circled it. One record
settles it.

**6.4 Option B — the DB-free `EngagementPacket` bridge. Deferred, and worth doing later.** It is a
real gap: the packet is the input every downstream contract names and nothing produces one. But it
would **not** avoid the evidence-empty problem — a bridge over empty artifacts produces an empty
packet, and the report would be blocked identically. It also needs source changes, where Option A
needs none. **It is better after evidence exists**, because then it has something to carry.

## 7. Cleanup posture

**Records created in Phase 107, if approved, are durable internal lab records.**

- They are **not** disposable smoke-test rows, and **must not be cleaned up after creation**.
- No cleanup is available in any case: the lab runtime role holds `SELECT` and `INSERT` only and **no
  `DELETE`**, so removal is impossible on this path **by construction, not by policy**. Removal would
  require the migration credential — a separate approval and a separate risk, not in scope.
- A correction means a **superseding record**, never a runtime deletion or in-place rewrite.
- They are clearly **internal test**: `client_id` `99999`, `authorization_scope`
  `internal_peak_only`, engagement `lab_internal_test_001`. **Not real client data, not pseudo-client
  data, not client accessible, not client-facing, not production evidence.**
- They must not assert authoritative evidence, and must not authorize capsule or AgentNet publication.

This posture is **decided before the write, not after** — the discipline Phases 92–94 used and the
production writer-enablement gate states explicitly.

## 8. Approval required before Phase 107

Phase 107 must not begin until each of the following is **explicitly** approved. None is granted by
this document.

1. **Approval to source the lab writer env**, out-of-repo, read structurally and value-free.
2. **Approval to enable the lab writer target/action pair** `evidence_references/create_draft` for
   that phase only. The pair is *enableable* by the Phase 89 gate; that is reachability, not approval,
   and there is no standing authority.
3. **Approval to invoke the evidence writer** — one call.
4. **Approval of the exact record count and type** — **one** `evidence_references` row, no
   source-ingestion row, no review record.
5. **Approval of the durable no-cleanup posture** in §7.
6. **Confirmation of the conservative type pair** — `other`/`other`, per §5.2.
7. **Acknowledgement that the reduced evidence set is accepted** — that Phase 107 does not produce the
   Phase 105 minimum, and that inventory accuracy stays unanswered.

Optionally approvable as a **second** record if the reviewer wants the evidence internally approved
before it is cited: one `review_records` row, `approve_internal`, `authoritative=false`. It is **not
recommended for Phase 107** — Phase 94 established that a review is INSERT-only and does not propagate
to its target, so it would not unblock anything. Reporting is blocked on evidence *existence*, not
evidence *approval*.

## 9. What not to do

- **No migration `015`** unless a concrete blocker appears. None has.
- **No schema, model, enum, writer, allowlist, gate, or harness change.** None is required.
- **No new one-off tool** if it can be avoided — Phase 99 §4 named the twelfth single-use record
  creator as a smell. The Phase 92 out-of-repo operator-script pattern applies.
- **No real or pseudo-client data**, and **no invented evidence contents** — including the missing
  cycle-count item.
- **No records for breadth alone.** One record, because one claim is missing. Not three to make a
  report shell look complete.
- **No client-facing output**, no capsule payload, no AgentNet publication.
- **No `peak_lab_scenario` write**, and no scenario row body read into a record or a document.

## 10. Recommended next phase

**Phase 107 — execute the approved minimal durable lab evidence write:** one `evidence_references`
row carrying the bounded R1 on-hand attribution claim, under the approvals in §8.

**Then Phase 108** — redraft the reporting exercise citing that record, to see whether the report
moves from a shell to **one** evidence-backed finding. That is the product question this whole
sequence has been circling, and it is the measure of whether Phase 107 was worth doing.

**Option B, the packet bridge, follows** if Phase 108 shows the hand-drafted path works and the
automation gap is the next real constraint.

---

**Provenance.** Produced by repo-local inspection of the Phase 101–105 workflow exercises, the
Phase 92–94 durable-record phases, the Phase 85 and Phase 88 lab scenario records, the Phase 99
course correction, and the source of the evidence, source-ingestion, and review writers and the lab
writer-enablement gate — **read, never invoked**. **No database was contacted. No env file was read.
No writer was invoked. No record was created. No migration `015` was created. No schema, model, enum,
writer, allowlist, gate, or harness changed.** `peak_lab` remains at four application rows by
documented state only. No secret, DSN, host, port, provider name, env value, credential path, scenario
row body, record body, model transcript, or planner JSON dump appears here.
