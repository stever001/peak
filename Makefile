# Convenience commands for Peak's internal AI operating system.
# This machine uses `python3` (there is no bare `python`), so all targets call
# python3 explicitly. Override with `make PYTHON=/path/to/python ...` if needed.

PYTHON ?= python3

.PHONY: help validate validate-phase1 validate-phase2 validate-phase3 validate-phase4 validate-phase5 validate-phase6 validate-phase7 validate-phase8 validate-phase9 validate-phase10 validate-phase11 validate-phase12 validate-phase13 validate-phase14 validate-phase15 validate-phase16 validate-phase17 validate-phase18 validate-phase19 validate-phase20 validate-phase21 validate-phase22 validate-phase23 validate-phase24 validate-phase25 validate-phase26 validate-phase27 validate-phase28 validate-phase29 validate-phase30 validate-phase31 validate-phase32 validate-phase33 validate-phase34 validate-phase35 validate-phase36 validate-phase37 validate-phase38 validate-phase39 validate-phase40 validate-phase41 validate-phase42 validate-phase43 validate-phase44 validate-phase47 validate-phase49 validate-phase50 validate-phase51 validate-phase53 validate-phase54 validate-phase55 validate-phase56 validate-phase57 validate-phase58 validate-phase59 validate-phase60 validate-phase61 validate-phase62 validate-phase63 validate-phase64 validate-phase65 validate-phase66 validate-phase67 validate-phase68 validate-phase69 validate-phase70 runtime-connectivity-gate writer-enablement-decision-gate db-check mysql-parity-static mysql-parity-staging mysql-collation-audit production-mysql-collation-verify db-check-managed-test managed-mysql-smoke managed-mysql-migration-check packet-summary install-dev

