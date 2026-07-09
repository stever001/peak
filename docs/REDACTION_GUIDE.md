# Redaction Guide

How to convert raw engagement notes into **safe, anonymized, example-friendly**
material for this repository. This guide operationalizes
[`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md). It is internal and pre-legal; it
does not claim legal compliance.

## Goal

Keep the **operational insight**, drop the **identifying detail**. A good redaction
reads like a realistic engagement, teaches the same lesson, and cannot be traced to a
real client, person, site, system, vendor, or price.

## Redaction patterns

Apply these consistently. Use a per-engagement alias set (`_alpha`, `_beta`, …) so a
single redacted engagement stays internally consistent.

| Raw material | Redact to | Notes |
| --- | --- | --- |
| Company / client name | `client_alpha` | Never commit the real name or an obvious pun on it. |
| A person (by name) | role alias: `warehouse_manager_alpha`, `finance_lead_alpha` | Prefer role over identity; or `stakeholder_1`. |
| Location / site / address | `site_alpha`, `receiving_area_alpha` | No addresses, city names, or identifiable geography. |
| System / software product | ERP/WMS **category** (e.g. "the ERP") | Do not name the product unless explicitly approved. |
| Screenshot / photograph | a **textual description** | Do not commit image files unless explicitly approved. |
| SKU / part number / item | generic **category** (e.g. "fasteners") | Never real part numbers. |
| Dollar amount / pricing / cost | a **range** or `[REDACTED_PRICING]` | No real unit costs, margins, or contract prices. |
| Inventory quantity / metric | a **range** or representative value | Label real figures "reported, not verified". |
| Vendor / supplier name | `vendor_alpha` | Anonymize every third party. |
| Contract / account numbers, IDs | remove entirely | Not needed for the operational point. |

## What NOT to over-redact

Redaction should not destroy the operational point. Keep the following — **generalized
safely** — because they are what makes an example useful:

- **The problem mechanism.** "Counts diverge from the ERP because adjustments are made
  without reason codes" is safe and important; keep it.
- **Process names.** receiving, put-away, picking, cycle count, replenishment,
  adjustment — generic, keep them.
- **Qualitative severity and direction.** "high impact", "unreviewed", "no approval
  step" — keep.
- **Generic system categories.** "an aging on-premise ERP", "per-branch spreadsheets" —
  keep; just don't name the product.
- **Reported metrics as ranges.** "~6–8 hours/week reconciling counts (reported)" is
  fine; an exact figure tied to a real client is not.

If removing a detail would make the example useless *and* the detail can be generalized
without re-identifying anyone, generalize it rather than deleting it.

## Before / after examples

**Company + people + system**

- Before: `Met with Jane Smith, Ops Director at Acme Fasteners Inc. (Cleveland). They run SAP.`
- After: `Met with the operations lead (operations_manager_alpha) at client_alpha, an industrial-parts distributor. They run an ERP (product not named).`

**Pricing + SKU**

- Before: `Part #FS-10933 costs $4.12/unit; carrying ~40,000 units.`
- After: `A fast-moving fastener SKU; unit cost [REDACTED_PRICING]; on-hand in the tens of thousands.`

**Location + vendor**

- Before: `Receiving dock at 1200 Industrial Pkwy; main supplier is Bolt Depot LLC.`
- After: `The receiving area (receiving_area_alpha); main supplier is vendor_alpha.`

**Screenshot**

- Before: *(an attached ERP screenshot showing negative on-hand for real SKUs)*
- After: `Text note: the ERP screen showed negative on-hand balances that were not flagged (no image committed).`

## Redaction checklist

Run through this before committing any example or pasting into a tool:

- [ ] No real company, client, or prospect name anywhere.
- [ ] No real person names (use role aliases or `stakeholder_N`).
- [ ] No addresses, cities, or identifiable locations.
- [ ] No named software products unless explicitly approved (use category).
- [ ] No image files / screenshots / photos of real sites or systems.
- [ ] No real SKUs or part numbers (use categories).
- [ ] No real pricing/cost/margin (use ranges or `[REDACTED_PRICING]`).
- [ ] No real vendor/supplier names (use `vendor_alpha`).
- [ ] Quantities are ranges or representative; real figures labeled "reported".
- [ ] No secrets, credentials, tokens, or private system exports.
- [ ] Alias set is internally consistent across the engagement.
- [ ] The operational insight still reads clearly after redaction.

See [`../examples/redacted/`](../examples/redacted/) for worked before-style notes
converted into safe, redacted form.
