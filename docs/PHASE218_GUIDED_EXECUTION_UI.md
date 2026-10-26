# Phase 218 — iPad-First Guided Execution UI

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `5921f68`.

## Purpose

Phase 217 built the primitives (roadmap items, separately authorized phases, ordered guided tasks,
insert-only task records, deterministic readiness) with no UI. Phase 218 lets a consultant on an
iPad, on site, open an authorized phase, see what to do next, follow each task's guidance, record
what they found, correct a record, complete or set aside a task, and see readiness, all in plain
language and without the rules being re-implemented in the browser.

Repository only: no migration, no production change, no deploy.

Not built: creating roadmap items or phases, recording authorization, adding template or consultant
tasks from the web (all remain API-only, see *Limitations*); proposals, fees, billing, photo or
document capture, SI generation, Final Report or artifact changes, role changes.

## The flow

```
Engagement page → "Engagement phases and work plans" (the engagement's phases, each with status and progress)
  → Phase workspace (/phases/{id})
      header: status, roadmap source, authorization basis and who authorized it
      "Next up": the first open task that applies and is not waiting on a prerequisite
      ordered task cards (number, Required/Optional, status, plain flags)
      suggested tasks, kept apart, each with "Add to the work plan"
      readiness panel; "Mark phase work complete" only when the API says ready
  → Task (/phases/{id}/tasks/{taskId})
      status panel: what is blocking completion, or done / not applicable / suggested
      guidance: what to do, what to look for, questions to ask, useful records,
                expected result, why it matters, prerequisites, condition, why included
      your records: current records, corrections, earlier versions kept and struck through
      record form: Note, Interview response, Measurement, Mismatch
      complete (result summary in the consultant's words) or mark not applicable (reason)
      link to the next task
```

A planned (not yet authorized) phase shows its plan read-only, with a notice that work starts once
the Lead or an Admin records authorization.

## API changes (read-only additions; no new endpoint, no new column)

`GET /phases/{id}` (and every response that returns the phase) now also returns:

| Field | What it is |
|---|---|
| `tasks[].work_state.applies` | `true` / `false` once a conditional task's condition is decided; `null` while pending or for a suggested task |
| `tasks[].work_state.prerequisites` | `[{task_id, sequence, title, resolved}]` |
| `tasks[].work_state.condition_task` | `{task_id, sequence, title}` or `null` |
| `tasks[].work_state.record_missing` | the task requires a record and has none current |
| `tasks[].work_state.completion_blockers` | `[{code, message}]`: `task_not_accepted`, `task_resolved`, `prerequisites_incomplete`, `record_required` |
| `tasks[].completed_by`, `tasks[].records[].recorded_by` | consultant names |
| `authorization.authorized_by` | consultant name |
| `roadmap_item` | `{id, title, status}` of the source item, or `null` |

`complete_task` now refuses with the first entry of the same `completion_blockers` list (same codes
and messages as before), so what the UI shows and what the API enforces cannot drift apart. The
phase-level check (`phase_not_authorized` and so on) is unchanged and separate.

## Web (Next.js, `web/`)

| File | Role |
|---|---|
| `lib/api.ts` | Phase 218 types (`EngagementPhaseDetail`, `PhaseTask`, `TaskWorkState`, `TaskRecord`, …) |
| `lib/work-plan.ts` | Pure helpers: record form definitions, labels, `recordPayload`, `splitRecords`, `nextTask`, `taskFlags`, `conditionText`. No rules; they read `work_state` and `readiness` |
| `app/work-plan-actions.ts` | Server actions: record, complete, not applicable, accept suggested, complete phase. Refusals show the API's message |
| `components/work-plan-record-form.tsx` | Record kind chooser and kind-specific fields; correction mode; never prefilled from guidance |
| `components/work-plan-actions.tsx` | Complete, not-applicable and single-button forms |
| `components/work-plan-parts.tsx` | Pills, task card, readiness panel, record list |
| `components/work-plan-section.tsx` | The engagement page's "Engagement phases and work plans" section |
| `app/(workspace)/phases/[id]/page.tsx` | Phase workspace |
| `app/(workspace)/phases/[id]/tasks/[taskId]/page.tsx` | Task page |
| `proxy.ts` | `/phases/:path*` added to the signed-in matcher |

iPad-first: single column on portrait, large tap targets (`min-h-touch`, task cards at least 80px),
no tables, existing tokens (`peak-card`, `peak-button`, `peak-input`, `bg-brand`), native radio,
`details` and form controls, no client-side state beyond form submission.

Records: the form offers only the four kinds the API accepts. A task's suggested photo or document
kinds are shown in its guidance as "not available yet", never as a form option. Structured fields
are optional; blank fields are not sent; a measurement value that is a plain number is sent as a
number. A correction is a new record that supersedes the old one; the old one stays visible under
"Earlier versions".

## Boundary

All new UI text stays inside the advisory boundary (Contract C21): no audit, compliance,
certification, assurance, deficiency or pass/fail language. Readiness is shown as "Ready to move
forward" / "Not ready yet" with the API's rule text, never a score. Phase work never calls the
discovery observation endpoints, and no Final Report or artifact is touched.

## Validation

`tests/validate_phase218_guided_execution_ui.py` (in `make validate`): read-only additions and
"reading creates nothing"; completion refused with exactly the reported first blocker; the four
record payloads built by `web/lib/work-plan.ts` under Node and accepted by the API; correction;
conditional task applying after its source task completes; not applicable with a reason; suggested
task accepted and marked as added after authorization; readiness to ready and phase completion; no
discovery observation created; every route the UI calls refuses logged out (401); static checks on
routes, actions, proxy, record kinds, no file or camera input, no guidance prefill, boundary text
scan, no observation endpoint, no new migration.

## Limitations (not fixed in Phase 218)

1. **No web path to start the workflow.** Creating roadmap items, accepting them, creating phases,
   recording authorization and adding template or consultant tasks are API-only. Until a later
   phase adds them, a consultant cannot get from discovery to a work plan in the web app.
2. Consultant notes on a task and an explicit "start task" are not exposed (recording a first
   record starts the task).
3. Photo and document capture remain reserved (Phase 217).
4. The sidebar does not highlight a section on `/phases` pages.
5. Records created within the same second are ordered by id, not entry order (Phase 217 ordering
   by `created_at, id`); display only.
