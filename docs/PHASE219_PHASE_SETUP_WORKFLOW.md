# Phase 219 — Work-Plan Initiation and Setup Workflow

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `7fe686b`.

## Purpose

Phase 218 let a consultant run an authorized work plan. Starting one was API-only. Phase 219 adds
the consultant-facing path from the engagement to the work plan:

```
Engagement → proposed roadmap work → accepted → engagement phase (planned)
           → initial work plan loaded + client authorization recorded → Phase 218 work plan
```

This is operational setup only: no proposals, fees, billing, signatures, uploads, client login, SI
generation, Final Report or artifact changes, and no role changes. Built in the repository with no
migration; not deployed.

## The flow

```
Engagement page → "Engagement phases and work plans"
  "Roadmap and phase setup" link (counts: suggested by Peak, proposed, accepted awaiting a phase)
  phase cards: setup stage; open setup until setup is finished, then the work plan

Roadmap and phase setup (/engagements/{id}/roadmap)
  Suggested by Peak     computed from discovery observations on every load, dashed and marked
                        "not saved"; shows the observations it rests on; "Add to roadmap"
  On the roadmap        stored items: status, framing, origin, observations it rests on, decision
                        note and who decided; the decisions the API allows (Accept / Defer /
                        Decline / Return to proposed); "Revise the wording" for proposed or deferred
                        items; an accepted item without a phase shows "Create the engagement phase"
  Earlier versions      superseded items, collapsed
  Add your own proposed work  title, issue or opportunity, why it matters, expected outcome,
                        optional discovery observations it rests on
  Engagement phases     setup cards; "Create a phase without a roadmap item" (reason required)

Phase setup (/phases/{id}/setup)
  Setup progress        1 proposed work accepted (or manual reason recorded), 2 phase created,
                        3 initial work plan loaded, 4 client authorization recorded, 5 ready
  Objective and scope, the item's issue/opportunity and expected outcome, source
  Initial work plan     template cards (title, scope, task outline); the roadmap item's template
                        preselected; loaded templates marked; "Load work plan tasks"
  Client authorization  what was authorized, by whom and how; optional reference; a confirmation;
                        Lead or Admin only (others see who can record it)
  "Open work plan" → /phases/{id} (Phase 218) once authorized with tasks
```

The Phase 218 phase page shows "Continue phase setup" while a phase is planned or has no tasks.

## Setup state is derived

`web/lib/phase-setup.ts` reads the stage from the phase's `status` and `work_plan_status` (which the
API derives from its tasks): `plan_and_authorization`, `authorization`, `plan`, `ready`,
`completed`. Nothing is stored; there is no wizard state and no new state machine. A phase is
executable only when the API says it is `authorized`; the UI never presents a planned phase as
workable.

## Work plan before authorization

The Phase 217 service marks every task added to an **authorized** phase as
`added_after_authorization`, a visible scope change. The Phase 217 and 218 harnesses load the
template while the phase is planned, then authorize. Setup therefore offers the template step
whenever the phase is planned, or authorized with no plan. While planned, it recommends loading
the plan first, so the client authorizes the plan the consultant will follow. If authorization is
recorded first, the template can still be loaded, and the page warns that its tasks will be marked
as added after authorization.

## API changes (read-only; no new write path, no new column)

| Change | What it is |
|---|---|
| `GET /phase-templates` | The Peak Method template catalogue (`peak_method_phases.catalogue()`): key, title, problem framing, expected outcome, scope, task outline `{sequence, title, required}`. No trigger categories, no task guidance |
| `GET /engagements/{id}/roadmap` items (and superseded) | `decisions`: statuses `decide_roadmap_item` accepts now (none once a phase exists); `revisable`; `phase_id`; `decided_by` (name) |

Every write the UI makes uses an existing Phase 217 endpoint. "Add to roadmap" for a suggestion
sends only the template key from the browser. The server action reads the roadmap again and posts
the observation ids Peak computed, so a suggestion cannot be stored with invented grounding.

## Permissions

Unchanged. Any signed-in consultant can work with the roadmap, create phases and load templates.
Recording authorization stays with the engagement's Lead or an Admin (`lead_or_admin_required`,
403). The setup page shows the form only to them, for display. The API decides.

## Boundary

All new UI text stays inside the advisory boundary (Contract C21). Authorization is described as
"This records that the client has authorized this phase of work". The page says it is an operational
record, not a proposal, a signed contract or a payment. Roadmap framing still passes the service's
boundary check: audit framing is refused, and the message is shown as given. Setup never calls a
discovery observation endpoint and creates no observation, finding, evidence or artifact. Answers
still never become findings.

## Validation

`tests/validate_phase219_phase_setup_workflow.py` (in `make validate`). It covers:
- the empty engagement;
- the template catalogue matches the canonical registry, and reads store nothing;
- a suggestion stays distinct until it is added;
- a consultant item built from the web payload (run under Node);
- accept, defer, decline and revise, with the allowed decisions reported;
- a phase from an accepted item, once only; a manual phase needs its reason;
- a planned phase stays non-executable;
- a template loaded before authorization is not marked as a scope change; a duplicate is refused
  with the API's message;
- only the Lead or an Admin can authorize; another consultant gets 403;
- a template loaded after authorization is marked;
- setup stage and handoff links are correct for every state;
- Phase 218 work is accepted afterwards;
- no observation or artifact is created; logged-out requests get 401.

Static checks:
- only the expected endpoints are called;
- no hard-coded templates;
- no raw ids or JSON rendered;
- no billing, signature or upload fields;
- the boundary text scan passes;
- the handoff and back-links are present;
- no migration.

## Limitations

1. Authorization has no separate "authorized by (client person)" or date field. The consultant
   writes who authorized it and how into the basis text. Peak stamps who recorded it and when.
2. Only Peak Method templates populate a plan from the web. Adding a single consultant task
   (`POST /phases/{id}/tasks`) stays API-only.
3. The roadmap item `sequence` is not editable from the web; items keep creation order.
4. Templates already in a plan are marked, but still selectable. A duplicate is refused by the API
   with its own message.
