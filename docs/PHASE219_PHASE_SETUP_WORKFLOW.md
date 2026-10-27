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
migration; deployed to production on 2026-10-26 (see *Production cutover*). **Phase 219 is CLOSED.**

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

## Production cutover

**Status: complete (2026-10-26). Phase 219 is CLOSED.** Deployment only: no migration, no grant
change, no environment variable change, and no production data written.

- **Releases.** Both from `8a5045e` (*Add Phase 219 work plan setup workflow*):
  - Render API `peak-consultant-api`, deploy `dep-dbg3e1t9el5s73bpdrag`, **Live**; deployed
    manually, Auto-Deploy off, environment unchanged;
  - Vercel web: the Git-connected production deployment, successful.
- **Health and protection.** `/healthz` returned 200. Logged out, `GET /phase-templates` returned
  401 (registered, not 404). Every roadmap, phase and task route tried returned 401 (8 reads and
  10 writes), and an unknown route returned 404. Logged out, the web roadmap, setup, phase and task
  pages redirected (307) to `/login`.
- **Authenticated API check (existing Admin, read-only):**
  - login 200, `/auth/me` 200 admin, `/engagements` count 1;
  - `/phase-templates` 200: `receiving_accuracy` (6 tasks) and `count_adjustment_practice` (4 tasks),
    **identical to the repository catalogue**, with no trigger categories or task guidance;
  - the engagement's detail, discovery, roadmap and phases all 200: roadmap `enabled=false`,
    0 items, 0 superseded, 0 suggestions, 0 phases;
  - an unknown phase returns 404;
  - logout 204, then `/auth/me` 401.
- **The historical anchor.** The only active production engagement is the unstamped Phase 59
  internal anchor. Its roadmap is `enabled=false` by design (it was not created in the consultant
  workspace, Phase 215), so the engagement page shows no "Roadmap and phase setup" link and the
  roadmap page shows only the notice that setup is available for consultant-workspace
  engagements. This is the expected disabled state, not a Phase 219 defect. The page renders no
  setup control in that state; the check script's "form present" result counted the sidebar
  sign-out form.
- **Web check (signed in, read-only; no setup form submitted):**
  - the engagement page loads with no application error and its work-plan section is present;
  - the roadmap page loads with the disabled notice;
  - no raw internal ids in the rendered text, and no advisory-boundary terms in Phase 219 UI;
  - the one whole-page "audit" match is the Phase 215 retention copy already reviewed in Phase 218;
  - a signed-in unknown setup page shows the normal not-found page;
  - no non-GET requests were made while pages loaded.
- **Responsive measurements (production).** The engagement page, roadmap page and unknown setup
  page at 1440×900, 820×1180 and 1180×820: overflow 0px, 0 elements past the edge, 0 controls
  under 40px.
- **Runtime database identity.** The process-list probe ran straight after the authenticated
  checks. API connections were `peak_prod_runtime` on `defaultdb` (5, Sleep). There was no
  `peak_prod_verify_ro` connection; the only other connection was the MySQL event scheduler.
- **Preservation.** All read-only:
  - the Phase 50 gate passes live: runtime session path, required grants present, no excess,
    global or grant-option privileges;
  - the verifier is green on MySQL 8.4: head `022_engagement_roadmap_work_plan`, 35 base tables
    (34 application + `alembic_version`), 394/394 governed columns and 11/11 idempotency
    boundaries, 0 at risk;
  - tables match the repository;
  - `roadmap_items`, `engagement_phases`, `phase_tasks` and `phase_task_records` all have 0 rows;
  - the 30-table count/checksum baseline (133 rows) is identical to the Phase 218 final snapshot,
    with no table changed.

**Deferred acceptance.** The full mutation path (roadmap item → phase → template → authorization) was
intentionally not exercised in production. No roadmap item, phase, task, authorization or task
record was created solely for acceptance. That workflow is covered by the Phase 219 harness and the
local browser walkthrough (50/50, temporary SQLite, synthetic data). Populated production acceptance
waits for the first real consultant-workspace engagement that reaches roadmap work.

## Limitations

1. Authorization has no separate "authorized by (client person)" or date field. The consultant
   writes who authorized it and how into the basis text. Peak stamps who recorded it and when.
2. Only Peak Method templates populate a plan from the web. Adding a single consultant task
   (`POST /phases/{id}/tasks`) stays API-only.
3. The roadmap item `sequence` is not editable from the web; items keep creation order.
4. Templates already in a plan are marked, but still selectable. A duplicate is refused by the API
   with its own message.
