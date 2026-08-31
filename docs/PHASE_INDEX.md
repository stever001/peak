# Peak Phase Index

A reader-facing map of Peak's delivery phases. This is a **navigation layer**, not a
replacement for the detailed records it points at.

## Where phase information lives

| Source | What it holds |
|---|---|
| [`README.md`](../README.md) | Project overview, plus narrative sections for **Phases 11–44** |
| [`docs/IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | The evolving implementation roadmap and the long-form running record for **Phases 11–85**, plus a Phase 88 pointer |
| `docs/PHASE##_*.md` | Dedicated per-phase records, present from **Phase 45 onward** (Phases 52, 86 and 87 excepted) |
| Commit history | The primary record for **Phases 1–10** and for code-only maintenance phases |
| This index | The single entry point covering **Phases 1–92** and the convention for future phases |

Two navigation traps are worth knowing before reading the plan:

- `IMPLEMENTATION_PLAN.md` uses **two numbering schemes**. Its top-level `##` headings are a
  *strategic* Phase 0–5 sequence. The delivery phases 11–85 are bold sub-entries nested inside
  `## Phase 5 — Hardening & scale (internal)`. Phase 47's entry, for example, sits under a
  heading that reads "Phase 5".
- Because those entries are bold text rather than headings, they generate **no table-of-contents
  anchors**, so they cannot be deep-linked. Search the phase name instead.

## Phase documentation convention

- Every phase gets **one durable purpose entry in this index**.
- Major implementation or operational phases should **also** get a dedicated
  `docs/PHASE##_*.md` record.
- Code-only validation-maintenance phases **may be indexed without a dedicated phase doc** when
  the commit message and the validation harnesses are self-explanatory.
- This index carries **no** secrets, hosts, provider names, DSNs, local paths, environment
  values, row bodies, fixtures, sample data, or client data. Phase purposes are described in
  governance terms only.

## Completed phase ledger

Phases 1–10 established the scaffolding, contracts, and policies. Their durable record is the
commit history plus the policy documents each produced; they have no dedicated `PHASE##_*.md`
file.

| Phase | Purpose | Primary record | Status / notes |
|---|---|---|---|
| 0 | Initial repository structure for the internal AI operating system | commit `c3a89e0` | Scaffold; predates phase numbering |
| 1 | Assessment schemas and validation | commit `ce0e031`; [`schemas/`](../schemas/) | Not separately documented as a phase doc |
| 2 | Engagement packet validation | commit `51e8ba5` | Not separately documented as a phase doc |
| 3 | Internal prompt contracts | commit `20ab017`; [`prompts/`](../prompts/) | Not separately documented as a phase doc |
| 4 | Sample run artifacts | commit `72e7424` | Not separately documented as a phase doc |
| 5 | Packet runner | commit `a590f71` | Not separately documented as a phase doc |
| 6 | Consultant workflow guide | [`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md) | Doc-backed |
| 7 | Data handling policy | [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md) | Doc-backed |
| 8 | Controlled data architecture | [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md) | Doc-backed |
| 9 | Governance state contracts | [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) | Doc-backed |
| 10 | Controlled database plan | [`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md) | Doc-backed; planning only, no code |

Phases 11–44 are the narrative core of the README. Each has a `###` section there, a bold entry
in the implementation plan, and in most cases one or more topic documents.

| Phase | Purpose | Primary record | Status / notes |
|---|---|---|---|
| 11 | Minimal MySQL database scaffold — models, enums, migration 001 | README §Scaffold; [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md) | Source assets only |
| 12 | AgentNet MCP governance boundary | README; [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md) | Wrapper scaffold; no live connector |
| 13 | Agent execution harness | README; [`AGENT_EXECUTION_HARNESS.md`](AGENT_EXECUTION_HARNESS.md) | Scaffold only |
| 14 | Evidence normalization worker | README; [`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md) | First production-shaped worker |
| 15 | QA / review gate | README; [`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md) | Scaffold only |
| 16 | Review persistence boundary | README; [`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md) | DB-aware, not DB-writing |
| 17 | Controlled DB writer boundary | README; [`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md) | DB-aware, not DB-writing |
| 18 | Evidence persistence mapping | README; [`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md) | DB-aware, not DB-writing |
| 19 | Agent run persistence mapping | README; [`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md) | DB-aware, not DB-writing |
| 20 | Agent run controlled writer | README; [`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md) | First DB-backed writer |
| 21 | Evidence controlled writer | README; [`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md) | Second writer |
| 22 | Review record controlled writer | README; [`REVIEW_CONTROLLED_WRITER.md`](REVIEW_CONTROLLED_WRITER.md) | Third writer |
| 23 | Engagement packet ingestion boundary | README; [`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md) | Boundary, not a writer |
| 24 | Source ingestion record controlled writer | README; [`SOURCE_INGESTION_CONTROLLED_WRITER.md`](SOURCE_INGESTION_CONTROLLED_WRITER.md) | Fourth writer |
| 25 | Controlled packet processing orchestrator | README; [`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md) | Sequencing layer; plan-only default |
| 26 | Agent task queue / execution readiness boundary | README; [`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md) | DB-free; no execution |
| 27 | Agent task queue controlled writer | README; [`AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](AGENT_TASK_QUEUE_CONTROLLED_WRITER.md) | Fifth writer |
| 28 | Packet → task queue orchestration integration | README; [`PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md) | Integration, not a new writer |
| 29 | Packet-derived review orchestration boundary | README; [`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md) | DB-free; no approval |
| 30 | Review bundle controlled writer | README; [`REVIEW_BUNDLE_CONTROLLED_WRITER.md`](REVIEW_BUNDLE_CONTROLLED_WRITER.md) | Sixth writer |
| 31 | Packet → review bundle orchestration integration | README; [`PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md) | Integration, not a new writer |
| 32 | Internal reviewer decision boundary | README; [`INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](INTERNAL_REVIEWER_DECISION_BOUNDARY.md) | DB-free; no approval |
| 33 | Internal reviewer decision controlled writer | README; [`INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md) | Seventh writer |
| 34 | Intake note controlled writer + managed MySQL rubric | README; [`INTAKE_NOTE_CONTROLLED_WRITER.md`](INTAKE_NOTE_CONTROLLED_WRITER.md), [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) | Eighth writer; managed MySQL declared the operational store |
| 35 | Governed managed record workflow integration | README; [`MANAGED_RECORD_WORKFLOW_INTEGRATION.md`](MANAGED_RECORD_WORKFLOW_INTEGRATION.md) | Six-stage workflow over existing writers |
| 36 | Internal assessment report assembly planning boundary | README; [`INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`](INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md) | DB-free report planning |
| 37 | Internal assessment report draft controlled writer | README; [`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md) | Ninth writer |
| 38 | Internal report review packet controlled writer | README; [`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md) | Tenth writer |
| 39 | Internal report review packet decision controlled writer | README; [`INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md) | Eleventh writer |
| 40 | End-to-end internal report review workflow integration | README; [`INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md`](INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md) | Read-only consolidation |
| 41 | Managed MySQL production-parity validation | README; [`MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md`](MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md) | Offline parity checks + opt-in staging gate |
| 42 | Governed MySQL collation policy | README; [`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md) | Policy, audit, remediation plan |
| 43 | Production MySQL collation verification | README; [`PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](PRODUCTION_MYSQL_COLLATION_VERIFICATION.md) | Read-only verification + go/no-go |
| 44 | Governed identifier collation migration | README; migration 013 | Last phase with a README narrative section |

From Phase 45 onward each phase has a dedicated record. **README narrative coverage stops at
Phase 44**; this table is the entry point for everything after it.

| Phase | Purpose | Primary record | Status / notes |
|---|---|---|---|
| 45 | Production collation verification | [`PHASE45_PRODUCTION_COLLATION_VERIFICATION.md`](PHASE45_PRODUCTION_COLLATION_VERIFICATION.md) | Operational, read-only |
| 46 | Production schema bootstrap recovery | [`PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md`](PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md) | Operational; approved recovery |
| 47 | Alembic version-table hardening | [`PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md`](PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md) | Source hardening; harness later fixed in commit `0301977` |
| 48 | Production runtime readiness gate | [`PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md`](PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md) | Read-only gate |
| 49 | Runtime database URL separation | [`PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md`](PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md) | Source wiring only |
| 50 | Controlled runtime connectivity gate | [`PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md`](PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md) | Read-only gate + reusable tool |
| 51 | Writer enablement decision gate | [`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md) | Governance gate; no writer enabled |
| 52 | Runtime gate driver-unavailable diagnostic | **No dedicated phase doc.** Recorded as "Phase 52A" in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md); commit `6736fe0` | Diagnostic polish; distinguishes a local driver problem from a production failure |
| 53 | Authorized engagement / intake write path planning | [`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md) | Plan only |
| 54 | Controlled engagement authorization anchor writer | [`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md) | Code path only; twelfth writer |
| 55 | Internal test engagement classification and creation decision | [`PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md`](PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md) | Plan and classification only |
| 56 | Internal test engagement schema and writer classification support | [`PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md`](PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md) | Migration 014; no records created |
| 57 | Read-side isolation for internal test engagements | [`PHASE57_INTERNAL_TEST_READ_ISOLATION.md`](PHASE57_INTERNAL_TEST_READ_ISOLATION.md) | Enforcement primitive only |
| 58 | Migration 014 applied to production, and verified | [`PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md`](PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md) | Schema change only |
| 59 | The first durable internal test engagement anchor | [`PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md`](PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md) | First application record |
| 60 | Intake taxonomy V0 and the first internal test intake note | [`PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md`](PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md) | One application record |
| 61 | The internal test intake review decision | [`PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md`](PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md) | One application record |
| 62 | The internal test source/evidence request plan | [`PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md`](PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md) | Planning only |
| 63 | The first internal test source ingestion record | [`PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md) | One application record |
| 64 | The internal test R1–R7 source artifact collection plan | [`PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md`](PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md) | Planning only |
| 65 | The R2 and R1 internal test source ingestion records | [`PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md) | Two application records |
| 66 | The internal test source ingestion review decision (R2) | [`PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md) | One application record |
| 67 | The first internal test evidence reference (R2 source availability) | [`PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md`](PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md) | One application record |
| 68 | The R2 evidence reference review decision | [`PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md`](PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md) | One application record |
| 69 | The R9 location/bin naming model source ingestion | [`PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md`](PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md) | One application record |
| 70 | The R9 source ingestion review decision | [`PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md) | One application record |
| 71 | The R1/R9 evidence-readiness plan | [`PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md`](PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md) | Planning; harness later fixed in commit `fb1ffdb` |
| 72 | The R10 location model answer set source ingestion | [`PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md`](PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md) | One application record |
| 73 | R10 review and the location-readiness evidence | [`PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md`](PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md) | Review + evidence |
| 74 | Location-readiness evidence review and the minimal internal assessment outline | [`PHASE74_LOCATION_READINESS_INTERNAL_ASSESSMENT.md`](PHASE74_LOCATION_READINESS_INTERNAL_ASSESSMENT.md) | Assessment outline |
| 75 | Location assessment review support: preferred path declined | [`PHASE75_LOCATION_ASSESSMENT_REVIEW_SUPPORT.md`](PHASE75_LOCATION_ASSESSMENT_REVIEW_SUPPORT.md) | Review decision recorded |
| 76 | The R8 authority review and the R5 WMS scope clarification | [`PHASE76_R8_R5_BLOCKER_CLARIFICATION.md`](PHASE76_R8_R5_BLOCKER_CLARIFICATION.md) | Blocker clarification |
| 77 | Parallel prep for R5 WMS scope clarification review and R8 prerequisite resolution | [`PHASE77_PARALLEL_PREP_R8_R5.md`](PHASE77_PARALLEL_PREP_R8_R5.md) | Preparation |
| 78 | The R5 WMS scope clarification review and the R4 scope correction | [`PHASE78_R5_WMS_SCOPE_REVIEW.md`](PHASE78_R5_WMS_SCOPE_REVIEW.md) | Review + correction |
| 79 | The R8 measurement feasibility source ingestion | [`PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md`](PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md) | Source ingestion |
| 80 | The R8 measurement feasibility review and the scenario-specific closure | [`PHASE80_R8_MEASUREMENT_FEASIBILITY_REVIEW_CLOSURE.md`](PHASE80_R8_MEASUREMENT_FEASIBILITY_REVIEW_CLOSURE.md) | Review closure |
| 81 | The production-parity lab MySQL plan | [`PHASE81_PRODUCTION_PARITY_LAB_MYSQL_PLAN.md`](PHASE81_PRODUCTION_PARITY_LAB_MYSQL_PLAN.md) | Plan only |
| 82 | Lab MySQL provisioning readiness | [`PHASE82_LAB_MYSQL_PROVISIONING_READINESS.md`](PHASE82_LAB_MYSQL_PROVISIONING_READINESS.md) | Readiness only |
| 83 | Provisioning and verifying the lab managed MySQL environment | [`PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md`](PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md) | Lab only; production untouched |
| 84 | Fixing the Alembic lab/production target guard | [`PHASE84_ALEMBIC_TARGET_GUARD_FIX.md`](PHASE84_ALEMBIC_TARGET_GUARD_FIX.md) | Source-only guard fix; commit `3892693` does not carry the phase number |
| 85 | Creating and seeding the lab scenario source-system schema | [`PHASE85_PEAK_LAB_SCENARIO_SEEDING.md`](PHASE85_PEAK_LAB_SCENARIO_SEEDING.md) | Lab only |
| 86 | Swept expiring baseline-window validation checks and converted them to durable git ancestry checks | **No dedicated phase doc** (code-only maintenance); commit `ddade90`; the 22 harnesses under [`tests/`](../tests/) | Converted 22 checks across two families; Phase 47's earlier fix (`0301977`) set the pattern |
| 87 | Added this phase index and reader navigation | **No dedicated phase doc** (docs-only); commit `fc943f5`; this file | Closed the post-Phase-44 discoverability gap in `README.md` |
| 88 | Read-only measurement pass over the seeded lab scenario, establishing evidence-readiness coverage for R1/R2/R5/R8/R9/R10 | [`PHASE88_LAB_SCENARIO_MEASUREMENT.md`](PHASE88_LAB_SCENARIO_MEASUREMENT.md) | Lab-only, `SELECT` only; no Peak record created, no writer invoked, no production access |
| 89 | Added a lab-only writer-enablement decision path, scoped to `peak_lab` and three create-only writer targets | [`PHASE89_LAB_WRITER_ENABLEMENT_GATE.md`](PHASE89_LAB_WRITER_ENABLEMENT_GATE.md) | Source/test/docs only; production enablement unchanged and still false; no writer invoked |
| 90 | Bootstrap-only lab enablement of the engagement anchor writer, and the first Peak writer invocation against `peak_lab` | [`PHASE90_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP.md`](PHASE90_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP.md) | **One durable lab `engagements` row created**; production enablement unchanged and still false |
| 91 | Drift, test-sprawl, and parallel agentic workflow review | [`PHASE91_DRIFT_TEST_SPRAWL_PARALLEL_WORKFLOW_REVIEW.md`](PHASE91_DRIFT_TEST_SPRAWL_PARALLEL_WORKFLOW_REVIEW.md) | Docs-only review; no database, cloud, environment, migration, writer, record, or scenario activity; no harness added; recommendations only, plus one `README.md` status-banner accuracy correction |
| 92 | First controlled lab source-ingestion write, derived from the Phase 88 measurement | [`PHASE92_FIRST_LAB_SOURCE_INGESTION_WRITE.md`](PHASE92_FIRST_LAB_SOURCE_INGESTION_WRITE.md) | **One durable lab `source_ingestion_records` row created**; Phase 89 gate used as-is; no new harness; production enablement unchanged and still false |

### Phases without a dedicated phase doc

- **Phases 0–10** — recorded by commit message and, from Phase 6 on, by the policy document each
  produced.
- **Phase 52** — the implementation plan records it as "Phase 52A"; there is no `PHASE52_*.md`.
- **Phase 86** — code-only validation maintenance, indexed here under the convention above.
- **Phase 87** — docs-only navigation work; this file is its record.

## Current baseline

As of Phase 92, whose baseline is the committed Phase 91 commit `98629da` — *Document Phase 91
drift and workflow review*:

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` |
| Migrations | 14 |
| Controlled Peak tables | 18 |
| Controlled writers | 12 |
| Migration 015 | Does not exist |
| Production write enablement | None standing |
| Lab write enablement | Anchor bootstrap enabled (Phase 90); source-ingestion exercised once (Phase 92); **lab evidence and review writes remain unapproved** |
| `peak_lab` controlled tables | 18, head `014_engagement_classification`, **2 application rows** (the Phase 90 `engagements` anchor and the Phase 92 `source_ingestion_records` row) |
| `peak_lab_scenario` | seeded, 120 rows, content hash re-verified in Phase 88 |

Phases 87–92 changed no migration, table, or writer, so the first six values are unchanged since
Phase 86. **Phase 90 changed the `peak_lab` row count**: it is no longer empty, and "0 application
rows" is no longer a valid safety assertion against the lab. **Any later phase that changes the schema, writer count, or baseline commit must
refresh this block.**

A note on how this block is written. Its first version was authored *during* Phase 88 and named
`fc943f5` — the commit the phase started from, not the commit it produced — which read as though
the block knew a SHA that did not yet exist. It is now written as "the baseline this phase starts
from", a fact that is true when written. **A phase must never name its own future commit SHA
here**; it records the commit it began at, and the next phase moves it forward.

## Future phase convention

- **Phase 87 and later must update this index as part of completion.** A phase is not finished
  until its purpose entry exists here.
- Future `docs/PHASE##_*.md` records should link back to this index where useful.
- **`README.md` stays high-level.** It is a project overview, not the phase ledger; new phases
  should not add narrative sections to it. The README's Phase 11–44 sections are existing history
  and are left as they are.
