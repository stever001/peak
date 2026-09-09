# Evidence Normalization Exercise — Preparing Requested Evidence for Use

**Status:** Internal Peak working document. DB-free and record-free. Non-authoritative. **Not
client-facing, not production evidence, not publication-ready.** The engagement is a synthetic
internal test scenario — no client, real or invented, is described, and no system, count, volume,
headcount, or financial figure has been supplied or inferred.

This is the third consulting workflow exercised end to end. It reads on its own.

---

## 1. Workflow selected, and the stage problem it exposed

**Evidence normalization**, which follows discovery because discovery decides *what to ask for* and
this step decides *what the answers can be used to say*.

| Piece | Status |
|---|---|
| Prompt contract (`prompts/evidence/extract-evidence-findings.prompt.md`) | Complete and usable |
| Agent registry (`evidence_normalization_worker`) | Present, points at that contract |
| Declared input | An `EngagementPacket` with **discovery already populated** — `evidence_references[]`, interviews, observations |
| Declared output | Evidence-backed findings in five groups, each citing at least one `evid_` id, plus an "Unsupported items" list |

**The contract is a *post*-collection step, and this engagement has collected nothing.** Discovery
produced a request list, not evidence. The prompt's central rule is that every finding must cite an
`evid_` id that exists in the packet, and that anything without one becomes an *Unsupported item*
rather than a finding. Run as written against this chain, it would correctly return **zero findings
and a long Unsupported list** — the contract working exactly as designed, on an engagement that is
not ready for it yet.

So this exercise does the step that actually comes next: **preparing the requested evidence for
use** — deciding, before anything arrives, what each item will and will not be allowed to support.
That work has to happen anyway, and doing it in advance is what stops a spreadsheet arriving on a
Tuesday from becoming a finding by Thursday.

## 2. Input used

The intake brief and the discovery plan from the two previous exercises, unchanged: on-hand balances
not trusted, triggered by a failed cycle-count audit, with three client-volunteered mechanisms —
split item-master ownership, bin labels disagreeing with the racks, and putaway recorded late or not
at all. One stakeholder, by role. **No system was named. No SKU count, volume, headcount, site size,
or financial figure was given.** The nine-item evidence request list comes from the discovery plan.

Those absences are carried forward. Nothing here converts one into a fact.

## 3. Mock executor result

The evidence agent was run through the mock executor. It resolved the prompt contract
(`exists: True`), permitted the run, and returned `planned_mock_no_execution` at `draft` /
`needs_review`, with `llm_call_made`, `agentnet_call_made`, `database_write_made`,
`client_facing_output_created`, and `resolver_context_used` all **false**.

**The executor planned the run; it generated none of the content below.** This plan was written from
the prompt contract and the two prior artifacts by hand, as the previous two exercises were.

---

## 4. Normalization plan, by evidence item

Every item below needs two things before it is usable at all: **the system it came from**, named by
someone who knows, and **an as-of time or period**. An extract with neither cannot support a finding
later, and re-requesting it costs a week.

### Item master export

**Why:** tests the split-ownership and contradictory-data mechanisms the client raised.
**Ask for:** the export, the completeness rules that govern item creation, and who can create an item.
**Inspect:** which attributes are mandatory versus filled later; items complete on their face but
internally contradictory; duplicates for the same physical thing; retired items still active.
**Supports:** a statement about item-master *completeness and internal consistency*.
**Cannot alone:** prove inventory is wrong, or that the item master is the cause of the audit
failure. It is one input to accuracy, not accuracy.
**Normalize:** classify each item as complete / incomplete / contradictory rather than counting
populated fields — a contradictory record is unusable even when full.
**Follow up:** if maintained in more than one place, get the same items from each and compare.

### Current inventory by SKU and location

**Why:** the core artefact; everything else is read against it.
**Ask for:** on-hand by item and location, with the system named and an as-of timestamp.
**Inspect:** rows that resolve to an item but not a location, or neither; rows with no quantity or
negative quantity; the oldest untouched balance.
**Supports:** a statement about *attributability* — how much of the on-hand picture can be placed.
**Cannot alone:** establish accuracy. A row that resolves perfectly can still be wrong; only a count
against the physical world speaks to that.
**Normalize:** report attributable / not-attributable with the reason for each failure, and keep
those reasons separate — a missing location and a dangling location are different problems.
**Follow up:** ask whether stock is held in more than one system, and whether those are reconciled.

### Receiving history