help: ## Show available targets
	@echo "Targets:"
	@echo "  make install-dev        Install dev dependencies ($(PYTHON) -m pip install -r requirements-dev.txt)"
	@echo "  make validate           Run all validation harnesses (Phase 1 through Phase 51)"
	@echo "  make validate-phase1    Run only the Phase 1 object harness"
	@echo "  make validate-phase2    Run only the Phase 2 EngagementPacket harness"
	@echo "  make validate-phase3    Run only the Phase 3 prompt-contract inventory check"
	@echo "  make validate-phase4    Run only the Phase 4 example-output inventory check"
	@echo "  make validate-phase5    Run only the Phase 5 packet-runner smoke check"
	@echo "  make validate-phase6    Run only the Phase 6 consultant-guide doc check"
	@echo "  make validate-phase7    Run only the Phase 7 repo-hygiene / data-artifact guard"
	@echo "  make validate-phase8    Run only the Phase 8 controlled-data architecture doc check"
	@echo "  make validate-phase9    Run only the Phase 9 governance-state contract check"
	@echo "  make validate-phase10   Run only the Phase 10 database-plan doc check"
	@echo "  make validate-phase11   Run only the Phase 11 database-scaffold check"
	@echo "  make validate-phase12   Run only the Phase 12 AgentNet MCP boundary check"
	@echo "  make validate-phase13   Run only the Phase 13 agent-execution-harness check"
	@echo "  make validate-phase14   Run only the Phase 14 evidence-normalization-worker check"
	@echo "  make validate-phase15   Run only the Phase 15 QA / review-gate check"
	@echo "  make validate-phase16   Run only the Phase 16 review-persistence-boundary check"
	@echo "  make validate-phase17   Run only the Phase 17 controlled-DB-writer-boundary check"
	@echo "  make validate-phase18   Run only the Phase 18 evidence-persistence-mapping check"
	@echo "  make validate-phase19   Run only the Phase 19 agent-run-persistence-mapping check"
	@echo "  make validate-phase20   Run only the Phase 20 controlled-DB agent-run-writer check"
	@echo "  make validate-phase21   Run only the Phase 21 controlled-DB evidence-writer check"
	@echo "  make validate-phase22   Run only the Phase 22 controlled-DB review-writer check"
	@echo "  make validate-phase23   Run only the Phase 23 engagement-packet-ingestion-boundary check"
	@echo "  make validate-phase24   Run only the Phase 24 controlled-DB source-ingestion-writer check"
	@echo "  make validate-phase25   Run only the Phase 25 controlled-packet-processing-orchestrator check"
	@echo "  make validate-phase26   Run only the Phase 26 agent-task-queue / execution-readiness check"
	@echo "  make validate-phase27   Run only the Phase 27 controlled-DB agent-task-queue-writer check"
	@echo "  make validate-phase28   Run only the Phase 28 packet -> task-queue orchestration integration check"
	@echo "  make validate-phase29   Run only the Phase 29 packet-derived review orchestration boundary check"
	@echo "  make validate-phase30   Run only the Phase 30 controlled-DB review-bundle-writer check"
	@echo "  make validate-phase31   Run only the Phase 31 packet -> review-bundle orchestration integration check"
	@echo "  make validate-phase32   Run only the Phase 32 internal reviewer decision boundary check"
	@echo "  make validate-phase33   Run only the Phase 33 controlled-DB internal-reviewer-decision-writer check"
	@echo "  make validate-phase34   Run only the Phase 34 intake-note-writer + managed-MySQL-rubric checks"
	@echo "  make validate-phase35   Run only the Phase 35 governed managed-record workflow integration check"
	@echo "  make validate-phase36   Run only the Phase 36 internal assessment report planning boundary check"
	@echo "  make validate-phase37   Run only the Phase 37 controlled-DB internal-assessment-report-draft-writer check"
	@echo "  make validate-phase38   Run only the Phase 38 controlled-DB internal-report-review-packet-writer check"
	@echo "  make validate-phase39   Run only the Phase 39 controlled-DB packet-decision-writer check"
	@echo "  make validate-phase40   Run only the Phase 40 internal report review workflow integration check"
	@echo "  make validate-phase41   Run only the Phase 41 managed MySQL production-parity check"
	@echo "  make validate-phase42   Run only the Phase 42 governed MySQL collation policy check"
	@echo "  make validate-phase43   Run only the Phase 43 production MySQL collation verification check"
	@echo "  make validate-phase44   Run only the Phase 44 governed identifier collation migration check"
	@echo "  make validate-phase47   Run only the Phase 47 Alembic version-table hardening check"
	@echo "  make validate-phase49   Run only the Phase 49 runtime database URL separation check"
	@echo "  make validate-phase50   Run only the Phase 50 runtime connectivity gate check"
	@echo "  make validate-phase51   Run only the Phase 51 writer enablement decision gate check"
	@echo "  make validate-phase53   Run only the Phase 53 authorized engagement/intake path check"
	@echo "  make validate-phase54   Run only the Phase 54 engagement authorization anchor writer check"
	@echo "  make validate-phase55   Run only the Phase 55 internal test engagement classification check"
	@echo "  make validate-phase56   Run only the Phase 56 internal test engagement support check"
	@echo "  make validate-phase57   Run only the Phase 57 internal test read-isolation check"
	@echo "  make validate-phase58   Run only the Phase 58 production migration 014 verification check"
	@echo "  make validate-phase59   Run only the Phase 59 first internal test engagement anchor check"
	@echo "  make validate-phase60   Run only the Phase 60 intake taxonomy + internal test intake note check"
	@echo "  make validate-phase61   Run only the Phase 61 internal test intake review decision check"
	@echo "  make db-check           Alias for the Phase 11 database-scaffold check"
	@echo "  make db-check-managed-test        Managed MySQL test-env rubric check (skips safely with no DSN)"
	@echo "  make managed-mysql-smoke          Managed MySQL test-env smoke runbook (skips safely with no DSN)"
	@echo "  make managed-mysql-migration-check Managed MySQL test-env migration runbook (skips safely with no DSN)"
	@echo "  make packet-summary PACKET=/path/to/packet.json   Summarize a real packet (read-only; no LLM/API)"

install-dev: ## Install development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

