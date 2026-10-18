# Phase 216 — Discovery instrument hardening

Phase 216 replaces the 29-question MVP discovery pool with the **Peak discovery instrument**: the
smallest question set that reliably exposes operational problems Peak can help solve, with a
recorded rationale and source provenance for every question. Baseline `312a2c6` — *Record Phase
215 production acceptance and closure*. Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: implementation committed as `3025614`. Migration `021_discovery_observation_trace_basis`
is applied to production (2026-10-17), and the verifier pin is at 021 and green. The API and web
deploys and the instrument seed follow this record**; see "Production rollout".

Authorities:
- [`PEAK_PROJECT_CONTRACT.md`](PEAK_PROJECT_CONTRACT.md) is unchanged. C4 (*discovery is not
  evidence*) and C5 (recommendation governance) apply as before.
- [`ARTIFACT_LIFECYCLE.md`](ARTIFACT_LIFECYCLE.md) is unchanged.

## Governing rule

**Question answers may:**
- determine which question is displayed next;
- trigger conditional follow-ups;
- trigger evidence requests;
- guide or contextualize consultant observations.

**Question answers may not, by themselves:**
- create a finding;
- become governed evidence;
- authorize a recommendation.

**How this holds in the code:**
- A finding is a consultant observation (Phase 206), quoted exactly.
- An observation may name the question that prompted it and its basis. It stays discovery material.
- The next question is chosen only by the stored deterministic branch (one earlier question,
  `equals` / `not_equals` a value). No model selects questions.
- The rule is stated in `peak/workspace/discovery_instrument.py` and `peak/workspace/discovery.py`,
  and the Phase 216 harness checks it.

**Question-selection rule.** A question earns its place only if it does at least one of these:
- exposes a meaningful operating condition;
- supports or eliminates a potential finding;
- requests evidence needed to substantiate a finding;
- determines what is asked next.

## The instrument

Source: `peak/workspace/discovery_instrument.py`, version `peak.discovery_instrument.2026-10.v1`.

**Questions.** There are 29 core questions, asked in every interview, and 17 conditional
follow-ups. Ten core questions are diagnostic gates.

| Section | Core questions (gates marked ◆) | Follow-ups (shown when) |
|---|---|---|
| Context and goals | `ctx_operation`, `ctx_traceability` ◆, `goal_pain_incident`, `goal_impact`, `goal_north_star` | `trace_how`, `trace_evidence` (traceability = yes) |
| Record reliability | `acc_check_before_promise` ◆, `acc_phantom` ◆, `acc_how_known` ◆, `acc_discrepancy_cause` | `acc_distrust_reason` (≠ Rarely); `acc_phantom_example`, `acc_phantom_evidence` (phantom = yes); `acc_results_evidence` (measured regularly); `acc_physical_variance` (physical inventory) |
| Receiving and storage | `rcv_walkthrough`, `rcv_exceptions`, `loc_recorded` ◆ | `loc_how_found` (≠ every item) |
| Replenishment and fulfillment | `repl_trigger`, `pick_method_confirm` ◆, `pick_error_detection` ◆ | `pick_confirmation` (paper); `pick_error_volume` (customers report) |
| Counting and adjustments | `count_method` ◆, `adj_control`, `adj_reviewed` ◆ | `count_program` (≠ no regular counting); `count_why_not` (no regular counting); `adj_history_evidence` (review = no); `adj_review_evidence` (review = yes) |
| Returns and stock condition | `rtn_damaged`, `excess_obsolete` | — |
| Systems and data | `sys_record`, `sys_handoffs`, `item_master` | — |
| People and accountability | `own_accuracy`, `people_dependency`, `labor_rework` | — |
| Management measures | `kpi_reviewed` ◆ | `kpi_which`, `kpi_report_evidence` (yes); `kpi_missing` (no) |
| Close | `prior_attempts`, `constraints` | — |

**Session size**, checked exhaustively over every combination of gate answers:
- 29 questions before any gate is answered;
- at least 32 once every gate is answered, because `count_method`, `adj_reviewed` and
  `kpi_reviewed` each open one side of a pair whatever the answer;
- at most 42.

Deeper probing is conditional. Nothing is added for everyone.

**Evidence requests.** Six follow-ups are evidence requests:
- `trace_evidence`
- `acc_phantom_evidence`
- `acc_results_evidence`
- `adj_history_evidence`
- `adj_review_evidence`
- `kpi_report_evidence`

