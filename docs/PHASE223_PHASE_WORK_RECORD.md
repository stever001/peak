# Phase 223 — Phase Work Record

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `14ed1f9`.

**Status: repository and local only.** No migration, no production action. Not deployed.

## Purpose

Phases 217–222 let a consultant do an authorized phase's work and record it: task outcomes (217,
218), records and corrections (217, 218), photos and documents (220), links from observations to
captures (221) and observations written during a task (222). Phase 223 puts everything recorded
during one engagement phase on one read-only page, task by task:

```
Engagement phase → agreed tasks, in order → for each task:
    outcome (result summary / not-applicable reason) · records · captures · observations (+ links)
```

## Problem

All of this is recorded, but only per task. To see what a phase actually produced, a consultant or
Lead has to open every task page in turn: up to three sections each (records, photos, observations),
behind a status-only task list. There is no single place to:
- review the work before marking the phase complete;
- hand a phase over to a colleague or the Lead;
- look back at a completed phase.

Phase 217's purpose was for findings and the Final Report to "rest on completed, documented work".
That needs the documented work to be readable as a whole.

## Why this is next

The guided-work chain is complete for *recording*. What it lacks is *reading back*. The record:
- needs no new state. Every fact it shows is already persisted by Phases 217–222;
- is deterministic composition (Contract C3): no model, no inference, no new decision;
- is the precondition for any later step that uses phase work. A Lead cannot sensibly review,
  issue or cite phase work they cannot see as a whole.

Alternatives considered and set aside:
- **A consultant-written phase close-out summary** needs a new column or table and new authored
  state. The task result summaries already hold the consultant's words.
- **A Lead review or sign-off of phase work** adds authority, which nothing in the authorities asks
  for.
- **Phase work in the assessment or Final Report** changes the one canonical report (C7) and
  recommendation inputs (C5). That is a larger, separately governed decision.
- **An issued phase-record artifact version** needs artifact binding to phases (AL1, C9). It is
  premature before the working view exists.

## Rules

1. **Composed, never stored.** The record is read from Phase 217–222 rows on every request. There is
   no table, cache or saved copy. It is not an artifact or artifact version (AL9: a view of working
   state is not issued).
2. **Nothing added.** Every word shown was written by a consultant. Peak orders and counts rows. It
   does not summarize, conclude, rank, score or read a capture.
3. **One phase, one engagement.** Every row must name this phase *and* its engagement. Work
   observations come in only through their Phase 222 origin. Interview and engagement-level
   observations, other engagements' rows and suggested tasks are left out. A suggested task is
   counted, not shown.
4. **Readiness is the Phase 217 rule**, computed by the same `phase_readiness`. The record does not
   decide anything.
5. **Read-only.** Reading the record changes no row.

## Non-goals

No model-generated text, summary or observation. No OCR or interpretation of captures. No automatic
finding or recommendation. No export, PDF, DOCX, print layout or artifact version. No client
access, publication, capsule or AgentNet effect. No sign-off, approval, review state or new
authority. No audit, compliance or scoring language. No change to task or phase state, readiness,
the assessment or the Final Report. No workflow-engine abstraction or refactoring.

## Interaction with Phases 217–222

| Phase | Used as | Changed? |
|---|---|---|
| 217 | Phase, tasks, task records, `phase_readiness`, `_applies` (condition outcome), `_phase_summary`, `_record_dict` | No |
| 218 | Phase workspace (one link added), `ReadinessPanel`, `RecordList`, `Pill`, `PhaseStatusPill` | Link only |
| 219 | Authorization basis/reference, roadmap item title | No |
| 220 | `phase_task_evidence` rows and content tokens (`/evidence-content/{token}`) | No |
| 221 | Link rows and `_item` capture shape, `EvidenceThumb` | No |
| 222 | `observation_task_origins`, `origins()`, `ObservationCard` | No |

## Data model and persistence

**No schema change.** No migration (the head stays `025_observation_task_origins`), no new table
or column, no allowlist action and no persistence classification. Nothing is written, so there is
no new write path and no grant implication.

## API

| Route | Auth | What it does |
|---|---|---|
| `GET /phases/{phase_id}/work-record` | session | The phase work record. 404 for an unknown phase. No other method (405) |

Response `work_record`:
- `phase`: the Phase 217 summary, with consultant **names** instead of ids (`authorized_by`,
  `completed_by`), and the roadmap item title;
- `engagement`: id, label and client name;
- `readiness`: exactly `phase_readiness`;
- `totals`: tasks; completed, not applicable, did not apply, open; current and corrected records;
  current and replaced captures; observations; linked captures;