validate: validate-phase1 validate-phase2 validate-phase3 validate-phase4 validate-phase5 validate-phase6 validate-phase7 validate-phase8 validate-phase9 validate-phase10 validate-phase11 validate-phase12 validate-phase13 validate-phase14 validate-phase15 validate-phase16 validate-phase17 validate-phase18 validate-phase19 validate-phase20 validate-phase21 validate-phase22 validate-phase23 validate-phase24 validate-phase25 validate-phase26 validate-phase27 validate-phase28 validate-phase29 validate-phase30 validate-phase31 validate-phase32 validate-phase33 validate-phase34 validate-phase35 validate-phase36 validate-phase37 validate-phase38 validate-phase39 validate-phase40 validate-phase41 validate-phase42 validate-phase43 validate-phase44 validate-phase47 validate-phase49 validate-phase50 validate-phase51 validate-phase53 validate-phase54 validate-phase55 validate-phase56 validate-phase57 validate-phase58 validate-phase59 validate-phase60 validate-phase61 validate-phase62 validate-phase63 validate-phase64 validate-phase65 validate-phase66 validate-phase67 validate-phase68 validate-phase69 validate-phase70 ## Run all validation harnesses

validate-phase1: ## Run the Phase 1 schema/example validation harness
	$(PYTHON) tests/validate_phase1.py

validate-phase2: ## Run the Phase 2 EngagementPacket validation harness
	$(PYTHON) tests/validate_phase2.py

validate-phase3: ## Run the Phase 3 prompt-contract inventory check (stdlib-only)
	$(PYTHON) tests/validate_phase3_prompts.py

validate-phase4: ## Run the Phase 4 example-output inventory check (stdlib-only)
	$(PYTHON) tests/validate_phase4_outputs.py

validate-phase5: ## Run the Phase 5 packet-runner smoke check (stdlib-only)
	$(PYTHON) tests/validate_phase5_runner.py

validate-phase6: ## Run the Phase 6 consultant-guide doc check (stdlib-only)
	$(PYTHON) tests/validate_phase6_docs.py

validate-phase7: ## Run the Phase 7 repo-hygiene / data-artifact guard (stdlib-only)
	$(PYTHON) tests/validate_phase7_policy.py

validate-phase8: ## Run the Phase 8 controlled-data architecture doc check (stdlib-only)
	$(PYTHON) tests/validate_phase8_architecture.py

validate-phase9: ## Run the Phase 9 governance-state contract check
	$(PYTHON) tests/validate_phase9_governance.py

validate-phase10: ## Run the Phase 10 database-plan doc check (stdlib-only)
	$(PYTHON) tests/validate_phase10_database_plan.py

validate-phase11: ## Run the Phase 11 database-scaffold check (stdlib-only)
	$(PYTHON) tests/validate_phase11_db_scaffold.py

validate-phase12: ## Run the Phase 12 AgentNet MCP boundary check (stdlib-only)
	$(PYTHON) tests/validate_phase12_agentnet_mcp_boundary.py

validate-phase13: ## Run the Phase 13 agent-execution-harness check (stdlib-only)
	$(PYTHON) tests/validate_phase13_agent_harness.py

validate-phase14: ## Run the Phase 14 evidence-normalization-worker check (stdlib-only)
	$(PYTHON) tests/validate_phase14_evidence_worker.py

validate-phase15: ## Run the Phase 15 QA / review-gate check (stdlib-only)
	$(PYTHON) tests/validate_phase15_review_gate.py

validate-phase16: ## Run the Phase 16 review-persistence-boundary check (stdlib-only)
	$(PYTHON) tests/validate_phase16_review_persistence.py

validate-phase17: ## Run the Phase 17 controlled-DB-writer-boundary check (stdlib-only)
	$(PYTHON) tests/validate_phase17_controlled_db_writer.py

validate-phase18: ## Run the Phase 18 evidence-persistence-mapping check (stdlib-only)
	$(PYTHON) tests/validate_phase18_evidence_persistence.py

validate-phase19: ## Run the Phase 19 agent-run-persistence-mapping check (stdlib-only)
	$(PYTHON) tests/validate_phase19_agent_run_persistence.py

validate-phase20: ## Run the Phase 20 controlled-DB agent-run-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase20_agent_run_writer.py

validate-phase21: ## Run the Phase 21 controlled-DB evidence-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase21_evidence_writer.py

validate-phase22: ## Run the Phase 22 controlled-DB review-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase22_review_writer.py