Each prompt begins "Evidence request:" and is answered *Provided* / *Will provide* / *Not
available*. That answer records the state of a request; it is not the evidence. Two text
follow-ups, `acc_physical_variance` and `pick_error_volume`, also ask whether a record exists.

**Rationale catalogue.** Every question defines 12 fields:
1. question wording;
2. domain;
3. purpose type (fact, symptom, process description, evidence request, control check, root-cause
   probe, desired outcome);
4. why it matters;
5. healthy indicators;
6. risk indicators;
7. corroborating evidence;
8. follow-up triggers;
9. permitted finding classes;
10. what the answer cannot support by itself;
11. common novice mistakes;
12. recommendation relevance.

The catalogue is keyed by the stable question key and versioned in the repository. It is never
written to the database. It is source material for a later Peak Method Consultant Training &
Certification phase. **No training, lesson, examination or certification feature is built here.**

**Finding classes.** These 14 provisional codes are diagnostic classification vocabulary, not
evidence that a finding exists. The observation form offers them for its category.

| Code | Covers |
|---|---|
| ACC | record inaccuracy |
| CTRL | transaction control / authorization |
| PROC | process step |
| LOC | location / storage |
| REPL | replenishment |
| FUL | picking / fulfillment |
| COND | returns, damaged, excess, obsolete stock |
| DATA | item master data |
| SYS | systems and handoffs |
| VIS | measurement / visibility |
| OWN | ownership |
| PEOPLE | key-person dependency / training |
| TRACE | traceability |
| IMPACT | business consequence; supports a finding, never stands alone |

**Old-to-new mapping.** The 29 Phase 204 questions (`peak/workspace/initial_questions.py`, kept as
history) are superseded (`SUPERSEDED_PHASE204_KEYS`):
- **merged:** `goal_success` + `goal_90_days`; `acc_confidence` + `sys_trusted`; and the four
  `cc_*` counting questions;
- **removed:** `put_directed` (low yield for a small business); `cc_blockers` (redundant, and shown
  even after "no");
- **revised:** all the rest.

Every new key is distinct from every old key, so the instrument never overwrites a Phase 204 row.

## Source provenance

`PROVENANCE` and `SOURCES` in the same module record, for every question:
- its primary sources, and for each source which of these it supports: inclusion, wording,
  interpretation, evidence, follow_up;
- further reading;
- what would trigger a revision.

**Basis.** The basis is derived from the sources:
- `external`: 30 questions;
- `mixed`: 7 questions;
- `peak_method_design`: 9 questions, labelled plainly: `goal_impact`, `goal_north_star`,
  `count_why_not`, `sys_record`, `sys_handoffs`, `labor_rework`, `kpi_missing`, `prior_attempts`
  and `constraints`.

**Sources are used selectively**, only where they materially shaped a question:

| Kind | Sources |
|---|---|
| Practical inventory and warehouse | Piasecki's *Inventory Accuracy* and *Inventory Management Explained*; Frazelle; Richards; the ASCM dictionary; WERC DC Measures |
| Controls and audit | COSO 2013; AICPA AU-C 501; FASB ASC 330 |
| Traceability | FDA FSMA §204; GS1 |
| Organizational knowledge | ISO 9001:2015 §7.1.6 |
| Research on record inaccuracy and stockouts | DeHoratius & Raman (2008); Kang & Gershwin (2005) |
| Interview method | Flanagan's critical incident technique |
| Root-cause questioning and waste | Ohno |
| Returns | Rogers & Tibben-Lembke |

No citation was added to fill a field.

**Verification (2026-10-17, `SOURCES_VERIFIED_ON`).** This was proportional, not a literature review.
Every one of the 18 external sources was checked against publisher, library, standards-body or
regulator records to confirm that it exists, its author or organization, title and edition, and
that it reasonably supports the role attributed to it. No source failed, so none was removed.

Corrections made:

