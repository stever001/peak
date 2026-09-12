# Phase 108 — Narrow Reporting Re-Exercise Against One Evidence Reference

**Baseline:** `f107863` — *Create Phase 107 lab evidence reference*.

**Status:** Internal Peak working document. **DB-free, record-free, internal-only, non-authoritative.
Not client-facing, not production evidence, not publication-ready.** No new write. The engagement is
the synthetic internal lab scenario used since Phase 85 — no client, real or invented, is described.

This is the reporting workflow run a second time, now that the chain holds one substantive evidence
reference. It reads on its own; §6 is the part a consultant would actually open.

---

## 1. The short answer

- **Reporting moved from a shell to one finding.** Phase 105 could produce a readiness memo and
  nothing else. With `evid_8151dad609974ea0` cited, it can now carry **one narrow internal finding
  candidate** about R1 on-hand attribution coverage.
- **Everything a client would care about is still blocked** — accuracy, root cause, recommendations,
  quick wins, value. One low-reliability, unreviewed coverage measure does not support any of them.
- **No operational recommendation can be made.** The only forward-looking content is an
  evidence-gathering step, labelled as such.
- **Unreviewed status does not block an internal draft; it does block anything client-facing.**
- **The missing `EngagementPacket` bridge is still real but is not the bottleneck.** The draft below
  was assembled by hand, as every prior exercise was.
- **Recommended next step:** review `evid_8151dad609974ea0` with the existing review writer, in its
  own approved phase (§11).

## 2. Workflow selected

**Reporting / initial assessment draft** — re-run because Phase 107 changed its input, and Phases 106
and 107 both named this as the test of whether that record was worth writing.

| Piece | Finding |
|---|---|
| Prompt contract | `prompts/reporting/draft-initial-assessment-report.prompt.md` — unchanged, usable |
| Registry agent | `initial_report_generation_agent` (workflow `reporting`, `client_facing_requires_human_approval=True`) |
| Declared input | An `EngagementPacket`, plus optional findings from the evidence step |
| Declared output | Executive summary · current-state findings with inline `evid_` ids · risks table · quick wins table · ranked recommendations · first-tranche value and next step |
| Governing rules that matter here | Every finding and risk cites an `evid_` id; quick wins and recommendations connect back to specific findings; no manufactured ROI, benchmarks, or metrics |

**Can the contract take a single evidence reference?** Yes. Nothing in it sets a minimum evidence
count; it requires that what *is* said be cited. It names a packet as input, and no packet exists, so
the input was assembled by hand from the documents below — the same substitution Phases 102–105 made.
No prompt change was needed.

## 3. Input used

- Phase 101 intake brief — the engagement framing and the unknowns.
- Phase 102 discovery plan — the six hypotheses and the evidence request list.
- Phase 104 evidence normalization plan — the per-item claim boundaries, especially *coverage is not
  accuracy* and *a source name is not authority*.
- Phase 105 draft-readiness memo — the report shell and the must-not-say list.
- Phase 107 evidence reference summary — the one citable record, taken **from the committed Phase 107
  document only**.

**No database was read in this phase.** No row body was used; the figures below are the aggregate
figures already committed in the Phase 107 record summary, repeated and not extended.

## 4. Mock executor result

`initial_report_generation_agent` was run through the mock executor, scoped to the internal lab
engagement with `evid_8151dad609974ea0` as the only input record id.

| Result | Value |
|---|---|
| Prompt contract resolved | yes (`exists: True`) |
| `permitted` / `status` | true / `planned_mock_no_execution` |
| `output_status` / `review_status` / `lifecycle_status` | `draft` / `needs_review` / `draft` |
| `llm_call_made` / `agentnet_call_made` / `database_write_made` | false / false / false |
| `client_facing_output_created` / `resolver_context_used` | false / false |
| Rejection reasons | none |

Resolver context was not requested, so none was routed, though the agent is flagged
`resolver_context_future=True`. **The executor planned the run and generated none of the content
below.** The draft in §6 was written by hand from the prompt contract and the inputs in §3. Passing
the record id to the executor records intent only; the executor does not read it.

