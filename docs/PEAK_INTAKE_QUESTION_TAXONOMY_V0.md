# Peak Intake Question Taxonomy — V0

**Status: V0. This is not the final client-facing questionnaire.** It is the working structure a
questionnaire gets *generated from*. Wording, ordering, question count, conditional logic, and
tone are all still open; what is settled is the **derivation rule** below.

---

## The derivation rule

**A Peak intake question is justified only when it supports a downstream decision, evidence need,
report section, or readiness judgment.** Intake questions are not arbitrary form fields, and they
are not a checklist copied from an industry template. They are *derived backwards* from what Peak
actually has to produce:

- an **inventory / warehouse operations assessment**
- a **prioritized improvement plan**
- an **evidence map**
- a **data / source quality review**
- an **AI / AgentNet readiness view**
- **future capsule / publication readiness**

If a proposed question cannot be traced to at least one of those six, it does not belong on the
form — however natural it sounds. The test is not "would a consultant ask this?" but "what changes
in a deliverable depending on the answer?"

This inverts the usual failure mode. A form built forwards ("what should we ask about
inventory?") collects fields nobody consumes, and still misses the input a report section needs.
A form built backwards from deliverables collects less and covers more.

## The categories

Each category names what it feeds. The **Feeds** column is the justification; a category with no
downstream consumer would be cut.

### 1. Engagement context
Scope, parties, authorization, timeframe, and what the engagement is *for*.
**Feeds:** scoping, authorization posture, and report framing. Determines what may be gathered at
all, and how findings are addressed.

### 2. Current inventory pain points
What hurts today, in the operator's own words, and how they'd rank it.
**Feeds:** assessment priorities and improvement-plan focus. Establishes the initial hypothesis the
evidence then confirms or contradicts.

### 3. Item / SKU master and product-data quality
Identifier discipline, duplicates, units of measure, attribute completeness, ownership of the item
master.
**Feeds:** inventory accuracy findings, data readiness, and future capsule readiness. Product data
that is inconsistent for humans is unusable for machines.

### 4. Warehouse / facility / location structure
Sites, zones, bins, location naming, and whether the physical layout matches the recorded one.
**Feeds:** operational assessment and evidence normalization. Without a location model, evidence
cannot be attributed to a place.

### 5. Receiving, putaway, picking, packing, shipping
The actual flow of goods, step by step, including where it deviates from the documented flow.
**Feeds:** workflow and process evaluation. This is where most improvement-plan items originate.

### 6. Cycle counts, physical counts, adjustments, shrink
Counting cadence, coverage, adjustment authority, reason-code discipline, and shrink visibility.
**Feeds:** control-risk and accuracy assessment. Adjustment practice is often the fastest read on
whether recorded inventory can be trusted.

### 7. Stockouts, overstocks, obsolete and slow-moving inventory
Frequency, cause, cost, and how each is currently detected.
**Feeds:** service-level and working-capital findings. Connects operational symptoms to money.

### 8. Systems of record
Which system is authoritative for what, where authority is ambiguous, and where two systems
disagree.
**Feeds:** authority and source-of-truth decisions. Every later evidence claim depends on knowing
which system wins.

### 9. Data exports and reporting
What can be exported, in what format, at what cadence, by whom, and what is already reported on.
**Feeds:** evidence ingestion and quantitative review. Determines whether findings can be measured
or only described.

### 10. SOPs, approvals, exceptions, workarounds
Documented procedure versus practiced procedure, who approves what, and which workarounds have
become permanent.
**Feeds:** process maturity and governance findings. The gap between documented and practiced is
itself a finding.

### 11. Evidence availability
What documentation, records, screenshots, exports, and system access actually exist and can be
shared.
**Feeds:** source ingestion and evidence-normalization planning. Sets the realistic ceiling on how
well-evidenced the assessment can be.

### 12. AI / AgentNet readiness
Whether workflows, data, and documentation are machine-readable and machine-actionable; where a
human step is load-bearing.
**Feeds:** machine-readable workflow and capsule-readiness assessment. Readiness is a finding in
its own right, not a bolt-on.

### 13. Publication and capsule boundaries
What is confidential, what could be shared, what is already public, and who decides.
**Feeds:** what may later become public, private, publishable, superseded, or withheld. Captured at
intake because reconstructing publication authority afterwards is unreliable.

### 14. Success metrics and urgency
How the client will judge the engagement, what the deadline is, and what a good outcome looks like.
**Feeds:** prioritization and engagement outcomes. Determines the order of the improvement plan,
not just its contents.

## How this gets used

Future client-facing intake forms should be **generated from this taxonomy, not guessed**. The
taxonomy is the source; a form is a rendering of it for a particular engagement type, depth, and
audience. When a form question exists that maps to no category, either the taxonomy is missing a
downstream need or the question should be cut — and that is a decision to make deliberately.

## The same strategy applies to GeoSites later

The reusable asset here is the **strategy**, not the inventory-specific category list. A future
GeoSites intake should replicate this approach: derive its questions from *its* downstream
deliverables — website structure and content, GEO/AEO positioning, structured data and schema
coverage, and generative-discovery readiness — rather than starting from a generic web-intake
template.

The category names will differ entirely. The rule will not: **questions are derived from
deliverables.** No GeoSites code, schema, or intake form is built here; this note exists so the
lesson survives to that phase instead of being rediscovered.

---

## Phase 61 — the taxonomy's first real use

In **Phase 61** this taxonomy was used to review an actual intake note, and the derivation rule
earned its place. Comparing the note against the fourteen categories produced a finding a
reviewer's memory would likely have missed: the note covers **all 14 categories qualitatively**
while carrying **no counts, rates, cadences, or dates** — so eight categories are quantitatively
incomplete, and the gaps map directly onto the evidence that must be requested next.

That is the taxonomy working as intended. Coverage is not a checkbox: a category can be discussed
at length and still fail to support the deliverable it feeds. **Future real-client forms should be
taxonomy-derived, not guessed** — and a form should ask for the *measurable* input a category
feeds, not merely invite narrative about it. See
[`PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md`](PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md).
