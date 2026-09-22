# Phase 206 — Discovery-to-assessment integration

Phase 204 gave consultants structured discovery: a North Star, interviews, answers and
observations. Phase 205 put it in production. But discovery lived on its own screen, and the
internal assessment — the Phase 113–119 persisted-state route — could not see any of it. Phase 206
joins them, and the whole point of the phase is *how* it joins them: side by side, under separate
labels, with the governed side untouched.

Baseline `9388958` — *Record Phase 205 discovery production cutover*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: built and validated locally. Not deployed.** The production API remains at Phase 205.

> **OPEN ITEM, carried forward and still open: production Admin acceptance is pending provisioning
> of `admin@peakinventorysolutions.com`.** Once that mailbox exists: bootstrap the Admin, sign in,
> verify the Dashboard, verify Consultants, sign out, sign back in, and only then record Phase 203
> authenticated acceptance complete. **No temporary Admin may be created.**
>
> **Authenticated production discovery acceptance also remains pending**, for the same reason: no
> production user can sign in yet, so Phase 204/205 discovery has never been exercised live under
> authentication. Phase 206's assessment inherits that gap — nothing on this page has been
> exercised against production.

## The distinction this phase is built around

Peak already has a governed evidence route. Evidence records are written by controlled writers,
reviewed, given a reliability and a claim scope, and only then — under the Phase 117 rules — does a
finding become eligible for a bounded Phase 118 recommendation.

Discovery is not that. A discovery answer is what somebody said in an interview. An observation is
what the consultant thought while listening. Both are valuable, and neither has been reviewed by
anyone.

So Phase 206 keeps them apart, deliberately and visibly:

| | Evidence-backed material | Consultant discovery material |
|---|---|---|
| Written by | controlled writers | the Phase 204 consultant workspace |
| Reviewed | yes, by review records | no |
| Carries reliability / claim scope | yes | **no field for it** |
| Can produce a formal recommendation | yes, when Phase 117 says eligible | **never, on its own** |
| Labelled in the document as | "evidence-backed, governed material" | "consultant working material" |

**Phase 117/118 eligibility was not touched.** Not widened, not softened, not consulted for
discovery. A discovery finding is not blocked from recommendation eligibility — it has no
eligibility field at all, so there is no attribute for a later change to flip. The Phase 206
harness asserts exactly that, by inspecting the dataclass fields rather than a value.

## What was built

Two new modules, both read-only, plus one optional field on the existing assessment.

### `peak/db/discovery_assessment_reader.py`

The discovery counterpart of `engagement_packet_reader`, following its rules: every statement is a
`select()` over an explicit whitelisted column list, the caller owns the connection, and the module
holds no credential, opens no session, reads no environment variable, and invokes no writer.

It reads the North Star from the engagement row, the engagement's sessions, answers and
observations, the active question pool, and the consultant names needed to say who recorded what.
`discovery_sessions.notes` is deliberately **not** selected: it is a free-text scratch column, and
the assessment reports coverage and observations rather than interview notes.

### `peak/reports/discovery_assessment.py`

A pure projection — no database import, no network, no environment, no LLM — producing
`DiscoveryAssessmentContext`:

```
DiscoveryAssessmentContext
├─ north_star, north_star_context, workspace_stamped
├─ coverage: InterviewCoverage
│    total / completed / in_progress sessions, interviewees, interviewee_titles,
│    answered_questions, active_questions, unbranched_active_questions,
│    answered_unbranched_questions, branching_makes_percentage_ambiguous,
│    sessions: [InterviewSummary(session_id, interviewee_name, interviewee_title,
│                                status, conducted_by, answered_count)]
├─ findings: [DiscoveryFinding]
│    finding_id, statement, category, source_type, source_ids, trace,
│    low_hanging_fruit, estimated_effort, estimated_value,
│    status, internal_only, requires_human_review
├─ low_hanging_fruit: [LowHangingFruitCandidate]
└─ available, status, internal_only, requires_human_review
```

