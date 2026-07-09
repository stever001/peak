# Consultant Workflow

A practical guide for a Peak consultant using this repository to run a
**human-in-the-loop** inventory assessment — from messy intake notes to reviewed
work product.

## 1. Purpose and scope

This is an **internal Peak operating workflow**. It helps a consultant convert intake
notes, interviews, visual observations, and workflow observations into a structured
`EngagementPacket` and, from there, into reviewed Peak work product (discovery plan,
findings, report, proposal, QA review, lessons).

What it **is not**:

- It is **not client-facing software**. Nothing here is operated by a client.
- It **does not call an LLM, AgentNet, API, database, or any external service**. You
  run the LLM step yourself, by hand, and you own every output.
- It does **not** execute prompts automatically. The repo gives you the data
  structures, the prompt contracts, a read-only summarizer, and validation — the
  judgment and the model calls are yours.

Think of the repo as a **disciplined operating manual plus data contract**, not an
application.

## 2. End-to-end workflow (human-in-the-loop)

```
 messy intake notes
        │  (you: prompts/intake/normalize-client-intake.prompt.md)
        ▼
 ClientIntake ──────────────┐
        │                   │
        ▼                   │  assemble by hand into one packet
 EvidenceReference[]        │
 InventorySystemProfile     │
 StakeholderInterview[]     ├──►  EngagementPacket (JSON)
 VisualObservation[]        │            │
 WorkflowObservation[]      │            │  make packet-summary
        └───────────────────┘            ▼
                                  pick a prompt contract
                                         │  paste packet JSON into its reusable body
                                         ▼
                                  draft output (LLM, run by you)
                                         │  QA review (qa contract)
                                         ▼
                                  save reviewed output to examples/outputs/... (or your engagement folder)
                                         │
                                         ▼
                                  extract engagement lessons (learning contract)
```

Step by step:

1. **Capture messy intake notes** — call notes, emails, questionnaire answers. Raw text
   is fine.
2. **Normalize into `ClientIntake`** — run
   `prompts/intake/normalize-client-intake.prompt.md`. It returns a `ClientIntake`
   draft plus a missing-information list and confidence notes. Do not invent fields.
3. **Add `EvidenceReference` records** — one per piece of evidence (interview
   statement, photo, document). Give each a stable `evid_` id; this is the
   traceability backbone.
4. **Add the `InventorySystemProfile`** — systems, source of truth, integrations,
   manual workarounds, data-quality concerns, access status.
5. **Add `StakeholderInterview` records** — topics, stated pain points, process/system
   claims (as claims), quantified impacts (as reported), contradictions/follow-ups.
6. **Add `VisualObservation` records** — walk-around observations, each linked to
   evidence (e.g. a photo).
7. **Add `WorkflowObservation` records** — how a process actually runs vs. how it is
   documented, with control risk and quick-win flag.
8. **Bundle into an `EngagementPacket`** — one self-contained JSON object. Every nested
   `evidence_references` id must resolve inside the packet, and every nested
   `related_intake_id` must equal the packet's `client_intake.intake_id`.
9. **Validate** — `make validate` (Phase 2 checks packet integrity as a blocking gate).
10. **Run the packet summary** — `make packet-summary` orients you: counts, systems,
    which contracts and output targets apply.
11. **Select a prompt contract** — pick the workflow you need (discovery, evidence,
    reporting, proposal, qa, learning).
12. **Paste packet JSON into the prompt body** — copy the contract's "Reusable prompt
    body" into your chosen LLM and paste the packet JSON where indicated.
13. **Draft sample output** — the LLM produces a draft. It is a draft, not a
    deliverable.
14. **QA review** — run `prompts/qa/review-assessment-packet.prompt.md` against the
    packet and the draft. Fix what it flags.
15. **Save reviewed output** — write the reviewed result to the matching file under
    `examples/outputs/` (for the sample engagement) or your real engagement folder.
16. **Extract engagement lessons** — run
    `prompts/learning/extract-engagement-lessons.prompt.md` to capture reusable
    lessons and **draft** knowledge capsules.

## 3. Commands

All commands are read-only or validation-only. This machine uses `python3`.

```bash
# Validate everything (schemas, packet integrity, prompt contracts, sample outputs,
# and the runner). Exits 0 on success.
make validate

# Summarize the example packet and see which contracts/targets apply (read-only;
# no LLM/API/network).
make packet-summary

# The same summary, invoked directly (point --packet at your own packet file):
python3 tools/packet_runner.py --packet examples/engagement-packet.example.json
```

## 4. File map

