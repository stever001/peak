# Intake Workflow Exercise — Consultant Intake Brief

**Status:** Internal Peak working document. DB-free and record-free. Non-authoritative. **Not
client-facing, not production evidence, not publication-ready.** The engagement below is a synthetic
internal test scenario — no client, real or invented, is described anywhere in this document.

This is the first exercise of one of Peak's ten consulting workflows end to end. It is meant to be
readable on its own.

---

## 1. What was exercised, and why intake

**Intake** — the first workflow in Peak's sequence, and the one everything downstream depends on.
Discovery was the alternative, but the discovery agent's stated job is to *turn intake into an
assessment plan*, so running it first would have meant inventing its input. Intake also had the most
complete existing support:

| Piece | Status |
|---|---|
| Prompt contract (`prompts/intake/normalize-client-intake.prompt.md`) | Complete and directly usable |
| Agent registry entry (`new_client_intake_agent`) | Present, points at that contract |
| Target schema (`schemas/client-intake.schema.json`) | Present — `ClientIntake` |
| Mock executor | Resolves the run, permits it, and executes nothing |

The mock executor was run against the intake agent. It confirmed the run is permitted, resolved the
prompt contract, and returned `planned_mock_no_execution` with `draft` / `needs_review` status and
every side-effect flag false — no LLM call, no AgentNet call, no database write, no client-facing
output. **That is the executor working as designed: it governs and plans a run; it does not produce
content.** The content work is carried by the prompt contract, performed by a person.

**What this exercise does not attempt:** persistence, a `ClientIntake` record, evidence capture,
assessment, scoring, recommendations, or anything client-facing. Intake precedes all of those.

## 2. The exercise input

A deliberately thin set of intake notes, of the kind a consultant actually gets off a first call:

> Warehouse operations group inside a distribution business. One site under discussion; there may be
> others. The operations manager says they "can't trust the on-hand numbers." Item master is
> maintained in more than one place, and it wasn't stated which one wins. Bin locations exist in the
> warehouse system, but the labels "don't always match the racks." Receiving and putaway are handled
> by different shifts, and putaway is sometimes recorded late or not at all. Trigger for the call was
> a failed cycle-count audit. No SKU count, headcount, systems by name, volumes, or financials were
> given. One stakeholder mentioned, by role only.

No company, industry, geography, size, or system name is stated — because none was given, and the
intake rules forbid supplying them.

---

## 3. Intake brief

### Engagement framing

A stated inventory-accuracy problem, with a specific business trigger (a failed cycle-count audit)
and three plausible contributing mechanisms already surfaced by the client's own words: **split item
master ownership**, **location labelling that disagrees with the physical racks**, and **putaway
recorded late or not at all**. None of those is yet established as a cause — they are the client's
framing, and they are where discovery should look first.

Scope is not yet defined. One site is under discussion; whether the engagement is one site or several
is an open question, and it changes the shape of everything downstream.

### Likely operational domains

Inventory accuracy and on-hand trust · item master quality · location/bin model integrity ·
receiving and putaway process · system-of-record ownership. Cycle counting is implicated by the
trigger but was not itself described.

### Source systems to ask about

Nothing can be listed here — **no system was named**. That is itself the first finding. Ask which
system holds on-hand quantity, which holds the item master, which holds the location model, and
which the floor actually trusts when two disagree. Those may be four different answers, and the gap
between the nominal and the trusted system of record is usually where accuracy problems live.

### Data readiness questions

- Which system is authoritative for on-hand quantity, and who decided that?
- Where is the item master maintained, in each of the places it is maintained, and which one wins
  when they disagree?
- Can a current on-hand extract be produced, and by whom, and how long does that take?
- Does every on-hand row carry both an item and a location, or can rows exist without one?
- Are there items with a complete-looking record that the floor still cannot use?

### Warehouse walk-around questions

- Do rack labels match what the system says is there — checked, not assumed?
- Are there physical areas with no system location at all (staging, returns, overflow, quarantine)?
- Where does stock sit between receipt and putaway, and is that location in the system?
- Can staff show a bin the system says is empty and one it says is full?

### Inventory accuracy questions

- What did the failed cycle-count audit actually measure, and against what?
- Is the failure concentrated in particular items, areas, or movement types — or spread evenly?
- Is the problem believed to be *count* accuracy, *location* accuracy, or both?
- What is the current cycle-count cadence and coverage, and who owns it?

### Receiving and putaway questions

- What is the intended receipt-to-putaway sequence, and how often does reality follow it?
- When putaway is recorded late, where does the system think the stock is in the meantime?
- Are there receipts with no corresponding putaway, and how would anyone notice?
- What happens on a shift handover mid-putaway?

### Item-master questions