## 5. What changed after Phase 107

| | Phase 105 | Phase 108 |
|---|---|---|
| Citable `evid_` ids carrying a claim about inventory data | none | **one** — `evid_8151dad609974ea0` |
| Findings section | blocked | **one internal finding candidate** |
| Risks and unknowns | unknowns only | unknowns, plus the named blockers the evidence reports |
| Recommendations / quick wins | blocked | **still blocked** |
| Executive summary | blocked | **limited** — can summarize the one finding and its limits |
| Evidence trace | structure only | **one entry** |
| Review status of cited evidence | n/a | **unreviewed** (`needs_review` / `draft`) |
| Client-facing | no | **no** |

Phase 93's evidence row still exists and still supports only a record-existence statement; it adds
nothing to the report and is not cited as a finding.

---

## 6. Narrow internal draft

> **INTERNAL DRAFT — NOT CLIENT-FACING.** Synthetic lab scenario. Cites one unreviewed,
> low-reliability evidence reference. Not an assessment of any real operation. Hand-drafted;
> not generated by an agent.

### 6.1 Executive summary — limited

In the synthetic lab scenario, fewer than half of the on-hand records can currently be tied to both a
known item and a known location: **14 of 32** (`evid_8151dad609974ea0`). The shortfall comes from
locations that don't resolve, gaps in the item master, and records with no quantity. This tells us how
much of the on-hand picture can be *placed*, not whether any quantity is *right* — **coverage is not
accuracy**, and inventory accuracy remains unanswered because no cycle-count evidence exists. Which
system is the record of authority is also unconfirmed. The evidence has not yet been reviewed. **No
recommendation follows from this yet**; the next step is gathering evidence, not changing operations.

### 6.2 Scope and basis

- One synthetic internal lab scenario (`internal_test_inventory_ops_v1`, version `v1`), engagement
  `lab_internal_test_001`, scope `internal_peak_only`.
- Basis: the Phase 88 lab measurement of the R1 on-hand snapshot, recorded as evidence in Phase 107.
- Assessment-only framing carried from Phases 101–102. No real site, system, volume, or financial
  figure is in scope, because none exists.

### 6.3 Evidence received

| Evidence | Id | Type | Reliability | Review posture | Supports |
|---|---|---|---|---|---|
| R1 on-hand attribution coverage measurement | `evid_8151dad609974ea0` | `other` / `other` | low | `needs_review` / `draft` / `active` — unreviewed | Coverage/readiness finding candidate only |

Linked source record: `ing_d67b76327aba4add` (the Phase 92 source-ingestion record for the Phase 88
measurement).

Of the Phase 105 three-item minimum, this is a partial answer to the first (the on-hand extract). The
system-of-record explanation remains partial — R8 precedence unconfirmed — and the cycle-count
results do not exist in the lab (Phase 106 §3).

### 6.4 Current-state findings

**Data quality — one internal finding candidate.** See §7 for the full candidate.

*R1 on-hand attribution coverage is incomplete in the synthetic lab scenario:* 14 of 32 on-hand rows
are attributable to both a resolvable item and a resolvable location (`evid_8151dad609974ea0`).

Separation, per the evidence contract's four-way split:

- **Observed evidence:** the 14-of-32 coverage figure and the blocker counts, as stored.
- **Stakeholder claim:** none used. The intake's "can't trust the on-hand numbers" is the client's
  framing and is not corroborated or contradicted by a coverage measure.
- **Consultant interpretation:** a majority of on-hand records cannot currently be placed, which
  limits what any later accuracy work could be read against. *Interpretation, not finding.*
- **Follow-up:** the evidence requests in §6.7.

### 6.5 Risks and unknowns

No risk **severity** is assigned. One unreviewed, low-reliability measure does not support a rating.