Note what `DiscoveryFinding` does **not** have: `review_status`, `reliability`, `claim_scope`,
`recommendation_eligible`.

### The assessment itself

`InternalAssessment` gained one optional field, `discovery`. `build_internal_assessment` gained one
optional argument. Discovery is attached **after** every evidence decision is final — after
findings, recommendations, confidence notes and limitations are computed — so there is no order of
operations in which discovery material could influence one. Passing `None` yields exactly the
document Phases 116–118 produced.

## Discovery-derived findings

**One finding per consultant observation, and nothing else.**

An answer is a response to a question the consultant asked. An observation is a statement the
consultant chose to make. Only the second is a finding — and only because the consultant already
wrote it as one, which is why the statement is the `observation_text` **quoted exactly as stored**,
never re-worded, summarised or expanded. An observation whose text is blank states nothing and
becomes no finding.

`direct_structured_answer` exists as a reserved `source_type` name for the narrow future case where
a structured answer supports a statement with no interpretation at all. **Nothing produces it
today.** Turning answers into findings is inference, and this phase does not infer.

Each finding carries `source_type`, `source_ids`, a trace (below), the consultant's own
low-hanging-fruit flag, effort and value, `status = consultant_working_material`,
`internal_only = true` and `requires_human_review = true`.

**There is no LLM anywhere in this path.** No synthesis, no summarisation, no scoring, no ranking,
no root cause, no ROI, and no alignment claim.

## North Star

Rendered at the top of the assessment, as orientation. Statement, then optional context.

It scores nothing. No finding is ranked, weighted, or described as aligned or misaligned with it,
and the page says so in as many words. That is a deliberate stopping point, not an oversight.

## Interview coverage

Counts, not completeness estimates:

- interviews total, completed, in progress;
- people interviewed, and the roles represented;
- distinct questions answered, against the active pool size.

**Why there is no pool-wide percentage.** Branching means a follow-up question is shown only to
interviewees whose earlier answer matched, so the set of questions a given interview *should* have
covered depends on that interview's own answers. "22 of 29" would be arithmetic over a denominator
that differs per interview. The projection therefore reports the unbranched count separately —
"4 of the 22 questions every interview sees" — and sets
`branching_makes_percentage_ambiguous` so the caller can say why the other number is missing. The
module refuses to compute the misleading figure at all.

A blank answer is not coverage: only answers carrying text are counted.

## Low-hanging fruit

Consultant-flagged observations only. Each shows the statement, category, the consultant's entered
effort and value, and its source interview and person.

They are **grouped** for readability — high value first, then low effort, then finding id so the
order is stable — and anything the consultant left blank sorts last, because an unstated level is
not a low one. Both the document and the UI label this as a display grouping, in those words, and
say it is not a score, a ranking, or a priority order.

**No ROI is calculated.** A low-hanging-fruit flag is the consultant's own mark on their own
observation. It is not an approved recommendation, and the page says so on every card.

## Traceability

Every discovery-derived finding answers "where did this come from?" through a `DiscoveryTrace`:
`session_id`, `interviewee_name`, `observation_id`, `question_id`, `answer_id`,
`question_prompt`, and the recording consultant's name and id.

**Human-readable first.** The UI leads with a link to the interview by the interviewee's name and a
link to the observation itself; the raw record identifiers sit in a collapsed "Record identifiers"
detail, which matches how the rest of the workspace treats internal ids. An observation recorded
outside an interview says so rather than showing an empty link.

## Assessment API

One read endpoint:

```
GET /engagements/{engagement_id}/assessment
  -> { engagement, assessment, markdown }
```

Read-only and derived on every request from persisted records. There is deliberately **no write
endpoint and no assessment table**: the assessment is a view of stored state, so the only way to
change it is to change that state through the existing paths, and it can never drift from them. The
harness confirms POST, PATCH, PUT and DELETE on that path are refused, and that repeated reads are
identical and change nothing.

