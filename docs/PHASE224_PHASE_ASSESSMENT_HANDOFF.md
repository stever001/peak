# Phase 224 — Phase-to-Assessment Handoff

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `534aeac`.

**Status: repository/local only.** Not deployed. Production cutover is a separate decision (see
*Production sequencing*).

## Purpose

One outcome: **a consultant can carry what a phase's work showed into the assessment, in their own
words and with its link to the work, and can see what has and has not been carried.**

```
Phase work record → consultant reads the whole phase → writes observations on the tasks they rest on
                  → the existing assessment path, unchanged
```

## Problem

Phase 217 said findings and the Final Report should "rest on completed, documented work". The Phase
222 path does that, but only through observations, and only while a task is open. Walking a phase
through the code (temporary SQLite, synthetic data) showed:

| Step | Result before Phase 224 |
|---|---|
| Four tasks completed with records and result summaries, one set not applicable | Readiness `ready: true` |
| The internal assessment and Final Report | **0 findings.** No record or result summary reaches either |
| Phase completed | Allowed. Nothing says that none of this work reached the assessment |
| `POST /tasks/{id}/observations` on a completed task | 422 `task_resolved` |
| The same, after the phase is completed | 422 `phase_closed`, on every task |
| An engagement-level observation instead | 201, with no origin. It reads "Recorded outside an interview", and the phase's own work record leaves it out |

So the moment the Phase 223 record is complete is the moment it can no longer lead anywhere. A
consultant reasons best after seeing the whole phase, and by then every required task is resolved.
The template's closing task makes this easy to fall into: it asks for "a note per pattern", and a
note is a record, which never reaches the assessment.

## Why now

Phase 223 made the whole phase readable, which exposes the dead end. The first real phase would hit
it: production has no phase yet, so nothing has been lost so far.

## Why existing phases do not solve it

- Phase 222 allows the right action, but closes it at task resolution.
- Phase 223 shows the work, but deliberately offers no way forward and says nothing about what
  reaches the assessment.
- Discovery lets a consultant write an engagement-level observation at any time, but that loses the
  link to the work and is invisible on the phase's record.
- Readiness answers "is the required work complete?". It rightly does not ask whether anything was
  carried forward.

## Selected mechanism

The least autonomous mechanism that works (Contract C3): derived state plus an existing human action.

1. **Derived, read-only:** `assessment_handoff` on the work record, and `written_after_work` on an
   observation's origin. Neither is stored.
2. **Explicit consultant action, already built:** a work observation (Phase 222). Phase 224 narrows
   one refusal. **A work observation can now be written on any agreed task of an authorized or
   completed phase.** Nothing else about it changes.

No model, inference, deterministic conclusion, new authority or schema.

### Why narrowing the refusal is safe

The refusal did not protect anything:
- An observation written during a task could already be edited in place after the task resolved and
  after the phase completed. Evidence links could also be added then.
- An engagement-level observation could already be created at any time and cite the task in its text.
- Observations are consultant working material (C4), not part of the frozen work record.

So its only effect was to drop provenance. What is actually frozen stays frozen: records, captures,
task outcomes and phase status all keep their Phase 217–220 refusals.

### Why not a smaller mechanism

A read-only panel with a link to the engagement-level observation form would add no rule change, but
the observation would lose its task, read "Recorded outside an interview", stay off the phase's
record, and leave the panel reporting the task as uncarried forever. That loses the provenance Phase
222 exists to keep.

## Alternatives re-evaluated

The four items Phase 223 set aside, plus two more:

| | Close-out summary | Lead sign-off | Phase content in the Final Report | Issued phase-record artifact |
|---|---|---|---|---|
| Business outcome | One narrative of the phase | A recorded review of the work | The report shows phase work | A frozen, citable record |
| Currently missing? | Partly, but result summaries and the record hold it | No consumer: nothing downstream would read it | The need is real, but observations already reach the report | No audience: internal, and no client surface |
| Derivable? | No, it is new authored text | No, it is a new fact | Yes, by composition | Yes, by snapshot |
| New authority? | No | **Yes** | No | Needs AL1 phase binding and AL15 review semantics |
| Duplicates? | Result summaries, observations | Phase completion, and Lead artifact approval (AL15) | Observations | The Phase 223 view |
| Creates a finding? | No, so it would still reach nothing | No | **Risks it:** un-reviewed records presented as report content | No |
| Affects recommendation eligibility? | No | Would invite it, wrongly | **Risks it (C5)** | No |
| Needed before real use? | No | No | No | No |
| Verdict | Rejected | Rejected | Rejected | Rejected |

