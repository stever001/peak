# Discovery Workflow Exercise — Scoped Assessment and Interview Plan

**Status:** Internal Peak working document. DB-free and record-free. Non-authoritative. **Not
client-facing, not production evidence, not publication-ready.** The engagement is a synthetic
internal test scenario — no client, real or invented, is described here, and no system, count,
volume, headcount, or financial figure has been supplied or inferred.

This is the second consulting workflow exercised end to end. It reads on its own.

---

## 1. Workflow selected

**Discovery**, which follows intake because its whole job is to turn intake into a plan for the first
site visit. Support found in the repo:

| Piece | Status |
|---|---|
| Prompt contract (`prompts/discovery/generate-discovery-plan.prompt.md`) | Complete and directly usable |
| Agent registry (`discovery_planning_agent`) | Present, points at that contract |
| Second discovery agent (`interview_structuring_assistant`) | Present, but **no prompt contract** — `prompt_contract_path` is `None` |
| Declared input | An `EngagementPacket` JSON, minimum `client_intake` |
| Declared output | Interview plan · walk-around checklist · data request list · risks to validate · sharpened first-tranche objective |

## 2. Input used

The intake brief from the previous exercise, unchanged: a warehouse operations group reporting that
they cannot trust on-hand numbers, triggered by a failed cycle-count audit, with three mechanisms
volunteered by the client — split item-master ownership, bin labels disagreeing with the racks, and
putaway recorded late or not at all. One stakeholder, by role. **No system was named. No SKU count,
volume, headcount, site size, or financial figure was given.**

Those absences are carried forward as unknowns. Nothing in this plan converts one into a fact.

## 3. Mock executor result

The discovery agent was run through the mock executor. It resolved the prompt contract
(`exists: True`), permitted the run, and returned `planned_mock_no_execution` at `draft` /
`needs_review`, with `llm_call_made`, `agentnet_call_made`, `database_write_made`,
`client_facing_output_created`, and `resolver_context_used` all **false**. `discovery_planning_agent`
is flagged `resolver_context_future=True`, but resolver context was not requested and none was
routed.

**The executor planned the run; it did not generate any of the content below.** The plan was written
from the discovery prompt contract and the intake brief, by hand. That is how this workflow currently
runs.

---

## 4. Scoped assessment plan

### Objective

Determine **why** on-hand balances are not trusted, and whether the cause is counting, location
integrity, item-master quality, putaway timing, or system-of-record ambiguity — far enough to
recommend a corrective path and size the work.

Note what is *not* the objective: proving the balances are wrong. One failed audit already suggests
that. The value is in the mechanism.

### Scope boundaries

- **One site**, unless discovery establishes otherwise — the number of sites is still open and is the
  first question to settle, because it changes everything downstream.
- **In scope:** inventory accuracy, item master, location model, receiving and putaway, cycle
  counting, and system-of-record ownership across those.
- **Out of scope for now:** demand planning, purchasing, labour productivity, slotting optimisation,
  and anything financial. They may surface; they are not what was asked about.
- **Assessment only.** No remediation, no system changes, no process rollout.

### Operational domains to examine

Inventory accuracy and adjustment behaviour · item-master completeness and consistency · location and
bin model integrity · receiving-to-putaway flow and timing · cycle-count design and coverage ·
system-of-record ownership across all of the above.

### Expected evidence categories

Master data (items, locations) · transactional history (receipts, putaways, adjustments) · current
state (on-hand by item and location) · control results (cycle counts) · process documentation ·
and stated ownership of each system. Every one needs a named source and an as-of time.

### Source-system discovery questions

- Which system holds on-hand quantity, and which holds the item master, and which holds the location
  model? These may be three different answers.
- When two systems disagree, which one does the floor actually believe — and is that the same one
  management would name?
- Who owns each system, and who can change data in it?
- Is there an interface between them, and does it run on a schedule or on demand?
- What happens to a transaction when an interface fails?

### Item-master discovery questions

- Which attributes are mandatory at item creation, and which get filled in later or never?
- Are there items whose data is internally contradictory rather than merely incomplete?
- Are there duplicate items representing the same physical thing?
- Who can create an item, and is that the same set of people who should?
- Is there a retirement process for items no longer stocked?

### Location and bin discovery questions

- Is there one location model or several, and does it match the physical layout?
- Are location codes structured, or free text?
- Are there physical areas with no system location — staging, returns, overflow, quarantine, damage?
- Are there system locations that no longer physically exist?
- What is the process when a label is found wrong, and does anyone follow it?