validate-phase23: ## Run the Phase 23 engagement-packet-ingestion-boundary check (stdlib-only)
	$(PYTHON) tests/validate_phase23_packet_ingestion.py

validate-phase24: ## Run the Phase 24 controlled-DB source-ingestion-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase24_source_ingestion_writer.py

validate-phase25: ## Run the Phase 25 controlled-packet-processing-orchestrator check (structural+plan-only always; DB-backed via .venv)
	$(PYTHON) tests/validate_phase25_packet_processing_orchestrator.py

validate-phase26: ## Run the Phase 26 agent-task-queue / execution-readiness check (stdlib-only; DB-free)
	$(PYTHON) tests/validate_phase26_agent_task_queue_readiness.py

validate-phase27: ## Run the Phase 27 controlled-DB agent-task-queue-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase27_agent_task_queue_writer.py

validate-phase28: ## Run the Phase 28 packet -> task-queue orchestration integration check (structural+plan-only always; DB-backed via .venv)
	$(PYTHON) tests/validate_phase28_packet_task_queue_integration.py

validate-phase29: ## Run the Phase 29 packet-derived review orchestration boundary check (stdlib-only; DB-free)
	$(PYTHON) tests/validate_phase29_review_orchestration_boundary.py

validate-phase30: ## Run the Phase 30 controlled-DB review-bundle-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase30_review_bundle_writer.py

validate-phase31: ## Run the Phase 31 packet -> review-bundle orchestration integration check (structural+plan-only always; DB-backed via .venv)
	$(PYTHON) tests/validate_phase31_packet_review_bundle_integration.py

validate-phase32: ## Run the Phase 32 internal reviewer decision boundary check (stdlib-only; DB-free)
	$(PYTHON) tests/validate_phase32_internal_reviewer_decision_boundary.py

validate-phase33: ## Run the Phase 33 controlled-DB internal-reviewer-decision-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase33_internal_reviewer_decision_writer.py

validate-phase34: ## Run the Phase 34 intake-note-writer + managed-MySQL-rubric checks (DB-backed via .venv)
	$(PYTHON) tests/validate_phase34_intake_note_writer.py
	$(PYTHON) tests/validate_phase34_managed_mysql_rubric.py

validate-phase35: ## Run the Phase 35 governed managed-record workflow integration check (structural+plan-only always; DB-backed via .venv)
	$(PYTHON) tests/validate_phase35_managed_record_workflow.py

validate-phase36: ## Run the Phase 36 internal assessment report planning boundary check (stdlib-only; DB-free)
	$(PYTHON) tests/validate_phase36_internal_assessment_report_planning.py

validate-phase37: ## Run the Phase 37 controlled-DB internal-assessment-report-draft-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase37_internal_assessment_report_draft_writer.py

validate-phase38: ## Run the Phase 38 controlled-DB internal-report-review-packet-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase38_internal_report_review_packet_writer.py

validate-phase39: ## Run the Phase 39 controlled-DB internal-report-review-packet-decision-writer check (DB-backed via .venv)
	$(PYTHON) tests/validate_phase39_internal_report_review_packet_decision_writer.py

validate-phase40: ## Run the Phase 40 end-to-end internal report review workflow integration check (structural always; DB-backed via .venv)
	$(PYTHON) tests/validate_phase40_internal_report_review_workflow.py

validate-phase41: ## Run the Phase 41 managed MySQL production-parity check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase41_managed_mysql_production_parity.py

validate-phase42: ## Run the Phase 42 governed MySQL collation policy check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase42_governed_mysql_collation_policy.py

validate-phase43: ## Run the Phase 43 production MySQL collation verification check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase43_production_mysql_collation_verification.py

validate-phase44: ## Run the Phase 44 governed identifier collation migration check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase44_governed_identifier_collation_migration.py

# Phase 47 hardens the Alembic version table in source so a fresh MySQL/MariaDB bootstrap can
# record this repo's long revision ids. Fully offline: no credentials, network, .env, or DSN.
validate-phase47: ## Run the Phase 47 Alembic version-table hardening check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase47_alembic_version_table_hardening.py