**Why:** the front of the flow; everything downstream inherits its timing.
**Ask for:** a defined window, with the trigger that causes a receipt to be recorded.
**Inspect:** receipts with no corresponding putaway; the gap between physical arrival and system
record; what happens when paperwork and delivery disagree.
**Supports:** a statement about *receipt recording discipline* within the window.
**Cannot alone:** prove stock is misplaced. It shows when the system learned about stock, not where
the stock is.
**Normalize:** pair every receipt with its putaway or mark it unpaired; keep the window explicit,
because a short window over a quiet period proves little.
**Follow up:** ask whether the window given is representative or was chosen for being clean.

### Putaway history

**Why:** tests the client's own timing hypothesis directly.
**Ask for:** the same window as receiving, so the two can be paired.
**Inspect:** recording lag relative to the physical move; putaways never recorded; behaviour at
shift handover; unresolvable target locations.
**Supports:** a statement about *putaway recording lag and completeness*.
**Cannot alone:** prove that lag caused the audit failure. It establishes a window in which the
system's location is unreliable, which is a mechanism, not a measurement of harm.
**Normalize:** treat late recording as **process-risk evidence**, not as inventory error. The two
are related and are not the same claim.
**Follow up:** where does stock physically sit during the gap, and is that place a system location?

### Location / bin master, and a physical map if one exists

**Why:** tests the label-versus-rack mechanism.
**Ask for:** the location master, plus any layout map, plus the correction process for a wrong label.
**Inspect:** whether codes are structured or free text; system locations that no longer exist;
physical areas with no system location — staging, returns, overflow, quarantine, damage.
**Supports:** a statement about *location-model completeness and structure*.
**Cannot alone:** establish that labels disagree with racks. That is a floor observation; the master
only shows what the system believes.
**Normalize:** keep model-side gaps separate from floor-side gaps. They need different fixes.
**Follow up:** walk a sample with the model in hand, in more than one zone, including an untidy one.

### Cycle-count results, including the audit that triggered the call

**Why:** the only artefact that speaks to accuracy, and the reason the engagement exists.
**Ask for:** the results, the count design, the coverage, and what each count compared against.
**Inspect:** what "failed" meant; whether variance is concentrated by area, item type, or movement
rate; who investigates a variance and what happens next.
**Supports:** a statement about *measured variance within the counted population*, and about whether
the control is designed to catch what it is being asked to catch.
**Cannot alone:** support a site-wide accuracy rate unless coverage supports it. A count of part of
the site describes that part.
**Normalize:** always carry the counted population alongside the result. A variance rate without its
denominator is not a finding.
**Follow up:** is the counted population representative, or the easiest to count?

### Adjustment history

**Why:** shows where corrections are already being made, by whom, and how often — often the clearest
signal of where the system is not trusted.
**Ask for:** the history with reason codes, over the same window.
**Inspect:** concentration by area, item, or user; adjustments without a reason code; whether
adjustments cluster before or after counts.
**Supports:** a statement about *where and how often the record is being corrected*.
**Cannot alone:** prove root cause. An adjustment records that something was wrong, not why.
**Normalize:** treat adjustments as a symptom map, not a fault list.
**Follow up:** ask who can adjust, and whether that differs from who should.

### System-of-record ownership explanation, in writing

**Why:** removes the largest ambiguity in the engagement. Without it, every extract above is of
uncertain provenance.
**Ask for:** which system is authoritative for on-hand, for the item master, and for locations; who
decided; and what happens when they disagree.
**Inspect:** whether the nominal authority matches the one the floor actually believes; interfaces
between systems and how they fail.
**Supports:** the *authority map* that lets every other item be interpreted.
**Cannot alone:** prove any system is correct. It establishes which one is supposed to be.
**Normalize:** record it as a stated map with its source, not as verified truth. **Where accounts
conflict, that is an authority question to resolve, not yet a finding.**
**Follow up:** ask management and the floor separately, and note divergence.

### SOPs / work instructions, if they exist

**Why:** separates intended process from actual.
**Ask for:** receiving, putaway, and counting procedures, with their last review date.
**Inspect:** whether documented steps match what the histories show; whether staff have seen them.
**Supports:** a statement about the *gap between documented and observed process*.
**Cannot alone:** show what people actually do. A current SOP and a non-compliant floor are a common
pairing.
**Normalize:** hold the SOP as the intended-state reference, never as evidence of behaviour.
**Follow up:** if none exist, that is itself worth recording — say it plainly rather than omitting it.

---

## 5. Claim boundary rules