| Source | Correction |
|---|---|
| ASCM dictionary | Edition recorded: the 19th is current |
| Piasecki, *Inventory Accuracy* | 1st edition 2003 confirmed; a 2nd edition (2021) noted |
| Piasecki, *Inventory Management Explained* | Full subtitle and ISBN added |
| Frazelle | 2nd edition, McGraw-Hill Education, **2016** (it revises the 2002 edition) |
| Richards | Current title is *Warehouse Management: The **Definitive** Guide to …*, 4th edition, Kogan Page, 2021; earlier editions were "A Complete Guide" |
| Rogers & Tibben-Lembke | Year corrected from 1999 to **1998** (title page); some library records give c1999 |
| FSMA 204 | Section cited (§1.1300 et seq.); compliance date recorded as extended from January 20, 2026 to **July 20, 2028**, and added to the revision trigger |
| GS1 Global Traceability Standard | Release 2.0 (August 2017) |
| GS1 General Specifications | Revised regularly (Release 25, January 2025, the latest seen) |
| ISO 9001 | 2015 edition plus Amendment 1:2024; a revised edition is in final stages, now a revision trigger for `people_dependency` |
| DeHoratius & Raman; Flanagan | DOIs added |
| COSO | Principles 5 and 10 named |
| AU-C 501 | Paragraphs .11–.14 named |
| WERC | Noted that the metric set changes by edition |

Roles narrowed where a source supports less than first claimed:
- **DeHoratius & Raman** now support only the *inclusion* of `acc_check_before_promise`. It is a
  retail study of record inaccuracy, not of checking behavior, so the behavioral interpretation is
  Peak's.
- **GS1 General Specifications** now support only the *inclusion* of `item_master`, not its
  evidence expectation.
- **Ohno** moved to further reading for `labor_rework`, which is now labelled a Peak Method design
  choice.

No page numbers are given. Training material that quotes a source adds page references from the
copy used.

`peak_field_observation` (*Peak field observation / consultant-added question from prior
engagement*) is a registered internal source kind. It is how a promoted supplemental question
would be cited, without client-identifying information. No question cites it yet.

## Canonical and supplemental questions

**Canonical questions** are the rows with a `seed_key`, inserted from the instrument by
`tools/init_discovery_questions.py`. They are globally authoritative for the Peak Method:
- Only an Admin may edit, deactivate or reactivate one. `update_question` refuses
  `admin_required`, which the API returns as **403**.
- The default with no role is refusal.
- The API never accepts `seed_key`, so it cannot create a canonical question.

**Global questions are Admin-controlled.** A question with no engagement is asked in every
interview, so only an Admin may create, edit or deactivate one, whether canonical or not. A
Consultant gets **403** `admin_required`, and the service refuses by default. The question pool's
"Add global question" control and the global form are shown only to an Admin.

**Supplemental questions** are the rows without a `seed_key` that belong to one engagement. A
Consultant may add them only within an engagement; there is no Consultant-created global question.
- Added from an engagement's Discovery section or an interview, a supplemental question records
  its field-use provenance. It is set at creation and never editable:
  - `engagement_id`, the engagement it was added in, which is the only place it is asked;
  - `added_by_consultant_id`, the signed-in consultant;
  - `created_at`.
- It also carries a required `rationale` (why it was asked), an optional `domain` and optional
  `finding_classes` tags, and an optional branch on an earlier question asked in the same
  interviews (the triggering parent question or answer).
- **Usage is derived, never stored.** `usage` counts answers with text, and observations that name
  the question.
- Any consultant may edit an engagement's supplemental question.

This is not a custom-question framework. It is five nullable columns and one scoping rule.

**Promotion is manual and outside the application (future review boundary).** Nothing in Phase
216 can make a supplemental question canonical or global: the API never sets `seed_key` or clears
`engagement_id`. Promotion is a deliberate Admin review of the instrument, done as a reviewed
repository change, not a workflow. It would:
- add a new catalogue entry with its own key, the rationale for promotion, and provenance citing
  `peak_field_observation`, plus any external sources later added to support or refine it;
- be seeded by the tool;
- keep the original supplemental row and its field-use provenance (engagement, author, rationale,
  usage), so the promotion stays traceable to field use.

No promotion workflow is built in Phase 216.

## Observation trace and basis (Part D evidence boundary)