### Inventory snapshot discovery questions

- Can every on-hand row be attributed to both an item and a location, or can rows exist without one?
- Are there on-hand rows with no quantity, or negative quantity?
- How old is the oldest untouched balance?
- Is stock held in more than one system, and are those balances reconciled?

### Receiving and putaway discovery questions

- What is the intended receipt-to-putaway sequence, and how often does reality follow it?
- When putaway is recorded late, where does the system believe the stock is meanwhile?
- Are there receipts with no corresponding putaway, and would anyone notice?
- What happens at a shift handover mid-putaway?
- Is there a physical staging area, and is it a system location?

### Walk-around observations to capture

- Whether rack labels match the system — checked directly on a sample, not assumed.
- Physical areas holding stock with no corresponding system location.
- Where stock actually sits between receipt and putaway.
- A bin the system says is empty, and one it says is full.
- Any local paper or spreadsheet tracking running alongside the system — these usually mark where the
  system is not trusted.
- General condition and legibility of labelling across zones, not just the tidy ones.

### Preliminary risk themes — hypotheses to validate, not findings

1. **Split item-master ownership produces conflicting item records.** → Confirm by identifying every
   place the item master is maintained and comparing the same items across them.
2. **The location model has drifted from the physical layout.** → Confirm by sampling labels against
   the system on the walk-around, in more than one zone.
3. **Putaway timing creates a window where the system location is wrong.** → Confirm from receipt-to-
   putaway timestamps and the count of receipts with no putaway.
4. **Cycle counting is measuring the wrong thing, or too little of it.** → Confirm from count design,
   coverage, and what the failed audit actually compared.
5. **The nominal system of record is not the trusted one.** → Confirm by asking management and the
   floor the same question separately.
6. **Accuracy problems are concentrated, not uniform.** → Confirm by segmenting count results by
   area, item type, and movement rate.

### What not to conclude yet

Not that inventory accuracy is poor — that the client believes it is, and one audit agrees. Not that
any of the six hypotheses is the cause; none has been tested. Not that the problem is systemic rather
than local to one zone or one shift. Not that any system is deficient — none has been named. And
nothing about effort, duration, or value: no number in this plan is a measurement.

### First-tranche objective

**Cannot be sharpened yet, and was deliberately not invented.** The intake carried no stated billing
objective, so there is nothing to restate. What would define it: the site count, whether the client
wants a diagnosis or a remediation plan, and how much data access is available before the visit. Ask
those three, and the objective writes itself.

---

## 5. Interview plan

Roles only. No individuals were named in intake, and none is named here.

| Role | Purpose | Key questions | Evidence to request | What would change the assessment path |
|---|---|---|---|---|
| **Operations leader** | Settle scope and hear the business version of the problem | How many sites, and is this one or all? What triggered the audit? What does "can't trust the numbers" cost you today? What has already been tried? | Site list; the audit result that triggered the call | More than one site in scope, or a remediation attempt already underway |
| **Warehouse supervisor** | Get the floor's version, which often differs | Where do the numbers go wrong most? Which areas do you not trust? What do you do when the system is wrong? | Any local tracking kept outside the system | A workaround in daily use — it marks the real failure point |
| **Inventory control / cycle-count owner** | Understand what the control actually measures | What does a count compare against? What is the cadence and coverage? Who investigates a variance, and what happens then? | Cycle-count results and adjustment history | Counts covering only part of the site, or variances closed without investigation |
| **Receiving lead** | Establish the front of the flow | What happens between truck and system? Where does stock sit before putaway? What happens if the paperwork disagrees? | Receiving history for a defined window | Receipt recorded on a different trigger than physical arrival |
| **Putaway / replenishment lead** | Test the timing hypothesis directly | When is putaway recorded relative to the physical move? What happens at shift change? Are there putaways that never get recorded? | Putaway history over the same window | A systematic recording lag, rather than occasional lapses |
| **Systems / data owner** | Resolve the system-of-record question | Which system is authoritative for which data? Where is the item master maintained? What interfaces exist and how do they fail? Who can change master data? | Item master, location master, system ownership map | Master data maintained in more places than operations believes |

**Sequence matters:** operations leader first (scope), systems owner second (so data requests go to
the right system), floor roles after. Interview the floor separately from management — where those
two accounts diverge is usually the most useful finding of the week.