- `tasks`: the agreed tasks in sequence. Each has `outcome` (`completed` / `not_applicable` /
  `does_not_apply` / `open`), its result summary or reason, who and when, every record (corrections
  marked with `superseded_by`), current captures (with a 15-minute `content_path`), the count of
  replaced captures, and the observations written during it, oldest first;
- `suggested_not_accepted`: the count of suggested tasks left out;
- `evidence_links`: each listed observation's linked captures, as in Phase 221;
- `composition`: the rule text, `stored: false`, `interpreted: false`.

No storage key, file name or content hash is returned. Ordering is deterministic: tasks by sequence,
then rows by creation time and id.

## UI

`/phases/{id}/record`, linked from the phase workspace ("Phase work record") once the phase is
authorized:
- the header names the client, engagement and phase. A note says every word is a consultant's own,
  with "How this record is put together" (the rule);
- scope, what the client agreed to (who recorded it and when), and completion;
- "At a glance": six counts in large tiles, two columns on an iPad in portrait and three on wider screens;
- "Task by task": one card per agreed task, with a touch-sized link to the task, Required/Optional,
  the outcome, the result summary or reason, then Records, Photos and documents, and Observations;
- the readiness panel (Phase 218), beside the tasks on wide screens and below them on an iPad.

The page has no form or action. Links are touch-sized, and no id is rendered as text.

**Degrade path.** The page loads the phase as before, then the record via `getPhaseWorkRecord`. If
the API has no route, fails or cannot be reached, that returns null and the page reads "The phase
work record is currently unavailable here." Every other page is unchanged.

## Authorization

The same as every phase read: any signed-in consultant (session cookie), and 401 when logged out.
There is no new role, permission or authority. Engagement scoping is by the phase's engagement, as
described under Rules.

## Provenance

Each item carries its own existing provenance:
- a task outcome: who completed or resolved it, and when;
- a record: who recorded it, when, and its basis;
- a capture: who added it and when;
- an observation: who recorded it, when, its basis and the task it was observed during;
- a link: who linked it and when.

The record adds no provenance of its own, because it is not stored.

## Assessment and report

None. The record is not read by the assessment, the Final Report (JSON, Markdown, DOCX) or any
artifact. Observations written during tasks continue to reach the assessment by the Phase 222 path,
unchanged.

## Readiness

The record displays readiness. It does not compute it differently or change it. Reading the record
completes nothing.

## Advisory boundary (C21)

All new text is advisory: "outcome", "Done", "Not applicable", "Did not apply", "Not finished".
There is no pass/fail, score or audit or compliance term (harness scan). Consultant-written content
is shown as written, as in Phases 217–222.

## Refusals

| Case | Response |
|---|---|
| Logged out | 401 |
| Unknown phase | 404 `not_found` |
| POST / PUT / PATCH / DELETE | 405 |
| Planned phase | 200, with nothing recorded and readiness `phase_not_authorized`. It is not an error: the plan is readable before authorization, as in Phase 218 |
| Row naming this phase with another engagement | left out |

## Production sequencing (when separately approved)

No migration, grant, environment or R2 change.
1. The commit is `[skip render]`. Vercel may build the web first: without the API route, the record
   page reads as unavailable and the phase workspace link leads there.
2. Deploy the API manually on Render, with Auto-Deploy still off.
3. Read-only checks: `GET /phases/{id}/work-record` returns 401 logged out, and 404 signed in for an
   unknown phase. The verifier and Phase 50 gate are unchanged (head 025).

Production has no phase today, so a populated read waits for the first real phase. As in Phases
220–222, no synthetic data is created for acceptance.

## Validation

`tests/validate_phase223_phase_work_record.py` (`make validate-phase223`, in `make validate`)
covers:
- no migration, table, allowlist or policy entry, and no write in the service;
- 401, 404, any signed-in consultant, 405 on write methods;
- planned, empty-authorized, mid-work and completed states;
- outcomes including a condition not met;
- verbatim summaries, reasons, records with corrections, and current and replaced captures;
- observations and their links, and totals;
- readiness identical to Phase 217;
- exclusion of engagement-level observations, other engagements, suggested tasks and forged
  cross-engagement rows;
- determinism, and a whole-database snapshot unchanged by reads;
- the assessment and Final Report unchanged;
- no key, file name or hash;
- the `getPhaseWorkRecord` degrade path under Node;
- static checks: no form or action, touch-sized links, no ids as text, the boundary scan, and no
  report or artifact code reading the record.