| Item | Kind | Evidence | Why it matters |
|---|---|---|---|
| Unresolvable locations — 7 of 32 (3 with no location code, 4 naming a code absent from the location model) | Reported blocker | `evid_8151dad609974ea0` | Rows that cannot be placed cannot be counted against a location |
| Item-master gaps — 11 of 32 | Reported blocker | `evid_8151dad609974ea0` | Rows that cannot be tied to an item cannot be interpreted |
| Absent quantities — 3 of 32 | Reported blocker | `evid_8151dad609974ea0` | A row with no quantity says nothing about stock |
| Source-of-record precedence unconfirmed | Unknown | `evid_8151dad609974ea0` (stored as unconfirmed) | No figure can be attributed to a system of record |
| Inventory accuracy | Unknown | none — no cycle-count population exists | The question that prompted the engagement is unanswered |
| Evidence unreviewed | Posture | `evid_8151dad609974ea0` | The finding candidate has had no second reader |

Blocker counts are reported per category as stored. This draft does not add them, net them, or
cross-tabulate them, and does not infer overlap between categories.

### 6.6 Quick wins and recommendations — blocked

**No quick win and no operational recommendation is supported.** See §9.

### 6.7 Next evidence requests

1. **Review of `evid_8151dad609974ea0`** by an internal reviewer, so the one finding is either
   confirmed as an internal finding or corrected (§11).
2. **A bounded cycle-count / variance source**, only through an approved future phase, and only if one
   can be obtained honestly — none exists in the lab and none may be seeded or invented.
3. **Confirmation of source-of-record precedence (R8)** before any figure is attributed to a system.
4. **The blocker detail behind each category** (which location codes are missing from the model, which
   item-master attributes are absent) — only if a later phase approves reading it, and never reproduced
   as row bodies in a document.

### 6.8 First-tranche value and next step

**Not stateable.** No billing objective exists (Phase 102), and a single coverage measure does not
establish value. The honest next step is §6.7, not a proposal.

### 6.9 Appendix — evidence trace

| Statement in this draft | Evidence | Boundary |
|---|---|---|
| 14 of 32 R1 on-hand rows attributable to both a resolvable item and location | `evid_8151dad609974ea0` → `ing_d67b76327aba4add` | Coverage/readiness only |
| Blocker categories and counts (7 / 11 / 3) | `evid_8151dad609974ea0` | As stored; not summed or cross-tabulated |
| Source-of-record precedence unconfirmed | `evid_8151dad609974ea0` | States an unknown, not a finding |
| Inventory accuracy unanswered | Phase 106 §3, Phase 107 §5 | Absence of evidence, stated as such |

---

## 7. The finding candidate

Exactly one.

| Field | Value |
|---|---|
| Finding | R1 on-hand attribution coverage is incomplete in the synthetic lab scenario. |
| Evidence | `evid_8151dad609974ea0` (source `ing_d67b76327aba4add`) |
| Basis | 14 of 32 R1 on-hand rows (43.8%) are attributable to both a resolvable item and a resolvable location. |
| Named blockers | 7 unresolvable locations; 11 item-master gaps; 3 absent quantities; source-of-record precedence unconfirmed. |
| Confidence / reliability | low |
| Review posture | `needs_review` / `draft` — **unreviewed** |
| Boundary | Supports a coverage/readiness statement **only**. **Does not support inventory accuracy.** Not a statement about any real client, warehouse, or system; no benchmark or rate for use outside the lab. |

Why it is safe to draft: it cites a durable record id, it repeats the record's own claim and no more,
and every limit the record states is carried into the text beside it.

## 8. What remains blocked

- **Inventory accuracy** — no cycle-count population exists.
- **Cycle-count variance** — same reason.
- **Source-of-record truth** — nothing is attributed to a system of record.
- **R8 authority precedence** — unconfirmed since Phase 85.
- **Item-master quality conclusion** beyond the blocker category and count.
- **Receiving and putaway performance** — no receiving or putaway evidence is cited.
- **Location/bin reliability as an operational conclusion** — the blocker count describes the model's
  fit to the snapshot, not the floor.
- **Root cause** — the Phase 101 mechanisms and Phase 102 hypotheses remain untested.
- **Recommendations** and **quick wins**.
- **ROI, savings, or any financial estimate.**
- **Risk severity ratings.**
- **Client-facing report.**
- **Capsule readiness** and **AgentNet publication readiness.**

## 9. Recommendations

