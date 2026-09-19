# Phase 204 — Consultant interview and discovery workflow

Consultants can run discovery inside an engagement: set a North Star, conduct structured interviews
with simple branching, record observations, and flag low-hanging fruit. The data stays structured
for later assessment and reporting. Baseline `5cb8ca9`. Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

> **OPEN PHASE 203 ITEM — still outstanding.** Production Admin acceptance is pending provisioning
> of `admin@peakinventorysolutions.com`. Phase 203 infrastructure is live, but authenticated
> production acceptance remains deferred. Once the mailbox exists:
> 1. bootstrap the Admin with `tools/bootstrap_admin.py --production` (steps in
>    [`PHASE203_FIRST_LIVE_DEPLOYMENT.md`](PHASE203_FIRST_LIVE_DEPLOYMENT.md));
> 2. sign in, check the Dashboard and Consultants, sign out, and sign back in;
> 3. record authenticated acceptance as complete.
>
> Do not create a temporary Admin, and do not remove this item until those steps pass.

## Model (migration `017_discovery_workflow`)

| Table | Purpose | Notes |
|---|---|---|
| `engagements.north_star`, `north_star_context` | The consultant-defined North Star for the current discovery effort, with optional context | Free text, no vocabulary |
| `discovery_questions` | The editable question pool | Application configuration, not client data. No governance columns (Phase 11 lists it in `NON_GOVERNED_TABLES`). Deactivated, never deleted. `seed_key` is unique so initialization is idempotent |
| `discovery_sessions` | Interviews | Interviewee name/title **snapshot**, `in_progress` / `completed`, conducting consultant, start/complete times, notes |
| `discovery_answers` | One answer per (session, question) | The prompt is snapshotted, so later question edits never rewrite history |
| `discovery_observations` | Consultant observations, optionally linked to an interview | Category, text, `low_hanging_fruit`, `estimated_effort` / `estimated_value` (low / medium / high), recording consultant |

Sessions, answers and observations are governed engagement work records, with the standard
governance and audit columns. Governed identifiers are pinned to the governed collation at
creation. The migration is additive and carries no data.

**Interviewees** are not a CRM. The interview form offers the client's Phase 202 key personnel as a
picker that fills in name and title; otherwise the consultant types them. The session stores a
snapshot either way.

## Question pool and branching

- Each question has a prompt, category, answer type (`short_text`, `long_text`, `yes_no`,
  `single_choice` with 2–20 choices), display order, an active flag, and an optional branch.
- **Branch rule:** one *earlier* question (lower display order), `equals` or `not_equals`, and one
  value. For yes/no and single-choice questions the value must be one of that question's answers.
- **Visibility:** a question is shown when it is active and either has no branch, or its branch
  question is itself shown and its stored answer satisfies the rule. It is evaluated in display
  order.
- **Edits stay consistent:** an edit is refused if it would put a question at or before a question
  that branches on it, or would invalidate that question's branch value.
- There is no expression language, scoring, matrix question, or form designer.
- **Question Pool screen (`/questions`):** any consultant (Admin or Consultant) can view questions
  grouped by category, add, edit, deactivate/reactivate, and set the category, answer type and
  branch.
- **History is kept:** a question that is deactivated, or hidden by a changed answer, drops out of
  the interview flow, but its stored answer is still shown under "Earlier answers no longer in the
  question flow", with the original prompt.

## Interview workflow

1. From the engagement page's **Discovery** section, choose **Start interview**, pick a key person
   or type a name and title, and add optional notes.
2. `/interviews/[id]` shows **one question at a time** with a progress bar and large controls (radio
   cards for yes/no and single choice).
   - **Back**, **Save** and **Save & next** move through the *currently shown* questions, which are
     recomputed after every save, so branches appear and disappear immediately.
   - Desktop adds a question list for jumping between questions. **Review all** lists every shown
     question and its answer.
3. **Resume** from the engagement page at any time. **Complete interview** makes it read-only.

## Observations and low-hanging fruit

