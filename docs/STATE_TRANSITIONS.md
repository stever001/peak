# State Transitions

Allowed transitions and governance gates between the states defined in
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md). This is a **contract/specification** so
future Peak agents and workers respect the same gates; **no engine, workflow runtime, or
stored data is implemented here.** AgentNet grounding is **intended future architecture,
not implemented.**

## General review transition

```
draft -> needs_review -> consultant_reviewed -> qa_reviewed -> approved_internal
```

- Agents may create records at `draft` or `needs_review`.
- `consultant_reviewed` and beyond require **human** action.
- Any state may move to `rejected` (with a reason) or `superseded`; retired records go to
  `archived`.

## Client-facing transition

```
approved_internal -> client_facing_candidate -> approved_for_client
```

- `client_facing_candidate` may be proposed after `approved_internal`.
- `requires_review` sits between candidate and approval.
- **Only a human** sets `approved_for_client`. `rejected_for_client` and `withdrawn` are
  the exits.

## Evidence transition

```
collected -> source_labeled -> needs_verification -> verified
collected -> disputed
verified -> superseded
<any non-final state> -> excluded   (with reason)
```

- Agents may advance to `needs_verification`. `verified` requires checking against data
  (human or a verification step).
- `disputed`, `excluded`, and `superseded` require a recorded **reason**.

## Financial impact transition

```
not_assessed -> reported
reported -> estimated
estimated -> calculated
calculated -> finance_review_needed -> finance_reviewed -> verified
verified -> client_facing_approved
<any non-final state> -> rejected   (with reason)
```

- Agents may advance up to `calculated` / `finance_review_needed`.
- **Agents may not** set `verified` or `client_facing_approved` — those require
  finance/human review. No invented ROI; a `reported` figure stays labeled reported until
  verified.

## Resolver capsule transition

```
draft_capsule -> private_client_capsule -> reviewed_private -> active_private
active_private -> superseded
active_private -> revoked
private_client_capsule -> methodology_candidate   (only after abstraction + human review)
methodology_candidate -> approved_methodology      (only after governance approval)
```

- Client-private capsules stay private; promotion to reusable methodology requires
  **abstraction and human review**, then **governance approval**.
- Agents may create `draft_capsule` and *propose* `methodology_candidate`; they may not
  activate, approve, publish, or promote.

## Source system access transition

```
not_requested -> requested -> granted | partial | denied
granted -> expired | revoked
```

- Granting/denying/revoking is a **client/governance** action; agents may record
  `requested` only.

## Archive / supersede rules

- **Supersede:** a newer record replaces an older one; the old record moves to
  `superseded` (evidence/capsules) and remains referenceable for traceability.
- **Archive:** a record no longer active but retained goes to `archived`.
- **Delete:** where deletion is required, the payload is removed and the record moves to
  `deleted_reference_only` (a governance reference remains; nothing is silently dropped).
- Superseding/archiving/deleting are governed actions and record a reason.

## Agent guardrails (must hold for any future agent/worker)

- Agents **may** create `draft` or `needs_review` records.
- Agents **may not** mark records `client_facing_approved`.
- Agents **may not** verify financial impact without human review.
- Agents **may not** publish or approve resolver capsules.
- Agents **may** propose methodology candidates but **may not** approve them.
- Agent-generated output **must default to `draft` or `needs_review`** (and
  `not_client_facing`), advancing only through the human gates above.