# Phase 49 separates the runtime DB URL variable from the migration one. Fully offline: it
# reads no credentials, opens no connection, and scrubs the three role variables from the env.
validate-phase49: ## Run the Phase 49 runtime database URL separation check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase49_runtime_database_url_separation.py

# Phase 50 checks the runtime connectivity gate itself. Fully offline: it contacts no
# database and scrubs all three role variables from every child process it starts.
validate-phase50: ## Run the Phase 50 runtime connectivity gate check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase50_controlled_runtime_connectivity_gate.py

# Phase 51 checks the writer-enablement decision gate. Fully offline: the gate it checks has
# no database code path at all.
validate-phase51: ## Run the Phase 51 writer enablement decision gate check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase51_writer_enablement_decision_gate.py

# Phase 53 checks the authorized engagement/intake write path *plan*. Fully offline: it
# contacts no database, reads no credential, and invokes no controlled writer.
validate-phase53: ## Run the Phase 53 authorized engagement/intake path check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase53_authorized_engagement_intake_path.py

# Phase 54 checks the engagement authorization anchor writer. Offline: it exercises the
# writer only against throwaway temporary SQLite databases and contacts no production DB.
validate-phase54: ## Run the Phase 54 engagement authorization anchor writer check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase54_engagement_authorization_anchor_writer.py

# Phase 55 checks the internal test engagement classification decision. Fully offline: it
# contacts no database, reads no credential, and invokes no controlled writer.
validate-phase55: ## Run the Phase 55 internal test engagement classification check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase55_internal_test_engagement_classification.py

# Phase 56 checks engagement classification support. Offline: the DB-backed layer runs only
# against throwaway temporary SQLite databases and contacts no production database.
validate-phase56: ## Run the Phase 56 internal test engagement support check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase56_internal_test_engagement_support.py

# Phase 57 checks the read-side isolation primitive. Offline: the helper opens no connection
# and the query layer runs only against throwaway temporary SQLite.
validate-phase57: ## Run the Phase 57 internal test read-isolation check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase57_internal_test_read_isolation.py

validate-phase58: ## Run the Phase 58 production migration 014 verification check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase58_production_014_verification.py

validate-phase59: ## Run the Phase 59 first internal test engagement anchor check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase59_first_internal_test_engagement_anchor.py

validate-phase60: ## Run the Phase 60 intake taxonomy + internal test intake note check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase60_first_internal_test_intake_note.py

validate-phase61: ## Run the Phase 61 internal test intake review decision check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase61_internal_test_intake_review_decision.py

validate-phase62: ## Run the Phase 62 internal test source/evidence request plan check (offline; planning-only, no DB)
	$(PYTHON) tests/validate_phase62_internal_test_source_evidence_request_plan.py

validate-phase63: ## Run the Phase 63 first internal test source ingestion check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase63_first_internal_test_source_ingestion.py

validate-phase64: ## Run the Phase 64 R1-R7 source artifact collection plan check (offline; planning-only, no DB)
	$(PYTHON) tests/validate_phase64_internal_test_r1_r7_source_artifact_collection_plan.py

validate-phase65: ## Run the Phase 65 R2/R1 internal test source ingestion check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase65_r1_r2_source_ingestion_records.py

validate-phase66: ## Run the Phase 66 R2 source ingestion review decision check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase66_internal_test_source_ingestion_review_decision.py

validate-phase67: ## Run the Phase 67 first internal test evidence reference check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase67_first_internal_test_evidence_reference.py

validate-phase68: ## Run the Phase 68 R2 evidence reference review decision check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase68_r2_evidence_reference_review_decision.py

validate-phase69: ## Run the Phase 69 R9 location/bin naming model source ingestion check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase69_r9_location_bin_model_source_ingestion.py

validate-phase70: ## Run the Phase 70 R9 source ingestion review decision check (offline; no credentials/network)
	$(PYTHON) tests/validate_phase70_r9_source_ingestion_review_decision.py

db-check: ## Validate the DB scaffold (alias for validate-phase11)
	$(PYTHON) tests/validate_phase11_db_scaffold.py