Observations form a parallel track to interview answers, added and edited from the engagement page.
Low-hanging fruit is a consultant flag. Effort and value are optional low / medium / high estimates.
The Discovery section lists low-hanging-fruit observations separately. Nothing is ranked or
ROI-calculated. These are internal working notes: they are never client-facing, published, or
sent to AgentNet.

## Governance and write boundary

- Every write goes through `peak/workspace/discovery.py` and is checked by
  `is_allowed_workspace_write` against ten new explicit `(table, action)` pairs in
  `WORKSPACE_WRITE_COLUMNS`:
  - `set_engagement_north_star`;
  - create/update discovery question;
  - start, update and complete discovery session;
  - create/update discovery answer;
  - create/update discovery observation.
- No update action can change an identity or link column (ids, client, engagement, session,
  question, conducting/recording consultant, `seed_key`). There is no delete action.
- Sessions, answers and observations are created with `WORKSPACE_ENGAGEMENT_CREATION_STAMP` (owner
  `peak_consultants`, scope `engagement_authorized`), and **only under an engagement that carries
  that stamp**. Discovery is refused on internal-test anchors or differently owned engagements.
- The conducting/recording consultant is always the signed-in consultant.
- API request models forbid unknown fields, so a caller cannot send owner, scope or identity
  fields. None of these appear in the UI.
- The generic controlled-writer allowlist is unchanged, and no discovery table is on it.

**API:**
- `GET/POST /questions`, `GET/PATCH /questions/{id}`
- `GET /engagements/{id}/discovery`, `PATCH /engagements/{id}/north-star`
- `POST /engagements/{id}/sessions`, `GET/PATCH /sessions/{id}`, `POST /sessions/{id}/complete`,
  `PUT /sessions/{id}/answers/{question_id}`
- `POST /engagements/{id}/observations`, `GET/PATCH /observations/{id}`

## Initial question set

`peak/workspace/initial_questions.py` holds 29 prompts across 10 categories:
- Business goals;
- Inventory accuracy;
- Receiving;
- Putaway;
- Picking / fulfillment;
- Cycle counting;
- Stockouts / overstock;
- Systems / visibility;
- Labor / workflow;
- Management reporting.

Seven are follow-ups with branches. This is configuration, with no answers and nothing about any
client. `tools/init_discovery_questions.py` loads it:
- It is a dry run unless `--execute` is passed.
- It is idempotent by `seed_key`: existing entries are skipped, never overwritten, so a
  consultant's edits or deactivations are never re-imposed.
- Targets are local SQLite or `peak_lab`. Production needs `--production` plus
  `PEAK_PRODUCTION_DISCOVERY_INIT_CONFIRM=1`, and is **not authorized in this phase**.
- The application never seeds at startup.

## Validation

- `tests/validate_phase204_discovery_workflow.py` (`make validate-phase204`), 31 checks: migration
  017 up/down; allowlist narrowness; the idempotent initializer; the North Star;
  start/save/resume/complete; answer normalization; branch show/hide and swap; hidden-question
  refusal; observations with low-hanging fruit, effort and value; question add/edit/deactivate and
  branch validation; history surviving edits and deactivation; governance override refusals and
  stamping; refusal on non-workspace engagements.
- Harness changes:
  - Phase 11 lists the four new tables.
  - The Phase 202 test no longer freezes the allowlist at exactly four pairs; it keeps those four
    pairs' exact columns.
  - Migration 017 triggered no historical freeze failures.
- `npm run build`, `npm run lint`, and a local end-to-end run of the real forms as a Consultant,
  with screenshots at 390, 820 and 1440 px.

## Production posture

**No Phase 204 production activity:** migration 017 is not applied, no question rows exist, and
there is no interview or observation data. That needs a separate review of migration 017, the
production migration, the question-pool initialization, and the runtime `UPDATE` grants on
`discovery_questions`, `discovery_sessions`, `discovery_answers` and `discovery_observations` (the
runtime role's existing schema-wide `INSERT` already covers creation).

**Likely next phase:** internal assessment and report consumption of the structured discovery data.