| Path | What it holds | You use it to… |
| --- | --- | --- |
| `schemas/` | JSON Schema (draft 2020-12) for every data object + the `EngagementPacket` | Know the exact shape each object must take |
| `examples/` | Anonymized worked example records (one per object) | See a valid, realistic instance of each object |
| `examples/outputs/` | Sample run artifacts (discovery plan, findings, report, proposal, QA review, lessons) | See what "good" reviewed output looks like |
| `prompts/` | One prompt contract per workflow (intake → learning) | Copy the reusable body into your LLM |
| `tools/` | `packet_runner.py` — read-only summarizer/orienter | Run `make packet-summary` on a packet |
| `tests/` | stdlib + `jsonschema` validation harnesses | Prove the packet and repo are internally consistent |
| `docs/` | Operating model, workflows, data objects, plan, this guide | Understand the why and the process |

## 5. Consultant rules

These are non-negotiable for internal quality and honesty:

- **Do not invent facts.** No client details, metrics, systems, interviews, photos, or
  observations that are not in the source material.
- **Separate the four layers.** Keep **observed evidence**, **stakeholder claims**,
  **consultant interpretation**, and **recommended follow-up** distinct. Never silently
  promote a claim to a fact.
- **Cite evidence IDs.** Every material finding references the packet `evid_` id(s) that
  support it. If you cannot cite one, it is a follow-up, not a finding.
- **Label reported metrics as reported.** A number a stakeholder gave you is "reported
  by <role>, not yet verified" until data confirms it.
- **Do not claim ROI** or savings unless the evidence supports it. An initial,
  data-blocked assessment usually cannot.
- **Do not claim AgentNet grounding, lookup, or publication occurred.** AgentNet is
  intended future architecture and is not integrated.
- **Keep outputs internal until reviewed.** Draft output is internal; it becomes
  shareable only after human review and (for client-facing) explicit approval.
- **Avoid real sensitive data in examples.** Use anonymized labels
  (`client_alpha`, `stakeholder_1`, `consultant_a`). `EvidenceReference` records the
  fact of sensitive evidence via `sensitive_data_flag`; it never embeds the content.

## 6. QA gate

Before any output moves toward a client, run it through the QA gate.

- **Contract:** `prompts/qa/review-assessment-packet.prompt.md` — strict but fair. It
  surfaces unsupported claims, missing evidence, contradictions, weak recommendations,
  a report-readiness score, and prioritized required fixes.
- **Worked example:** `examples/outputs/qa-review.alpha.example.md` — shows the gate
  applied to the sample engagement (it scored the sample a `3/5` client-readiness and
  listed concrete fixes).

**Readiness categories** (advance only by human decision):

| Category | Meaning |
| --- | --- |
| **internal draft** | Raw LLM output. Not reviewed. Never leaves the consultant. |
| **consultant-reviewed** | A consultant has checked evidence, claims, and separation of layers. |
| **management-ready draft** | Passed QA; suitable for internal management review and commercial framing. |
| **client-ready** | Only after **explicit human approval**. The repo never marks anything client-ready automatically. |

## 7. Lessons capture

After an engagement, capture what is reusable.

- **Contract:** `prompts/learning/extract-engagement-lessons.prompt.md` — extracts
  reusable patterns, checklist/prompt improvements, schema gaps, candidate knowledge
  capsules, and follow-up actions.
- **Worked example:** `examples/outputs/engagement-lessons.alpha.example.md`.

Emphasis:

- Lessons **may become future Peak methodology capsules** — but only as candidates.
- **Mark candidate capsules `DRAFT`.**
- **Do not claim AgentNet publication or grounding occurred.** Capsules are drafts held
  for a possible future grounding decision, nothing more.

## 8. Phase boundary (what this repo does and does not do today)

**Supported now:**

- Human-in-the-loop packet and prompt workflows: structured data objects, a validated
  `EngagementPacket`, prompt contracts, a read-only packet summarizer, and validation.

**Not yet (deliberately out of scope):**

- It does **not** execute prompts automatically (no agent runtime, no LLM calls).
- It does **not** integrate with AgentNet (intended future grounding/resolution only).
- It does **not** store real client data (no database; a retention/redaction policy is
  still to be defined).
- No frontend, API, or client-facing functionality.

**Possible future phases** (not promises): guarded runners that assist without
automating judgment, packet manifests, a redaction/retention policy for real data, and
eventual AgentNet grounding of methodology capsules — each added only when the
human-in-the-loop core is proven.

---

*See also:* [`OPERATING_MODEL.md`](OPERATING_MODEL.md) (why),
[`AGENT_WORKFLOWS.md`](AGENT_WORKFLOWS.md) (the ten workflows),
[`DATA_OBJECTS.md`](DATA_OBJECTS.md) (object shapes), and
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) (phasing).