An observation may now carry two more fields:
- **`question_id`**: the question that prompted it. It must exist and be asked in the observation's
  engagement (global, or that engagement's own supplemental question). Optional, and correctable.
- **`basis`**: what it rests on. One of:
  - `testimony`: the client said it;
  - `observed`: the consultant saw it;
  - `document`: the consultant reviewed a report, export or screen;
  - `measured`: the consultant counted or calculated it;
  - `inferred`: the consultant concluded it.

  A basis is a description of footing. It never promotes discovery material into governed
  evidence. The database enforces the vocabulary (`ck_discovery_observations_basis`).

**In the assessment and Final Report** (Markdown, web, DOCX, and the stored web/DOCX renditions):
- Each discovery finding shows its basis, or "Basis not recorded".
- Its trace names the prompting question. If the observation's interview answered that question,
  the trace also names the answer and uses the answer's prompt snapshot. The answer text is never
  copied into the finding.
- The discovery limitations state how many findings rest on testimony or inference only, and how
  many have no recorded basis.

Evidence-backed findings, recommendation eligibility (Phases 117/118) and C4/C5 are unchanged.
Discovery findings still have no review status, reliability, claim scope or eligibility field.

**Artifact content.** The `DiscoveryFinding` and `LowHangingFruitCandidate` dataclasses gain
`basis`, so a version created after the deploy includes it in its canonical content (format name
unchanged, `peak.final_report.canonical_json.v1`).
- Stored versions are never rebuilt; only a version created moments earlier is.
- Released packages are read as stored bytes, so existing versions and packages are untouched.
- Re-preparing an unchanged engagement after the deploy creates a new version, because the content
  now carries `basis`.

## Schema and migration impact

Migration `021_discovery_observation_trace_basis` (down-revision
`020_internal_test_engagement_retirement`) adds nullable columns only. It changes no existing
column, adds no data and leaves the artifact tables alone.

| Table | New columns |
|---|---|
| `discovery_observations` | `question_id` (governed), indexed; `basis` with `ck_discovery_observations_basis` |
| `discovery_questions` | `engagement_id` (governed), indexed; `added_by_consultant_id` (governed); `rationale`; `domain`; `finding_classes` (JSON) |

**Governed columns.** Three new governed string columns are added. The production collation
verifier pin stays at `020` until 021 is really applied (Phase 58 rule).

**Allowlist:**
- the observation create and update actions gain `question_id` and `basis`;
- question create gains `engagement_id` and `added_by_consultant_id`, which are create-only;
- question create and update gain `rationale`, `domain` and `finding_classes`.

No delete action is added, and no forbidden column is touched.

**Phase 204 harness exemption.** The Phase 204 identity-link check now names one explicit
exemption: an observation's `question_id`. It is a "prompted by" annotation, editable so a wrong
link can be corrected, and it is kept within the observation's engagement.

## UI

The changes are minimal:
- **Question pool:** badges for *Peak Method*, *Supplemental · one engagement* and *Global ·
  Admin*, plus usage counts on supplemental questions. "Add global question" is shown to an Admin
  only.
- **Editing a canonical or global question:** read-only for a Consultant, with a pointer to adding
  a supplemental question. The global form, opened without an engagement, tells a Consultant to add
  the question from an engagement instead.
- **Supplemental questions:** "Add supplemental question" on the engagement's Discovery section and
  on an in-progress interview. The form takes a required rationale and optional domain and
  finding classes, then returns to where it was opened.
- **Observation form:** optional *Basis*, optional *Prompted by question* (that engagement's
  questions, grouped by section), and finding-class suggestions for the category.
- **Observation cards, the assessment and the Final Report** show the basis and the prompting
  question.

## Production rollout

**Read-only check before any change** (2026-10-16). It used the read-only login inside a
`READ ONLY` transaction, SELECT/SHOW only:

| Property | Production |
|---|---|
| Alembic head | `020_internal_test_engagement_retirement` |
| `discovery_questions` | 29 rows, all with a Phase 204 `seed_key`, all active; no consultant-added question |
| Edits | **none**: every row matches the Phase 204 seed (prompt, category, type, choices, order, active, branch), and `updated_at` equals `created_at` on all 29 |
| `discovery_sessions` / `discovery_answers` | 0 / 0 (0 answers with text) |
| `discovery_observations` | 1, the Phase 215 synthetic internal-test observation |
| Runtime grants | SELECT and INSERT on the schema; table-level UPDATE on six tables (`clients`, `engagements`, `discovery_questions`, `discovery_sessions`, `discovery_answers`, `discovery_observations`), from Phases 203 and 205; no change needed |

No historical answer exists to preserve yet. The rollout still only deactivates, so the 29 rows
and their wording are kept.

### Schema: 020 → 021 (2026-10-17)

**Preflight (read-only):**
- `main` = `origin/main` = `3025614`, clean;
- production head `020_internal_test_engagement_retirement`;
- 29 `discovery_questions`, all active and unedited; 0 answers;
- runtime grants as listed above.

**Migration.** `alembic upgrade 021_discovery_observation_trace_basis` ran with the production
migration credential in a subshell (`PEAK_ALEMBIC_TARGET=production`,
`PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, `PEAK_PRODUCTION_SCHEMA_CONFIRM=defaultdb`). It applied
`020 → 021` only.

**Read-only check afterwards:**

| Property | After |
|---|---|
| Alembic head | `021_discovery_observation_trace_basis`, single row |
| New columns | all seven present and nullable: `discovery_observations.question_id` (`utf8mb4_bin`), `.basis`; `discovery_questions.engagement_id`, `.added_by_consultant_id` (both `utf8mb4_bin`), `.rationale`, `.domain`, `.finding_classes` (JSON) |
| Constraint | `ck_discovery_observations_basis` present |
| Indexes | `ix_discovery_observations_question_id`, `ix_discovery_questions_engagement_id` |
| Row counts | unchanged in every table (`discovery_questions` 29, `discovery_answers` 0, `discovery_observations` 1, `engagements` 2, artifact tables 1/1/1/2/2/1/1) |
| Content | unchanged: a fingerprint over every row of the artifact tables, `engagements`, `clients` and the discovery record tables (excluding only the two new, null observation columns) equals the preflight value |
| Question pool | unchanged: 29 Phase 204 rows, active, matching the seed |
| Runtime grants | unchanged, identical `SHOW GRANTS` |

**Verifier.**
- `EXPECTED_ALEMBIC_HEAD` moved to `021_discovery_observation_trace_basis`, after the migration was
  applied (Phase 58 rule).
- The run against production returned `verified_safe_no_remediation_required`, exit 0:
  - head matches;
  - 31 base tables;
  - **345/345** governed columns deterministic (the three new governed ids add three);
  - 11/11 idempotency boundaries safe;
  - no schema mutation, data write or migration by the tool.
- Phase 43, 58 and 216 harnesses: PASS.

**Pending at this record:** the Render API deploy (Auto-Deploy gate first), the Vercel web deploy,
the instrument seed and its read-only verification.

### Remaining sequence (each step separately approved)
1. Migrate production 020 → 021 with the migration credential and target guard.
2. Run the read-only verifier, then move `EXPECTED_ALEMBIC_HEAD` to 021.
3. Deploy the API (Render, Auto-Deploy gate first), then the web app (Vercel). The models select
   the new columns, so the migration must come first.
4. Seed the instrument: `tools/init_discovery_questions.py --production`, dry run first, then
   `--execute`. It inserts the 46 instrument questions after the existing pool, then deactivates
   the 29 superseded ones. Nothing is deleted or re-worded, and every answer keeps its prompt
   snapshot.
5. Verify read-only: 75 question rows, 46 active canonical, 29 inactive superseded, answers
   unchanged.

The seed tool uses the runtime credential, which already holds INSERT and UPDATE on
`discovery_questions` (questions were always editable in the app). No grant change is needed.

### Verifier credential reduced to read-only (2026-10-18)

`peak_prod_verify_ro` is now **read-only by database grant**: `SELECT ON defaultdb.*` only, plus
the implicit `USAGE ON *.*`. Before this, it held the platform's default for new service users:
global privileges with `GRANT OPTION`, identical to `peak_prod_migrate`. That was the accepted
risk carried since Phase 203. The earlier "read-only login" checks in this record were read-only
by `READ ONLY` transaction and tool code, not by grant. The reduction was made during Phase 216
closure.

**What the verifier needs.** `tools/production_mysql_collation_verify.py` is the only tool that
connects with this credential. Every statement it runs is a hard-coded SELECT: `VERSION()`,
`DATABASE()`, a collation probe on literals, `INFORMATION_SCHEMA` reads for the schema,
`alembic_version`, and the optional `COUNT(*) … GROUP BY` collision probe. `SELECT ON defaultdb.*`
covers all of them.

**Rehearsal.** The exact sequence ran first on a disposable, loopback-only MySQL 8.4.8 (the
production version) with `partial_revokes=ON`. The test verifier and a separate grantor carried the
production grant set, partial revokes included, and the schema was migrated to 021. Afterwards:
- `SHOW GRANTS` was exactly USAGE and SELECT on the schema, with no residual restrictions;
- the unmodified verifier returned `verified_safe_no_remediation_required` (345/345, 11/11);
- INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, CREATE USER and GRANT were refused;
- the grantor's own grants were unchanged.

The instance was torn down.

**Production.** The operator ran these two statements as `peak_prod_migrate` on `defaultdb`, and
nothing else:

```sql
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'peak_prod_verify_ro'@'%';
GRANT SELECT ON `defaultdb`.* TO 'peak_prod_verify_ro'@'%';
```

The revoke comes first and the grant is issued by a different account: under partial revokes,
granting to yourself after revoking leaves an account with no privileges (Phase 85).

**Afterwards, read-only, as the verifier itself:**
- `CURRENT_USER()` is `peak_prod_verify_ro@%`, and `SHOW GRANTS` is exactly USAGE on `*.*` and
  SELECT on `defaultdb.*`;
- the verifier returned `verified_safe_no_remediation_required`, exit 0, with output identical to
  the run just before: head 021, 31 base tables, 345/345 governed columns, 11/11 boundaries;
- all 31 tables have unchanged row counts and content fingerprints, and the question pool is
  unchanged.

No user, password, env file, application code, runtime grant or migration-user grant changed.

**Consequence for later checks.** The verifier can no longer read `mysql.*`, so it cannot list
other users' grants. Check the runtime and migration grants through each credential's own
`SHOW GRANTS FOR CURRENT_USER()` (the Phase 50 gate does this for the runtime user).

**Follow-ups (not done here):**
1. Review whether `peak_prod_migrate` can be reduced below the platform default while keeping the
   capability migrations need.
2. Review the Phase 50 runtime gate. Its `FORBIDDEN_GRANTS` lists UPDATE, which predates the six
   table-level UPDATE grants approved in Phases 203 and 205, so the gate may now encode obsolete
   assumptions.

## Validation

- `tests/validate_phase216_discovery_instrument.py`, in `make validate`. It covers:
  - the catalogue (counts, the 12 fields, branches, evidence choices, domain coverage, exhaustive
    session sizes, determinism);
  - provenance;
  - the governing rule;
  - migration 021 up and down, with the constraint;
  - the rollout on a Phase 204 pool with answers, including an Admin-edited legacy question;
  - canonical Admin control;
  - supplemental provenance and scoping;
  - observation trace and basis through the assessment, Markdown, web and DOCX;
  - "answers never become findings";
  - governance.
- `tests/validate_phase204_discovery_workflow.py`, updated to the instrument keys. Canonical edits
  are made as an Admin, and the identity-link check has the exemption described above.
- Web: `npm run lint` and `npm run build` are clean.
- `make PYTHON=.venv/bin/python validate`: **PASS**, exit 0, 0 failures, in a committed tree (a
  temporary detached worktree, since removed). As in Phases 212–215, the older harnesses' "the
  allowlist was not modified" diffs against HEAD clear only on commit.
- **MySQL 8.2.0, disposable and loopback-only:**
  - `tests/validate_phase214_mysql_artifact_concurrency.py` passed 41 checks, migrating to head
    through 021.
  - A direct 021 check passed 13/13: all seven columns are nullable; the governed ids are
    `utf8mb4_bin`; `finding_classes` is JSON; the named `ck_discovery_observations_basis` exists
    and refuses an unknown basis (MySQL 3819); the downgrade removes the columns and the CHECK;
    re-upgrade works.
  - The lab schema and user were dropped afterwards.
- **Policy change.** `tools/managed_mysql_parity_check.py` now allows `create_check_constraint`
  and `drop_constraint`: schema-only operations its simulator already modelled. `drop_constraint`
  is also listed as destructive, so it is permitted only in a downgrade. The Phase 41 harness
  passes.

## Out of scope

Not built in this phase:
- training, lessons, examinations or certification;
- a rules engine or a custom-question framework;
- a proposal workflow;
- AgentNet or capsule publication;
- a recommendation-engine change;
- model-selected next questions.