- **Deterministic next-phase decision.** Rejected. The roadmap already holds proposed work, the
  client's position and Peak Method suggestions. Work observations already feed those suggestions.
  No missing decision was found.
- **Gating phase completion on observations.** Rejected. It would make an observation a completion
  rule, contradicting Phase 222, and would change readiness. A phase with nothing worth carrying
  forward is legitimate.
- **Prefilling an observation from a record, or a "promote record" button.** Rejected. Phase 222's
  rule stands: the text starts empty and is written by the consultant. A record and an observation
  are different statements. The record stays visible for reference.

## Non-goals

No automatic finding, recommendation, observation or summary. No model use. No evidence
interpretation or OCR. No scoring. No sign-off, review state, approval or new role. No close-out
record. No change to readiness, task or phase status or completion rules. No new Final Report or
assessment content. No artifact, capsule, AgentNet or client-facing effect. No billing. No
workflow abstraction.

## Interaction with Phases 217–223

| Phase | Effect |
|---|---|
| 217 | Unchanged: readiness, completion, frozen records, insert-only rows |
| 218 | Phase workspace shows one short read-only panel; the task page's Observations form now also appears on a finished task |
| 219 | Unchanged |
| 220 | Unchanged: capture stays closed once a task resolves |
| 221 | Unchanged: an after-the-work observation may link current captures of the engagement by the same rules |
| 222 | **One rule narrowed:** `task_resolved` and `phase_closed` no longer refuse a new observation. `phase_not_authorized` and `task_not_accepted` stay. The origin gains derived `written_after_work` |
| 223 | The record gains `assessment_handoff` and one read-only section. Still composed, unstored, and without a form |

## Authority

**No new authority.** Any signed-in consultant may write a work observation, as in Phase 222, and the
signed-in consultant is recorded as its author. Keeping these acts distinct:

| Act | Who | Effect of Phase 224 |
|---|---|---|
| Record that work was performed | Consultant | None |
| Complete a task or phase | Consultant | None |
| State what the work showed (observation) | Consultant | Now also possible after the work |
| Authorize more work | Lead or Admin | None |
| Approve an artifact version | Lead, then Final Approver | None |
| Client acceptance | Not modelled | None |

Writing an observation is not a review, a sign-off or a conclusion that the phase is finished.

## Provenance

An observation keeps its existing provenance: author, time, basis, task and phase. An origin stays
insert-only, written once, in the observation's transaction.

**"Observed during" must stay true.** An observation written after the work is therefore shown as
"Written after the work on: Task n", and with the "Written after the work" pill.

`written_after_work` is derived on each read, not stored: true when the origin was created after the
task resolved or after the phase completed. Same-second writes read as during the work.

The comparison uses `updated_at` on the task and phase, not `completed_at`. A resolved task and a
completed phase are never updated again, so `updated_at` is when that happened, and it shares the
database clock with the origin's `created_at`. `completed_at` comes from the API host's clock, and
comparing across the two clocks would depend on the database's time zone.

## Persistence

**No schema change.** No migration (the head stays `025_observation_task_origins`), table, column,
allowlist action or persistence classification. No grant: discovery observations, origins and links
already have the INSERT they need, and the origin stays `append_only`. The verifier pin does not
move.

The questions a new persisted fact would have to answer:
- *What real-world fact is unrepresented?* None. That an observation was written after the work
  follows from existing timestamps. That work "was carried forward" follows from which observations
  exist.
- *Why not a "handed off" flag?* It would be a second, drifting copy of that, and would imply an
  authority and a finished state that do not exist.

## API

| Route | Change |
|---|---|
| `POST /tasks/{id}/observations` | Also accepts a resolved task, and any agreed task of a completed phase |
| `GET /tasks/{id}/observations` | `recording_closed` is now null for those tasks. It remains set for a planned phase or a suggested task |
| `GET /phases/{id}/work-record` | Adds `assessment_handoff` |
| Every read that returns an origin | Adds `written_after_work`, beside the assessment as before |

`assessment_handoff`:
- `open`: whether observations can be written on this phase's tasks (false only while planned);
- `observations`, `written_after_work`: counts;
- `without_observation`: each agreed task with recorded work (completed, or holding a current record
  or capture) and no observation, as `{task_id, sequence, title}`, in sequence;
- `rule`: the rule text;
- `stored: false`, `interpreted: false`.