A missing engagement and one not visible through the Phase 57 primitive both return 404, so the
route never reports the existence of an engagement it may not show.

## Consultant UI

`/engagements/[id]/assessment`, reachable from a button on the engagement page.

Every section carries a badge naming what kind of material it holds — "Consultant working material"
or "Evidence-backed · governed" — so a consultant never has to infer it. Sections, in order:
North Star, discovery summary, discovery-derived findings, low-hanging-fruit candidates,
evidence-backed findings, internal recommendations, review status and limitations.

Responsive with the existing shell and tokens: cards throughout, `min-h-touch` targets, stacked on
phones with no horizontal scrolling, two-column card grids from `lg` up, and a four-up coverage
stat row that folds to two columns on narrow screens.

It is **not** the final client report, and it does not try to be. No PDF, no export, no proposal, no
client-facing rendering.

## No new persisted state

**There is no migration 018, and Phase 206 adds no table, no column and no write action.**

Everything is derived from records Phase 204 already persists. The workspace write allowlist still
holds exactly the ten Phase 204 discovery actions and nothing named "assessment". Derived findings
are not cached, because caching them would create a second source of truth that could disagree with
the records.

## Governance

Read-only integration. Phase 206 modifies no `owner_id`, no `authorization_scope`, no publication
or client-facing flag, no review state, no evidence reliability rule, and no recommendation
eligibility rule. `peak/workspace/discovery.py` and `peak/persistence/allowlist.py` are **unchanged
by this phase**. Nothing is published to AgentNet.

Every discovery-derived section is `internal_only = true` and `requires_human_review = true`, and
the assessment as a whole remains `client_facing = false`.

## The Phase 59 internal-test engagement

The historical production internal-test anchor does not carry the Phase 202 workspace stamp, and
**discovery authorization was not weakened to let it hold discovery records.** It simply has none,
which is the ordinary case the projection already handles: `available` is false, the discovery
sections say plainly that no discovery material was recorded, and the evidence-backed sections
render exactly as before.

An evidence-only engagement still renders. An engagement with neither still renders. Both are
asserted by the harness.

## Validation

- `tests/validate_phase206_discovery_assessment_integration.py` — new, in `make validate`. Offline,
  temporary SQLite only, no network and no production contact. It covers all ten required proofs,
  plus the no-migration, no-new-write-action and pure-projection rules.
- `tests/validate_phase113_persisted_state_reporting_path.py` — **one shape assumption updated.**
  It exercises the one-call workflow with a dummy connection object, which worked while the
  workflow made exactly one read. The workflow now makes two, so the harness stubs the discovery
  read as empty — which is the no-discovery case, and it asserts the resulting document is
  byte-identical to the lower-level Phase 116–118 route. No invariant was weakened; a new assertion
  was added that the workflow carries no discovery context when there is no discovery data.
- `make validate` — 82 harnesses, exit 0 (81 before this phase).
- `npm run build` and `npm run lint` from `web/` — clean.

## Production

**Nothing was deployed, and nothing in production was touched.** No schema change, no grant change,
no production discovery data, no Admin bootstrap.

**Render Auto-Deploy remains OFF.** API deploys stay manual until a later phase explicitly changes
that, and the repository is expected to run ahead of the live API — which it now does: production
runs Phase 205 code while Phase 206 sits in the repository.

## Known limits

- Discovery findings come from observations only; answers contribute coverage counts, not findings.
- Observations are ordered by `created_at` then id, and `created_at` has one-second resolution, so
  several observations recorded in the same second fall back to id order. Deterministic, but not
  meaningfully chronological at that granularity.
- Interview coverage counts distinct questions answered across the engagement; it does not model
  per-interview expected question sets, which is what a defensible per-interview completeness
  figure would need.
- None of this has been exercised against production, under authentication, by a real consultant —
  see the open item at the top.
