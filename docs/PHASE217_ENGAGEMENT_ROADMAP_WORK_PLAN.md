# Phase 217 — Engagement Roadmap and Guided Work Plan Foundation

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `63b3c65`.

## Purpose

Peak should let a relatively inexperienced consultant deliver professional SMB inventory and
process consulting: interpret discovery, propose useful follow-on phases, have each paid phase
separately agreed, be guided step by step through the authorized work, and record what actually
happened, so that findings and the Final Report can later rest on completed, documented work.

Phase 217 builds only the primitives:

```
Discovery → roadmap item (advisory) → engagement phase (separately authorized)
          → guided work plan (ordered tasks) → consultant task records → completion readiness
```

Not built: proposal documents, fees, e-signature, billing, evidence/photo upload, Final Report
changes, AgentNet changes, a governed audit capability, consultant training, a generic workflow
engine, any web UI.

## Current state found (before Phase 217)

- `engagements.status` is a coarse engagement state (active / on_hold / closed) and
  `engagements.current_phase` is a free-text label. There was no phase entity.
- Contract C9 and ARTIFACT_LIFECYCLE AL1 already define "Engagement Phase" as a *consulting stage*
  and place it between engagement and artifact. `artifacts.engagement_phase_label` snapshots the
  free-text label. The new record realizes that concept; it does not conflict with it.
- Discovery observations (Phase 204/216) are explicit consultant statements with an optional
  prompting question (whose category places them in a discovery domain) and a basis. They are the
  only legitimate grounding for a roadmap suggestion. Answers guide discovery and never establish
  anything (Phase 216, Contract C4).
- Artifacts and versions are engagement-scoped and immutable; a proposal or final report artifact
  can later bind to a phase by an added `engagement_phase_id` on `artifacts`.
- Discovery observations cannot be reused as phase-work records: the assessment and Final Report
  compose from them, so phase work would leak into the report. Phase work gets its own records.

## Model (migration `022_engagement_roadmap_work_plan`, four new tables)

| Table | What it is | Mutability |
|---|---|---|
| `roadmap_items` | Proposed future work: sequence, title, problem framing, rationale, expected outcome, source observation ids, origin (`peak_method` / `consultant` / `si_suggested`), template key, method version | Framing fixed at creation; revision = new item with `supersedes_item_id`. Lifecycle: proposed → accepted / deferred / declined; superseded |
| `engagement_phases` | One authorized unit of work: origin (`roadmap_item` / `manual` + required reason), title, scope, status planned → authorized → completed, authorization basis/reference/who/when, completion who/when | Status columns only |
| `phase_tasks` | Ordered guided tasks of one phase: instructions, why, what to observe, suggested evidence kinds, follow-up questions, expected result, required, requires-record, prerequisites, one condition (an earlier task recorded a given record kind), origin, template key, inclusion reason, `added_after_authorization`, status, notes, result summary | Framing fixed; only progress columns change |
| `phase_task_records` | What the consultant recorded: note, interview response, measurement, mismatch (structured fields per kind), basis; photo / document photo / document reserved | Insert-only (ORM listeners refuse update/delete); a correction supersedes |

Work-plan state is derived (not_started / draft / active / closed). A proposal/fee binding is not a
column; it is future artifact binding.

## Rules enforced (service `peak/workspace/engagement_phases.py`)

- A Peak Method or synthesis roadmap item must cite observations of its own engagement
  (`ungrounded_suggestion`). Suggestions (`peak/workspace/peak_method_phases.py`) are deterministic:
  a template is suggested when an observation falls in one of its discovery categories.
- Accepting a roadmap item authorizes nothing. Only an accepted item becomes a phase, at most once.
- Authorization is recorded by the engagement's Lead or an Admin, with a stated basis. Nothing infers
  it. No record or completion is possible before it.
- Tasks are completed only by the signed-in consultant, with a result summary, after prerequisites,
  and with a record when the task requires one. A synthesis-suggested task enters as `suggested` and
  does nothing until a consultant accepts it. Tasks added after authorization are marked.
- **Readiness** (`phase_readiness`): ready when the phase is authorized, the plan has a task, and
  every required task that applies is completed or resolved not applicable with a reason. Optional,
  suggested and unmet-condition tasks never block. A phase completes only when ready.
- Framing passes the advisory boundary (Contract C21, [`ADVISORY_ENGAGEMENT_BOUNDARY.md`](ADVISORY_ENGAGEMENT_BOUNDARY.md)).

## API

`GET /engagements/{id}/roadmap` · `POST /engagements/{id}/roadmap-items` ·
`POST /roadmap-items/{id}/decision` · `POST /roadmap-items/{id}/revision` ·
`GET|POST /engagements/{id}/phases` · `GET /phases/{id}` · `GET /phases/{id}/readiness` ·
`POST /phases/{id}/authorization` · `POST /phases/{id}/template-tasks` · `POST /phases/{id}/tasks` ·
`POST /phases/{id}/completion` · `PATCH /tasks/{id}` · `POST /tasks/{id}/acceptance` ·
`POST /tasks/{id}/completion` · `POST /tasks/{id}/not-applicable` · `POST /tasks/{id}/records`.

## Production implications (not performed)

- Apply `022` before an API deploy that reads the new tables (the existing routes do not read them).
- Grant the runtime role SELECT, INSERT on the four tables, and UPDATE on `roadmap_items`,
  `engagement_phases`, `phase_tasks` (none on `phase_task_records`). The Phase 50 gate's
  `APPROVED_TABLE_UPDATE` must be extended by the same approved step; it is unchanged here.
- Re-pin the production collation verifier at `022`.

## Validation

`tests/validate_phase217_engagement_roadmap_work_plan.py` (`make validate-phase217`, in
`make validate`); `--example` prints the receiving example end to end.
