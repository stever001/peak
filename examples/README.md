# Examples

Anonymized, worked example records that conform to the schemas in
[`../schemas/`](../schemas/). They exist to make the data objects concrete for
developers, consultants, and reviewers, and to serve as fixtures for the planned
validation tests.

## One coherent engagement

All six examples describe the **same fictional engagement** so their cross-references
line up end-to-end:

- Client: `client_alpha`, an industrial-parts distributor (all details fictional).
- Intake: `intake_alpha_2026`.
- Every downstream record sets `related_intake_id` to `intake_alpha_2026`.
- Records cite shared `EvidenceReference` ids (e.g. `evid_alpha_002`) to show the
  evidence-first traceability chain in action.

| Example file | Object | Key id |
| --- | --- | --- |
| `client-intake.example.json` | `ClientIntake` | `intake_alpha_2026` |
| `evidence-reference.example.json` | `EvidenceReference` | `evid_alpha_002` |
| `stakeholder-interview.example.json` | `StakeholderInterview` | `intv_alpha_wh_lead` |
| `visual-observation.example.json` | `VisualObservation` | `vobs_alpha_binspill` |
| `workflow-observation.example.json` | `WorkflowObservation` | `wobs_alpha_adjustments` |
| `inventory-system-profile.example.json` | `InventorySystemProfile` | `isp_alpha_2026` |

The thread: intake flags stockouts and count/ERP mismatches → a warehouse-lead
interview and evidence record capture the counting/adjustment problem → visual and
workflow observations locate concrete causes (bin labeling, uncontrolled
adjustments) → the system profile shows competing sources of truth. This is exactly
the material an initial management report and next-phase proposal would draw on.

## The engagement packet (Phase 2)

`engagement-packet.example.json` bundles the whole thread into one
`EngagementPacket` (`pkt_alpha_2026`) for the same fictional engagement: the client
intake, the inventory system profile, three `EvidenceReference` records, and the
stakeholder interview, visual observation, and workflow observation.

Because the packet carries its own evidence store, it **resolves the cross-references
that remain warnings for the standalone examples**: it declares `evid_alpha_001`,
`evid_alpha_002`, and `evid_alpha_003`, so every nested `evidence_references` id
resolves inside the packet, and every nested `related_intake_id` matches
`intake_alpha_2026`. The Phase 2 harness enforces this as a blocking check.

The standalone object examples above intentionally keep their non-blocking
warnings — they are single objects, not a packaged engagement.

## Ground rules

- **No real client data or PII.** Organizations and people are anonymized labels
  (`client_alpha`, `stakeholder_2`, `consultant_a`). Reported figures are
  illustrative.
- **Validated.** Each example validates against its schema under JSON Schema draft
  2020-12. Run `make validate` (or `python3 tests/validate_phase1.py`) from the repo
  root to check.
- **Not exhaustive.** Examples show representative, not maximal, records. Optional
  fields are intentionally left out in places to reflect realistic partial capture.