These govern everything above, and they are the part worth carrying into every engagement:

1. **Evidence supports only the claim it can actually carry.** Ask "what would I have to also know
   for this to be true?" before writing a finding.
2. **Field presence is not usability.** A record with every attribute populated can still be
   unusable if those attributes contradict each other. Read the completeness classification, not the
   fill rate.
3. **Coverage is not accuracy.** Attributing every row to a SKU says nothing about whether the
   quantity is right.
4. **A source name is not authority.** Knowing which system an extract came from is necessary; it
   does not make that system the system of record.
5. **Late or missing process records are process-risk evidence, not proof of inventory error.** They
   establish a window of unreliability, which is a mechanism, not harm.
6. **Conflicting sources raise an authority question before they raise a finding.** Resolve who is
   supposed to be right before deciding who is.
7. **Freshness is part of the evidence.** Every operational extract carries an as-of time or period,
   and a claim inherits the age of its weakest input.

## 6. Handoff to the next workflow

What reporting should receive, and in this shape:

- **Normalized evidence inventory** — what arrived, and what each item is allowed to support.
- **Source and as-of metadata** on every item, with gaps flagged rather than assumed.
- **Unresolved authority questions**, listed separately from findings.
- **Candidate claim boundaries** — the sentence each item could support, written out.
- **Missing evidence list** — what was requested and did not arrive, and what that blocks.
- **Hypotheses to validate on the floor**, still labelled as hypotheses.
- **Items safe for internal finding candidates** — those with a named source, an as-of time, and a
  claim that does not depend on evidence that has not arrived.
- **Items not safe for recommendation candidates yet** — anything resting on a single source, an
  unresolved authority question, or an unrepresentative population. Expect most items to sit here at
  this stage, and say so rather than promoting them.

## 7. Product observations

**What worked.** The evidence prompt is well built for the job it names. Its four-way split —
observed evidence, stakeholder claim, consultant interpretation, recommended follow-up — is the
single most useful discipline in the prompt set, and its refusal to let an uncited item become a
finding is exactly right.

**The stage gap.** The contract begins where evidence already exists. Between discovery's request
list and that starting point there is a step — deciding what each item will be allowed to support —
that no contract currently names. It is real consulting work, it is what this document is, and
nothing in the repo asked for it.

**A smaller mismatch.** The registry describes `evidence_normalization_worker` as normalizing
"heterogeneous inputs into traceable evidence and candidate issues," which reads like the
pre-collection job. The contract behind it does post-collection findings extraction. The description
and the contract are describing different steps.

**Did the Phase 103 seam closure help?** Not directly — that seam was intake → discovery, and this
hand-off is discovery → evidence. But it helped in a way worth noting: because discovery could take
the intake brief, the discovery plan carried its evidence request list forward in usable prose, and
that list is what this document normalizes. The chain held.

**Smallest suggested improvement:** a short "before evidence arrives" section in the evidence prompt
contract, naming the per-item claim boundary as a preparation output. That is the third prompt note
in four phases; **it should not be made piecemeal.** Better to collect it with any others and decide
once, as Phase 103 did with two.

## 8. Recommended next step

**Exercise the reporting / initial assessment draft workflow DB-free**, using this plan as input.
That will test whether the chain can carry a bounded claim into a draft without collected evidence —
and it will most likely surface the same shape as here: the reporting contract expects findings that
do not exist yet.

If that proves true, the honest read is that **the chain is now blocked on evidence rather than on
contracts**, and the next real step is a decision about producing evidence — not another prompt edit
and not another docs-only exercise.

## 9. Stop conditions

- Do not create records to make the evidence picture look complete. Nothing has been collected;
  a record would be manufacturing the thing that is missing.
- Do not add a harness, a gate, or migration `015` for this.
- Do not use any of this with a client.
- **Stop if an unknown starts being repeated as a fact** — the systems, the site count, or the three
  mechanisms.
- **Stop if an evidence category is treated as authoritative before the system-of-record question is
  answered.**

---

**Provenance.** Produced by exercising Peak's existing evidence prompt contract, agent registry
entry, and mock executor against the intake brief and discovery plan from the two previous
exercises. **No database was contacted. No env file was read. No writer was invoked. No record was
created. No migration `015` was created. No schema, model, enum, writer, allowlist, gate, or harness
changed, and no prompt or source file was modified.** `peak_lab` remains at four application rows by
documented state only; this phase did not connect to verify that. No real or pseudo-client data was
used, and no model transcript, fixture, packet, or data extract is reproduced here.
