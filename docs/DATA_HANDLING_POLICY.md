# Data Handling Policy

**Status: operational first policy — internal, pre-legal.** This is Peak's initial,
working policy for handling client-related material in this repository. It is written
for founder/consultant use and is intended to be reviewed and strengthened by legal
counsel later. It does **not** claim legal or regulatory compliance is complete.

## 1. Purpose and scope

This policy governs what may and may not be stored or processed in the Peak internal
AI operating system repository, and how real client material must be handled before it
touches this repo or any tool used with it.

It applies to everything in the repository — `schemas/`, `examples/`, `prompts/`,
`tools/`, `tests/`, `docs/` — and to any working files a consultant creates while using
the repo.

## 2. Internal-only status

This repository is an **internal Peak operating system**. It is not client-facing, and
nothing in it is operated by or delivered directly to a client. Access is limited to
Peak personnel.

## 3. No real client data in `examples/`

`examples/` (and everything committed to the repo generally) must contain **only
fictional, anonymized material**. The worked engagement (`client_alpha`,
`intake_alpha_2026`, `consultant_a`, `stakeholder_1..3`) is invented for illustration
and testing. Real client data — even "lightly disguised" — must never be committed.

To turn real notes into safe repository examples, follow
[`REDACTION_GUIDE.md`](REDACTION_GUIDE.md).

## 4. No secrets or private exports in the repo

The following must **never** be committed, in any form:

- Secrets, credentials, passwords, API keys, or access tokens.
- Private system exports (ERP/WMS extracts, database dumps, raw stock-on-hand files).
- System screenshots or photographs of a real client site.
- Any file that would grant access to, or reveal the internals of, a client system.

If a secret is ever committed by mistake, treat it as compromised: rotate it and raise
it with Peak leadership. (Removing it from a later commit does **not** remove it from
history.)

## 5. Treatment of specific data types

| Data type | Handling in this repo |
| --- | --- |
| Client / company names | Anonymize → `client_alpha`, `client_beta`, … Never commit the real name. |
| Employee / stakeholder names | Anonymize by role → `warehouse_manager_alpha`, `finance_lead_alpha`, or `stakeholder_1`. |
| Locations / sites | Generalize → `site_alpha`, `receiving_area_alpha`. No addresses or identifiable geography. |
| Photos / screenshots | Do **not** commit image files of real sites/systems. Replace with **textual descriptions** unless explicitly approved. |
| Inventory exports / data files | Never commit. Summarize findings in words; keep raw exports out of the repo. |
| Pricing / cost data | Redact → ranges or `[REDACTED_PRICING]`. No real unit costs, margins, or contract prices. |
| Vendor / supplier names | Anonymize → `vendor_alpha`. |
| SKUs / item identifiers | Generalize → product categories (e.g. "fasteners"), not real part numbers. |
| Quantities / metrics | Use ranges or representative values; label anything real as "reported, not verified". |
| Operationally sensitive info | Keep the operational *insight* (generalized safely); drop the identifying specifics. |

## 6. Allowed vs. prohibited repository content

**Allowed:**
- Fictional, anonymized example records and notes.
- Schemas, prompt contracts, tools, tests, and documentation.
- Generalized operational findings that carry no identifying detail.

**Prohibited:**
- Any real client identity, person, address, or site.
- Secrets/credentials/tokens; private system exports; real screenshots/photos.
- Real pricing, cost, margin, or contract terms.
- Real part numbers, real vendor names, or anything that re-identifies a client.

## 7. Temporary working files

While working an engagement, a consultant may need real notes locally **before**
redaction. Guidance:

- Keep real, unredacted working files **outside the repository** (e.g. a
  Peak-approved secure location), never inside `~/projects/peak`.
- Redact **before** anything is copied into the repo or pasted into a tool.
- Do not rely on `.gitignore` to protect real data — the safe default is "not in the
  repo at all."
- Delete local temporary real-data files when the engagement no longer needs them,
  per the retention assumptions below.

## 8. Sensitive-data flags in `EvidenceReference`

The `EvidenceReference` object carries a `sensitive_data_flag` and records only a
non-sensitive `summary` — it **never embeds the sensitive content itself**. When
capturing evidence:

- Set `sensitive_data_flag: true` when the underlying evidence is sensitive.
- Put a generalized description in `summary`; keep the raw content out of the repo.
- Use `access_notes` / `retention_notes` to record where the real evidence lives and
  how it is handled (without reproducing it).

## 9. Retention assumptions (provisional)

Until a formal schedule exists (see Future work):

- The repo retains **only** fictional examples indefinitely; they carry no client risk.
- Real working material lives outside the repo and is kept only as long as the
  engagement requires, then deleted or moved to Peak-approved storage.
- No real client data is retained inside this repository at any time.

These are **working assumptions**, not a legal retention schedule.

## 10. Human review before client-facing use

No output derived from this repo may be shared with a client without **explicit human
review and approval**. Draft output is internal until a consultant (and, where
relevant, management) signs off. See the readiness ladder in
[`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md).

## 11. AgentNet status

AgentNet is **intended future grounding/resolution architecture only**. It is **not
integrated**. No real client data may be published to, or grounded through, AgentNet
without a **separate, explicit Peak governance decision**. Nothing in this repo
performs or implies any AgentNet lookup or publication.

## 12. LLM usage caution

The prompt contracts are run by a human against an LLM of their choice. Because that
may be a third-party service:

- **Do not paste unredacted real client data** into any third-party LLM/tool unless it
  is explicitly approved under Peak policy (e.g. an approved, contractually covered
  service).
- Prefer redacted material for any exploratory or drafting use.
- Treat anything pasted into a third-party tool as potentially retained by that
  vendor.

## 13. Future work (not yet in place)

This is a first policy. Still to be defined, ideally with legal review:

- A real **retention schedule** with concrete durations.
- **Access controls** and secure storage for real working material.
- A **redaction/verification step** in tooling (currently a human discipline).
- **DPA / vendor review** for any LLM or third-party service used with client material.
- **Client consent** language covering AI-assisted assessment and data handling.
- A defined **governance process** for any future AgentNet grounding of real material.

Nothing in this section is claimed to exist yet.

---

*See also:* [`REDACTION_GUIDE.md`](REDACTION_GUIDE.md) (how to redact),
[`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md) (the operating process),
[`../examples/redacted/`](../examples/redacted/) (worked redaction examples).