- Which attributes are mandatory to create an item, and which are filled in later or never?
- Are there items whose data is internally contradictory rather than simply missing?
- Who can create an item, and is that different from who *should*?
- Are there duplicate items for the same physical thing?

### Location and bin questions

- Is there one location model or several, and does it match the physical layout?
- Are location codes structured (zone/aisle/rack/level) or free text?
- Are there locations in the system that no longer physically exist?
- When a label is wrong, what is the correction process, and does anyone follow it?

### Evidence needed

An on-hand extract with item and location; the item master with its completeness rules; the location
master; a receiving-to-putaway event history over a defined window; and the cycle-count results that
triggered the call. Each should arrive with a stated system of origin and an as-of time — an extract
with no known source and no timestamp cannot support a finding later.

### Risks and unknowns

- **Scope is undefined** — one site or many changes the engagement materially.
- **Nothing has been verified.** Every item above is the client's account of their own operation.
- **The stated causes may not be the real ones.** A failed audit is a symptom; three plausible
  mechanisms were volunteered, which is a reason to test them, not to accept them.
- **No volumes, headcount, or financials** — the engagement cannot yet be sized.
- **One stakeholder, by role.** Receiving, IT/systems, and whoever owns the item master have not been
  heard from, and they may not agree with the operations manager's account.

### Recommended discovery next steps

1. Settle scope: how many sites, and is this engagement one of them or all of them.
2. Establish the system-of-record map before requesting any data — an extract from the wrong system
   wastes the request.
3. Request the five evidence items above, with source and as-of time attached to each.
4. Interview receiving and systems separately from operations.
5. Walk the floor with the location model in hand and check labels against it directly.

### What not to conclude yet

Not that inventory accuracy is poor — that the client believes it is, and one audit says so. Not that
the item master is the cause. Not that the location model is broken. Not that putaway discipline is
the driver. Not that the problem is systemic rather than local to one area or one shift. And nothing
at all about size, effort, or value — no number in this brief is a measurement, because no
measurement has been taken.

---

## 4. Consultant handoff

**Ask next:** the scope question and the system-of-record question, in that order, before anything
else. Both are cheap to ask and both change what you request afterward.

**Request:** the five evidence items, each with a named source system and an as-of time.

**The next workflow — discovery — should produce:** a scoped assessment plan, an initial inventory
system profile, and an interview plan covering the three roles not yet heard from. It should not
produce findings; there is nothing to find from yet.

---

## 5. Product observations

**What worked.** The intake prompt contract is genuinely good and needed no changes. Its grounding
rules — use only what the notes contain, never fabricate names or numbers, keep pain points in the
client's framing, do not invent identifiers — are exactly the discipline this brief needed, and they
are what kept the "source systems" section honest instead of quietly filling it with plausible
warehouse software. The registry entry resolved cleanly and the executor's governance defaults
(`draft` / `needs_review`, no self-approval) are correct and unobtrusive.

**What was awkward.**

1. **The executor plans a run but cannot perform one.** This is documented and deliberate, but it
   means "exercise the intake workflow" today means "read the prompt contract and do the work by
   hand." That is a fine place to be; it is just worth naming plainly rather than implying the agent
   ran.
2. **The prompt's required output format is a JSON block, but the useful consulting artifact is a
   brief.** A `ClientIntake`-shaped JSON draft serves the schema and the future record; it is not
   what a consultant reads before a site visit. Both are legitimate outputs of the same step, and
   the contract currently names only one.
3. **When the notes are thin, the honest intake output is mostly questions** — which looks like
   failure and is not. The contract's "Missing information" section covers this, but nothing tells a
   consultant that a brief which is 70% questions is the correct result of a first call.

**Smallest useful product improvement:** add a short second output option to the intake prompt
contract — a consultant-readable brief alongside the JSON draft — and one line noting that a
question-heavy result is expected from thin notes. That is a prompt edit, not a framework. **It was
not made in this phase**, because the exercise ran fine without it and the change should be its own
small, deliberate decision.

## 6. Stop conditions

- Do not add a `ClientIntake` record, or any record, to make this artifact feel more complete. It is
  complete; it is a brief, and briefs precede records.
- Do not add a harness for this phase.
- Do not add migration `015`.
- Do not treat any of this as client-ready. It is a working document about a synthetic scenario.

---

**Provenance.** Produced by exercising Peak's existing intake prompt contract, agent registry entry,
and mock executor against a synthetic internal test scenario. **No database was contacted. No env
file was read. No writer was invoked. No record was created. No migration `015` was created. No
schema, model, enum, writer, allowlist, gate, or harness changed.** `peak_lab` remains at four
application rows by documented state only; this phase did not connect to verify that. No real or
pseudo-client data was used, and no model transcript, fixture, packet, or data extract is reproduced
here.
