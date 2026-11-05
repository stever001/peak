# Phase 225 — Truthful Report Discovery Provenance

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `bd3c6bb`.

**Status: CLOSED in production (2026-11-05); the first live corrected sentence is deferred** (see
*Production cutover and closure*). Implementation `e86ae6f`.

## Purpose

One outcome: **a Final Report that holds observations made outside interviews says so, instead of
saying that all its discovery material was recorded during interviews.**

## Problem

Phase 224 made it normal for phase work to reach the Final Report through an observation. Following
one through the code (temporary SQLite, synthetic data), in an engagement with no interview at all:

| Where | Before Phase 225 |
|---|---|
| Interview coverage | `Interviews 0` |
| The finding's trace | "recorded outside an interview" (true) |
| The discovery section's opening sentence | "Recorded **during interviews**, not reviewed evidence…" (false) |
| The limitations section's boundary statement | "…working material recorded **during interviews**…" (false) |
| Where these appear | The internal draft, its Markdown and DOCX, **and the client-facing package** |

The report contradicts itself about where its statements came from, and a Lead and a Final Approver
would be approving that sentence. A statement of source is exactly what a reader relies on when
weighing an observation.

The sentence dates from Phase 206, when it was close to true. Engagement-level observations already
made it inexact. Phases 222 and 224 make it routinely false.

## Why now

The first real phase would hit it: its observations reach the next package prepared. Production has no
phase yet, so no package has carried a phase observation.

## Why existing phases do not solve it

- Phase 222 and Phase 224 added the route into the report, and chose not to touch the report.
- The per-finding trace is true, but cannot correct a section-level sentence that contradicts it.
- The Phase 213 staleness notice says the draft changed. It says nothing about what the draft states.

## Selected mechanism

The least autonomous mechanism that works (Contract C3): **one small deterministic rule, on facts the
report already holds.**

> If any discovery finding has no interview session, the two sentences read "during interviews or
> other consulting work". Otherwise they stay exactly as they are.

`discovery_not_evidence_text(findings)` holds the rule, once, in
`peak/reports/discovery_assessment.py`. The composer, the Markdown, HTML and DOCX renderers, and the
internal assessment's Markdown all use it. The internal draft page applies the same test to its own
opening line. No model, inference, new input or new read.

"or" keeps it true for a mixed report and for one with no interviews. Peak does not say which
observations came from where in these sentences: the trace does that already.

**A report whose findings all came from interviews is byte-identical**, so its content hash does not
change and its package still matches its draft.

## Alternatives rejected

| Candidate | Why not |
|---|---|
| Show the phase task on the Final Report page | Already one tap away: "Open observation" shows it, as does the assessment. Phase 222 deliberately kept origins off this view, and its checks still hold |
| Name the phase or task in the report's trace | New composer input, a change to every such report's content, and phase names in a client rendition (C8). "Recorded outside an interview" is true, so nothing needs correcting |
| Close the loop on the roadmap ("Accepted · Phase created" after completion) | Nothing there is false. The phase's status is on the same page and on the engagement page. No decision depends on it |
| Propose follow-on work from a phase | Work observations already feed suggestions and the roadmap form. Phase 224 found no missing decision |
| Warn when a package is out of date | Already built (Phase 213). Checked again: an observation written after a package flips `draft_matches_latest` |
| Phase recommendations | **A real gap, but not a small one.** Templates promise "recommended process changes", and discovery-derived findings can never produce a recommendation. Closing it is a C5 governance decision with new persisted state and authority. It needs its own decision |
| Change the sentence for every report | Simplest, but changes the content hash of every report, so every current package would falsely appear out of date |

## Non-goals

No automatic finding, recommendation or summary. No model use. No origin, phase name or task name in
the report. No change to any finding, trace, eligibility rule, readiness or completion rule. No change
to any stored version or package. No new section, route, table or authority.

## Authority

**None added.** The sentence is fixed text chosen by a fixed rule. Who may write an observation, prepare
a package, approve or release is unchanged.

## Persistence and schema

**None.** No migration (the head stays `025_observation_task_origins`), table, column, allowlist action,
grant or persistence classification. The verifier pin does not move. The sentence that sits in report
content is stored only when a consultant prepares a package, through the existing path.

## API and UI

No route or field is added. `GET /engagements/{id}/final-report`, `/final-report.docx` and
`/assessment` return the corrected sentence when the rule applies. The internal draft page's opening
line follows the same test.

**Degrade path.** Before the API is deployed, the page's opening line can read "or other consulting
work" above a limitations statement that still says "during interviews". That lasts only for the
window between the Vercel build and the Render deploy, on an internal page.

## Assessment and report

- The internal assessment's Markdown uses the rule. Its findings and structure are unchanged.
- There is one composition (C7): every rendition takes the sentence from the same rule on the same
  findings.
- The limitations boundary statement is report content. The opening sentence is rendered text. Neither
  affects a finding, and C5 is untouched: both still say the material carries no recommendation
  eligibility.
- The client rendition carries the corrected sentences. They pass the Phase 213 client-facing checks.

## Existing packages

Stored versions and renditions are never rewritten (AL5, AL7, AL47). An engagement that has a package
and an observation with no interview session gets a new draft sentence. Its panel then correctly says
that the live draft has changed. The package can still be reviewed as it is, and approvals do not
carry over to a new one. That is the existing rule working as intended. The cutover counts how many
engagements this reaches before the deploy.

## Readiness and status

No change to task or phase state, readiness or completion. Package and approval states are unchanged.

## Advisory boundary (C21)

The new wording names no pass/fail, score, audit or compliance concept (harness scan).