## UI

Consultant-facing, touch-sized, and explicit about which kind of thing is on screen.

- **Work record: "What reaches the assessment"** (viewing derived state). The rule, the count, the
  tasks with recorded work and no observation, each with a "Write an observation" link, and a link to
  the internal assessment. It says that not every task needs one. Each task's Observations part also
  has the link. The page still has no form: the link goes to the task page.
- **Phase workspace:** a short panel with the same count and a link to that section, including when
  the phase is ready to complete and after it is completed. It says observations can still be written
  after completion. It does not block or nag.
- **Task page: Observations** (recording a statement). On a finished task, the section says the work
  is finished, its records stay as they are, and the observation will be marked as written
  afterwards. The form is collapsed unless the consultant arrived through "Write an observation". Its
  text starts empty. Records and captures remain closed.
- **Cards and traces:** the wording above, wherever an origin is shown.

**Degrade path.** Before the Phase 224 API is deployed, the web simply shows no panel, the field being
absent. The form follows `recording_closed` as given by the API, so it stays hidden.

## Readiness and phase status

No change. An observation is never a completion rule, and readiness does not read them. Writing one
after completion leaves `completed`, who completed it and when exactly as they were.

## Assessment

**The code is unchanged.** The existing authoritative input is `discovery_observations`, read by
`fetch_observation_summaries`. An after-the-work observation becomes a discovery-derived finding
quoting the consultant's text, exactly like any other. It is written by a consultant, not
manufactured. It is not `recommendation_eligible`, and no recommendation appears. `written_after_work`
is beside the assessment, not inside it.

Records, result summaries and captures still never become findings on their own.

## Final Report

The composer is unchanged. Such an observation appears as any observation does, with the existing
"Recorded outside an interview" trace. No phase content is added. C5 and C7 are untouched.

## Artifacts

None. The record stays unissued (AL9). A new observation changes working state only. It cannot alter
an existing artifact version (AL5, AL7), and including it in one needs a new version (AL12).

## Advisory boundary (C21)

New text speaks of observations, work and the assessment. There is no pass/fail, score or audit or
compliance language (harness scan). Consultant text is shown as written.

## Refusals

| Case | Response |
|---|---|
| Logged out | 401 |
| Unknown task | 404 |
| Planned phase | 422 `phase_not_authorized` |
| Suggested task | 422 `task_not_accepted` |
| Missing or blank text | 422 `invalid_field` |
| An interview named | 422 |
| Another engagement's capture | 422 `invalid_link`; the whole save is refused |
| A replaced capture | 422 `evidence_replaced` |
| Records on a resolved task or completed phase | 422 `task_resolved` / `phase_closed`, unchanged |
| Upload on a resolved task or completed phase | Refused, unchanged |
| Task progress or a second completion on a resolved task | Refused, unchanged |

## Production sequencing (when separately approved)

Deployment only: no migration, grant, environment, R2 or data change, and no verifier pin move.

1. The commit is `[skip render]`. Vercel may build the web first. Without the API change it shows no
   panel and keeps the form hidden on finished tasks.
2. Read-only preflight: head 025, 38 base tables, the verifier (431/431, 11/11), the Phase 50 gate,
   the 30-table baseline.
3. Deploy the API manually on Render, with Auto-Deploy still off.
4. Read-only checks, logged out: `GET` and `POST /tasks/{id}/observations` and
   `GET /phases/{id}/work-record` still return 401.
5. Repeat the preservation checks. Expect no change.

There is no production phase, so a populated check waits for the first real phase. No synthetic data
is created for acceptance. When the first real phase exists, confirm that an observation written on a
finished task creates exactly one observation and one origin, reads "Written after the work on", and
changes no task, phase or readiness state.

## Validation

`tests/validate_phase224_phase_assessment_handoff.py` (`make validate-phase224`, in `make validate`)
covers:
- no migration, model, allowlist, policy or verifier-pin change;
- the problem itself, reproduced first;
- observations accepted on resolved tasks and after completion; refusals kept;
- records, captures and task state still frozen;
- `written_after_work` true and false, and stable across an edit;
- only observations, origins and links change, by whole-database comparison;
- task and phase state, readiness and the completion stamp unchanged;
- assessment and Final Report behaviour: same finding shape, not eligible, no recommendation added;
- derived handoff counts, scoping and exclusions, determinism, reads writing nothing;
- no leaks;
- static UI checks.

The Phase 222 harness's resolved-task check and origin shape were updated deliberately for this rule.