## 6. Evidence request list

Each item needs a **named source system** and an **as-of timestamp**. An extract with neither cannot
support a finding later, and re-requesting it costs a week.

| Item | Why it matters | Maps to |
|---|---|---|
| Item master export, with the completeness rules that govern it | Tests the split-ownership and contradictory-data hypotheses | Item master; hypothesis 1 |
| Current on-hand by item and location | The core artefact; tests attributability | Inventory snapshot; hypothesis 6 |
| Receiving history, defined window | Front of the flow | Receiving; hypothesis 3 |
| Putaway history, same window | Timing hypothesis; pairs with receiving | Putaway; hypothesis 3 |
| Location / bin master, plus a physical map if one exists | Tests model-versus-reality drift | Location model; hypothesis 2 |
| Cycle-count results, including the audit that triggered the call | Shows what the control measures and what it found | Cycle counting; hypotheses 4, 6 |
| Adjustment history | Where corrections are already being made, and by whom | Accuracy; hypothesis 6 |
| System-of-record ownership explanation, in writing | Removes the largest ambiguity in the engagement | All domains; hypothesis 5 |
| SOPs or work instructions for receiving, putaway, and counting, if they exist | Separates intended process from actual | Process; hypotheses 3, 4 |

If only two can be obtained before the visit, take the **on-hand extract** and the **system-of-record
explanation**. Without the second, the first cannot be interpreted.

## 7. Consultant handoff

**Do next:** ask the site-count question and the system-of-record question before requesting any
data. An extract pulled from the wrong system wastes a week and teaches nothing.

**Request first:** on-hand by item and location, and the written system-of-record explanation.

**Avoid overclaiming:** the six risk themes are hypotheses, and the plan says so in every place they
appear. None may be repeated as a finding until discovery tests it. Nothing here is a measurement.

**The next workflow — evidence normalization — should produce:** structured evidence references from
what discovery actually collects, each tied to a named source and an as-of time, with the claim
boundary set at what the evidence supports and no wider.

## 8. Product observations

**What worked.** The discovery prompt contract is well built and needed no change. Its grounding
rules — plan from the intake, label extrapolation as a hypothesis rather than a finding, never invent
stakeholders or metrics — are what kept the six risk themes honest and what stopped the first-tranche
objective from being fabricated. Its declared output shape (interview plan, walk-around checklist,
data request list, risks, tranche objective) is the right shape for the job.

**What was awkward — one real seam.** The discovery prompt's declared input is an `EngagementPacket`
JSON containing a `client_intake`. Intake's useful human output is a brief. **Nothing converts one to
the other**, so running discovery from the previous exercise meant supplying the brief where a packet
was specified. The substance was all present and the grounding rules are about substance, so this was
not blocking — but the chain has a format seam at exactly the hand-off the workflows are supposed to
make routine. `tools/packet_runner.py` is the natural bridge and reads a packet file, but it needs a
packet that nothing currently produces.

**Second, smaller.** `interview_structuring_assistant` is registered as a discovery agent with
`prompt_contract_path` set to `None`. The interview plan above came from the planning prompt's own
interview table, which covers it — so the registry entry currently promises a capability that has no
contract behind it.

**Smallest useful product improvement:** note in the discovery prompt contract that a consultant
intake brief is acceptable input where no packet exists yet. One or two lines, no behaviour change,
and it closes the seam for the way the workflow is actually run today. **Not made in this phase** —
it touches a prompt, and it should be its own deliberate decision alongside the intake-prompt note
still outstanding from the previous exercise.

## 9. Stop conditions

- Do not create records to make this plan look more complete. A discovery plan precedes evidence by
  definition.
- Do not add a harness, a gate, or migration `015` for this.
- Do not use any of this with a client.
- **Stop if an unknown starts being repeated as a fact** — particularly the site count, the systems,
  or any of the six hypotheses.

---

**Provenance.** Produced by exercising Peak's existing discovery prompt contract, agent registry
entry, and mock executor against the intake brief from the previous exercise. **No database was
contacted. No env file was read. No writer was invoked. No record was created. No migration `015` was
created. No schema, model, enum, writer, allowlist, gate, or harness changed, and no prompt or source
file was modified.** `peak_lab` remains at four application rows by documented state only; this phase
did not connect to verify that. No real or pseudo-client data was used, and no model transcript,
fixture, packet, or data extract is reproduced here.
