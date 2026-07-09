# Redacted Interview Notes — client_alpha (EXAMPLE)

> Fictional, redacted example. A stakeholder interview after applying
> [`../../docs/REDACTION_GUIDE.md`](../../docs/REDACTION_GUIDE.md). No real person,
> quote-that-identifies, system product, vendor, or figure appears here.

**Engagement:** client_alpha
**Interviewee:** warehouse_lead_alpha (role: warehouse lead)
**Interviewer:** consultant_a
**Topics:** counting process, adjustments, receiving, system usage

---

## Raw-ish notes (redacted)

- **Counting:** counts are done weekly, but only on an informally chosen subset of
  aisles. (Note a **contradiction** to resolve: the operations lead described counts as
  full-warehouse monthly — reconcile the actual cadence.)
- **Adjustments (key issue):** when a count disagrees with the ERP, staff adjust the
  ERP on-hand to match the count directly — **no approval step, no reason code, no
  root-cause review**. Described as routine.
  - Consultant interpretation: this masks recurring accuracy problems rather than
    fixing them; also a segregation-of-duties / shrink-concealment concern.
- **Receiving:** received goods are *sometimes* put away before being booked into the
  ERP (claim — not yet corroborated).
- **System:** claims the ERP does not flag negative on-hand balances, so they go
  unnoticed (claim — verify directly in the system).
- **Reported impact:** roughly **6–8 hours/week** spent reconciling counts
  (*reported, not verified*).
- Trust: purchasing "no longer trusts on-hand figures," which is why branches keep
  their own reorder spreadsheets. Suppliers referred to generically as vendor_alpha.

## Evidence handling
- This interview would be captured as an `EvidenceReference` with
  `sensitive_data_flag` set as appropriate and only a **generalized summary** stored —
  never a verbatim recording or identifying quote.
- Claims are recorded **as claims**, kept separate from observed evidence and from
  consultant interpretation.

## Redaction notes
- Interviewee identified by role alias only; no personal name.
- No product names, vendor names, prices, or real quantities; the 6–8 hours figure is
  a reported range, explicitly not verified.