## Validation

`tests/validate_phase225_report_discovery_provenance.py` (`make validate-phase225`, in `make validate`)
covers:
- no migration, model, allowlist, policy or verifier-pin change;
- the rule on its own: interview-only, none, mixed, outside-only;
- the problem reproduced through the routes, and corrected in the draft, Markdown, DOCX, assessment
  Markdown and client package;
- a report from interviews only, or with no findings: content hash, Markdown, web rendition and
  assessment Markdown equal to the output of the baseline code, pinned from `bd3c6bb`, and its package
  still matches its draft;
- an earlier package's bytes, hash and state unchanged when the draft's sentence changes;
- findings, traces, eligibility and recommendations unchanged; no origin in the report; reads write
  nothing;
- static UI checks, including the Phase 222 rule that origins stay off this view.

## Production sequencing (as planned; performed below)

Deployment only: no migration, grant, environment, R2 or data change, and no verifier-pin move.

1. The commit is `[skip render]`. Vercel may build the web first (see the degrade path).
2. Read-only preflight: head 025, 38 base tables, the verifier, the Phase 50 gate, the 30-table
   baseline. Count the engagements with a release package and an observation with no session, which
   are the only ones whose live draft will differ from their latest package.
3. Deploy the API manually on Render, with Auto-Deploy still off.
4. Read-only checks: `/healthz` 200 and logged-out routes 401, as before.
5. Repeat the preservation checks. Expect no change: this phase writes nothing.

No synthetic data is created for acceptance. If the preflight count is above zero, a signed-in read of
one such draft can confirm the sentence. Otherwise acceptance waits for the first real phase's package.

## Production cutover and closure (2026-11-05)

**Status: complete (2026-11-05). Phase 225 is CLOSED**, with one deferred acceptance item (below).
Deployment only: no migration, grant, environment, R2, verifier-pin or data change. No production
data was written.

**Preflight (read-only).** The repository was clean at `e86ae6f`, with HEAD equal to `origin/main`.
As `peak_prod_verify_ro`:
- head `025_observation_task_origins`, single row;
- 38 base tables, matching the repository;
- `roadmap_items`, `engagement_phases`, `phase_tasks`, `phase_task_records`, `phase_task_evidence`,
  `observation_evidence_links` and `observation_task_origins` all 0 rows;
- the 30-table `COUNT(*)` + `CHECKSUM TABLE` baseline (133 rows) identical to the Phase 224 closure
  snapshot;
- verifier `verified_safe_no_remediation_required`: head matches, 431/431 governed columns
  deterministic, 11/11 idempotency boundaries safe, 0 at risk, no warnings.

The Phase 50 gate passed as `peak_prod_runtime`, and `/healthz` returned 200.

**Affected engagements (read-only count, none modified).** 2 engagements hold both a stored package
and an observation with no interview session. Both are retired (`deleted_at` set), and 1 of them has a
released package. **0 live engagements are affected**, so no active reviewer's draft now differs from
its package because of this phase.

**Web.** GitHub reports the Git-connected Vercel production deployment of `e86ae6f`
(`dpl_Da9ExV6LMme7S3x5xiWoBfSq1BoS`) as `success`. No extra deployment was triggered. `/login` returned
200 after the API deploy.

**Release (as read from Render by the operator).**
- Render API `peak-consultant-api`, deploy `dep-dbmc2k3bc2fs738ssrp0` of
  `e86ae6fb34b2f4ed782dc34791f8f1454cc42dab`, trigger manual.
- Started 2026-11-05T17:48:00Z, finished 17:49:07Z, status **Live**, instance
  `srv-dan03c3tqb8s73a39tgg-pcp67`.
- It replaced `dep-dbl2bdp42hec73dlmq4g` (`177fea8`).
- Auto-Deploy stayed Off.
- Startup was normal ("Application startup complete", Uvicorn running). The new deployment logged 0
  errors, 0 critical events and 0 warnings.

**Production checks (read-only, logged out):**
- `/healthz` returned 200 on six consecutive requests;
- `GET` on `final-report`, `final-report.docx`, `final-report/packages` and `assessment` under
  `/engagements/nonexistent/` returns **401**;
- `GET /engagements/nonexistent/phases`, `/phases/nonexistent/work-record`,
  `/tasks/nonexistent/observations`, `/auth/me` and `/engagements` return **401**;
- a route that does not exist returns **404**.

Phase 225 adds no route, so logged-out checks cannot tell the new code from the old. That the new code
is live rests on the Render deploy record above.

**Preservation (read-only, after the deploy):**
- head `025_observation_task_origins`, 38 base tables, no table's `CREATE_TIME` changed;
- the seven Phase 217–222 tables all 0 rows;
- the 30-table baseline unchanged at 133 rows, `changed_tables = []`;
- runtime grants identical to the preflight;
- the Phase 50 gate PASS;
- the verifier `verified_safe_no_remediation_required`: head matches, 431/431 governed columns
  deterministic, 11/11 idempotency boundaries safe, 0 at risk, no warnings;
- the verifier pin stays at `025`: Phase 225 has no migration.

**Deferred acceptance.** The corrected sentence has **not been observed live**. The only affected
engagements are retired, so there is no live qualifying engagement, and no synthetic report or
observation was created for acceptance. This is an operational acceptance item, not unfinished
implementation: the behaviour is covered by the Phase 225 harness.

When the first real qualifying engagement exists, confirm with a signed-in read that:
- its live draft says "during interviews or other consulting work";
- any package prepared before that observation is unchanged, and its panel shows that the live draft
  has changed.
