# Controlled Lab Chain Viability — Internal Consultant Memo

**Status:** Internal Peak memo. DB-free and record-free. Non-authoritative. **Not client-facing, not
production evidence, not publication-ready.** Nothing in here may be quoted to a client, and no
figure in it describes any real warehouse.

---

## Executive summary

Peak carried one controlled measurement all the way through its own pipeline — from a lab source,
into a source-ingestion record, into an evidence reference, into a review, into the assessment
planner, and out into this memo. Every hand-off held.

**The finding is narrow and it is about Peak, not about inventory.** What the exercise shows is that
Peak can carry a limited, clearly-labelled claim across five hand-offs without the claim quietly
growing. The measurement went in described as *internal, synthetic, partial, and not client
evidence*, and it came out the far end still described that way. That is worth knowing, because the
failure mode we were testing for — a hedged observation hardening into a confident conclusion as it
moves between systems — is the one that would actually hurt a client engagement.

**It shows nothing about inventory.** It does not establish inventory accuracy, source-system truth,
operational correctness, client readiness, production readiness, capsule readiness, or AgentNet
publication readiness. The material was a synthetic scenario built to be measurable, not a
warehouse.

## What was measured

A single lab scenario, read-only, across the readiness dimensions Peak cares about in a real
assessment:

- **Source-system map** — which system is the authority for which domain.
- **Item master** — whether SKU records are complete enough to rely on.
- **Location model** — whether the bin/location structure resolves.
- **Inventory snapshot** — whether on-hand rows can be attributed to a SKU and a place.
- **Receiving and putaway** — whether receipt-to-putaway events are usable.
- **Derived readiness** — what falls out of the above when combined.

**Every dimension came back *partial*. None was clean, and none was empty** — by design, since a
dataset where everything resolved could not demonstrate that a readiness check works at all.

Two results are worth a consultant's attention because they generalize beyond the lab:

**Coverage is not accuracy.** Every inventory row resolved to a SKU, which sounds like good news
until you add location: a meaningful share of rows could not be placed, and once item-master quality
and quantity presence were also required, fewer than half the rows survived. A readiness number that
counts one attribute at a time will always flatter the data.

**Presence is not usability.** One item carried every required attribute and was still unusable,
because its data was internally contradictory rather than missing. A presence-only rule over-counted
usable items by roughly one in ten. **Any readiness rule Peak builds has to read the completeness
classification, not just check that fields are populated.**

All figures here are internal synthetic lab values. None is a benchmark, a projection, or a client
finding.

## What the chain proves

- One lab source can be represented as a source-ingestion record.
- One evidence reference can carry a narrow internal finding boundary.
- One review record can supply review support at the category level.
- The planner can consume the whole chain with no database access at all.
- A memo can be written off that plan that states the boundary without overclaiming.

In short: **the plumbing works, and it does not leak claims.**

## What the chain does not prove

Not inventory accuracy. Not complete data readiness. Not source-system truth — the authority map was
measured, not settled, and remains unconfirmed. Not client evidence. Not production evidence. Not
authoritative evidence; the review was deliberately recorded as non-authoritative. Not recommendation
support. Not capsule readiness. Not AgentNet publication readiness.

The review also did **not** propagate approval anywhere. It records a decision *about* the evidence;
it did not change it.

## The catch a consultant must not miss

The planner marked seven of its fourteen sections "ready." **That is not the good news it looks
like.**

"Ready" means *the required kind of reference exists*. It does not mean *there is enough evidence to
write the section*. Underneath those seven ready sections there are only **three** references in
total: four of the sections rest on the same single evidence reference, two rest on the same single
source record, and every one of them has a supporting-reference count of exactly **one**.

**Before drafting from any section, check its support count and evidence trace.** Four sections
sharing one piece of evidence are one finding wearing four hats. Treating them as four independent
findings would manufacture breadth that does not exist — and it is the same trap as the
presence-vs-usability problem in the item master, one layer up.

**One finding slot is the honest ceiling here.** The planner offered exactly one, and that is
correct.

## The practical finding

> Peak's current lab chain is sufficient to support a limited internal finding: the platform can
> preserve a controlled, non-authoritative claim boundary from measured lab input, through source
> ingestion, evidence reference, and review support, into planner recognition and memo drafting.

It cannot support anything wider. It cannot support a second independent finding, a recommendation,
a client-facing statement, or any conclusion about a real inventory operation. One source, one piece
of evidence, one review — and one finding.

## How to use this internally

Use it as a **worked example of claim discipline** — how Peak structures evidence so that a narrow
observation stays narrow. It is a good internal teaching artifact and a reasonable reference when
explaining to a colleague why an assessment section needs its own evidence rather than borrowing a
neighbour's.

Do not use it as a client deliverable, a template for client language, or a demonstration that Peak
has measured anything about a real warehouse.

## Recommended next work

**Exercise one real consulting workflow end to end and produce something a consultant would actually
hand to a colleague.** Intake or discovery is the natural place to start: prompts and agent registry
entries already exist for both, and there is a mock executor to run them against.

Keep it DB-free unless the workflow genuinely needs persistence. The output should be a
consultant-usable artifact — a structured intake summary, a discovery plan — not another proof that
the machinery is safe. The machinery's safety is well established by now. Its usefulness is what
remains unproven.

## Stop conditions

Stop and reconsider if a proposed next phase:

- adds a harness, gate, migration, or record without a specific workflow that needs it;
- produces another document about governance instead of an artifact a consultant can use; or
- treats a "ready" planner section as sufficient without checking its support count and evidence
  trace.

---

**Provenance.** Written from Peak's existing internal records of the lab chain — the engagement
anchor, source-ingestion record, evidence reference, and review record — and the DB-free planner run
over them. **No database was contacted. No env file was read. No writer was invoked. No record was
created. No migration `015` was created. No schema, model, enum, writer, allowlist, gate, or harness
changed.** `peak_lab` remains at four application rows by documented state only; this memo did not
connect to verify that.