# --- Managed MySQL parity (Phase 41) ---
# `mysql-parity-static` is fully offline: no credentials, no network, no .env, no DSN, no database.
# It is safe inside `make validate`. `mysql-parity-staging` can reach a database and is therefore
# opt-in only and deliberately NOT part of `make validate`; it skips cleanly with no configuration.
mysql-parity-static: ## Offline MySQL parity checks (identifiers/migrations/charset; no credentials)
	$(PYTHON) tools/managed_mysql_parity_check.py --mode static

mysql-parity-staging: ## Opt-in disposable-staging MySQL parity gate (skips safely with no DSN)
	$(PYTHON) tools/managed_mysql_parity_check.py --mode staging

# Offline governed-collation audit (Phase 42). No credentials, network, .env, DSN, or DB driver.
# Reports NEEDS_REMEDIATION as a WARNING and still exits 0: the unpinned-collation finding is a
# known, documented open item, not a build failure. See docs/GOVERNED_MYSQL_COLLATION_POLICY.md.
mysql-collation-audit: ## Offline governed-collation audit (classification + remediation status)
	$(PYTHON) tools/governed_mysql_collation_audit.py

# READ-ONLY production collation verification (Phase 43). This target CAN connect to the real
# deployed production database, so it is deliberately NOT part of `make validate`. It fails closed:
# with no configuration it skips (exit 0) without importing a driver or reading .env, and with a
# connection setting but no PEAK_PRODUCTION_DB_READONLY_CONFIRM it refuses (exit 2) without
# connecting. It issues only hard-coded SELECT/SHOW metadata queries, performs no schema mutation,
# data write, migration, or cleanup, and never prints a DSN or a production row value.
# See docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md.
production-mysql-collation-verify: ## READ-ONLY production collation verification (opt-in; skips safely)
	$(PYTHON) tools/production_mysql_collation_verify.py

# READ-ONLY runtime connectivity gate (Phase 50). This target CAN connect to the real deployed
# database using the RUNTIME credential, so it is deliberately NOT part of `make validate`.
# It fails closed: with no PEAK_RUNTIME_DATABASE_URL it refuses (exit 2) without connecting,
# and it never reads PEAK_DATABASE_URL or PEAK_PRODUCTION_DB_URL. It issues only SELECT 1 and
# SHOW GRANTS, writes nothing, reads no application table, and runs no writer.
runtime-connectivity-gate: ## READ-ONLY runtime connectivity gate (opt-in; refuses safely)
	$(PYTHON) tools/production_runtime_connectivity_gate.py

# OFFLINE writer-enablement decision gate (Phase 51). It contacts no database, reads no
# environment variable, issues no statement, and invokes no writer — it records the current
# decision and refuses (exit 3) any request to authorize a write. Kept opt-in so the
# operational gates stay in one place; its static harness runs inside `make validate`.
writer-enablement-decision-gate: ## OFFLINE writer enablement decision gate (opt-in; records the no-write decision)
	$(PYTHON) tools/production_writer_enablement_decision_gate.py

# --- Managed MySQL production-parity targets (opt-in; credential-free; skip safely with no DSN) ---
# These are NOT part of `make validate`: they require an out-of-band managed test/staging DSN and
# never print DSNs, never write to production, and never run destructive cleanup. See
# docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md and docs/PRODUCTION_PARITY_DB_VALIDATION.md.
db-check-managed-test: ## Managed MySQL test-env rubric check (skips with guidance if no DSN)
	$(PYTHON) tools/managed_mysql_check.py --env test --mode db-check

managed-mysql-smoke: ## Managed MySQL test-env smoke runbook (skips with guidance if no DSN)
	$(PYTHON) tools/managed_mysql_check.py --env test --mode smoke

managed-mysql-migration-check: ## Managed MySQL test-env migration runbook (skips with guidance if no DSN)
	$(PYTHON) tools/managed_mysql_check.py --env test --mode migration-check

packet-summary: ## Summarize a real packet: make packet-summary PACKET=/path/to/packet.json
	@if [ -z "$(PACKET)" ]; then \
		echo "Provide PACKET=/path/to/engagement-packet.json from a controlled engagement workspace."; \
		exit 2; \
	fi
	$(PYTHON) tools/packet_runner.py --packet "$(PACKET)"