**No operational recommendation is supported yet.** The reporting contract requires recommendations
to connect back to findings. The one finding is unreviewed, low-reliability, single-source, and
describes coverage rather than accuracy. Anything operational built on it — cleaning the item master,
re-labelling locations, changing putaway — would be a recommendation the evidence cannot carry.

**Evidence-gathering next step (not an operational recommendation):** review `evid_8151dad609974ea0`
first if the goal is to test how reporting treats reviewed evidence; or, only through a separately
approved phase, obtain a bounded cycle-count/variance evidence source without inventing one.

## 10. Product observations

**Did reporting become useful with one evidence reference?** Modestly, and in the right way. The
draft now says one true, specific thing and puts every limit next to it. For a consultant, §6.1 and §7
are usable internally as they stand. It is not an assessment and should not be described as one.

**Did it stay narrow?** Yes, and the contract did the work. The requirement that recommendations
connect to findings is what kept §9 empty without any special handling.

**Did unreviewed status matter?** For the internal draft, **no** — Phase 106 was right that reporting
was blocked on evidence *existence*, not approval. For anything client-facing, **yes**. The
practical gap: **the reporting contract says nothing about the review status of the evidence it
cites.** It treats any `evid_` id in the packet as citable. The posture label in §6 was added by hand
from the Phase 107 record; nothing in the workflow would have added it. Phase 94 also established that
a review record does not propagate to its target, so even after review the evidence row itself would
still read `needs_review` — a report would have to look the review up separately.

**Did the missing `EngagementPacket` bridge matter?** Only as friction. With one evidence item, hand
assembly took minutes and was easy to check. It becomes the bottleneck once there are enough evidence
items that hand assembly stops being checkable — not yet.

**What is the next bottleneck?** In order: **evidence review** (cheapest, and it answers the open
reviewed-versus-unreviewed question), then **more evidence** (the one that actually unblocks accuracy,
and the hardest to obtain honestly), then **packet assembly**.

**Prompt change needed?** No. The review-status gap above is worth noting for the batch of prompt
notes carried since Phases 101, 102, and 104, and should be taken with them if and when they are
taken.

## 11. Recommended next step

**Phase 109 — review `evid_8151dad609974ea0` using the existing review writer.**

It is the smallest step that changes what reporting can say. It uses a writer/action pair already in
the lab gate's enableable set and already exercised once (Phase 94), so it needs no migration, no new
writer, and no new framework. It would turn the finding candidate into either a reviewed internal
finding or a corrected one, and it tests the question §10 raised: how a report should treat reviewed
versus unreviewed evidence when review does not propagate.

What it would **not** do: unblock recommendations, accuracy, or anything client-facing. A reviewed
coverage measure is still a coverage measure.

It is **not approved here.** Like every lab write, it needs its own phase naming the writer, the
single record, the expected count (five → six), scope, idempotency key, receipts, verification, and
the durable no-cleanup posture decided in advance.

The alternatives are later, not rejected: a new evidence source only with explicit approval and no
invented cycle-count data; the DB-free packet bridge once there is enough evidence to make hand
assembly the constraint.

## 12. Stop conditions

- **No finding beyond what `evid_8151dad609974ea0` supports.**
- **No recommendation from unreviewed or low-reliability evidence.**
- No client-facing output.
- No DB access, no record creation, no migration `015`.
- **Stop if an unknown starts being stated as a fact** — accuracy, the system of record, or any of
  the untested mechanisms.

---

**Provenance.** Phase 108 re-exercised the reporting workflow DB-free against the Phase 107 evidence
reference, using the existing reporting prompt contract, registry entry, and mock executor. **No
database was contacted. No env file was read. No writer was invoked. No record was created — no
source, review, or evidence row. No migration `015` was created. No schema, model, enum, writer,
allowlist, gate, harness, prompt, test, tool, or Makefile changed.** `peak_lab` remains at **five
application rows by documented state only**; this phase did not connect to verify that.
`evid_8151dad609974ea0` **remains unreviewed.** The automated `EngagementPacket` path remains absent.
The mock executor planned only and generated no content. No real or pseudo-client data, row body,
data extract, model transcript, or planner dump appears here.
