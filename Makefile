# Convenience commands for Peak's internal AI operating system.
# This machine uses `python3` (there is no bare `python`), so all targets call
# python3 explicitly. Override with `make PYTHON=/path/to/python ...` if needed.

PYTHON ?= python3

.PHONY: help validate validate-phase1 validate-phase2 validate-phase3 validate-phase4 validate-phase5 validate-phase6 validate-phase7 validate-phase8 validate-phase9 validate-phase10 validate-phase11 validate-phase12 validate-phase13 validate-phase14 validate-phase15 validate-phase16 validate-phase17 validate-phase18 validate-phase19 validate-phase20 validate-phase21 validate-phase22 validate-phase23 validate-phase24 validate-phase25 validate-phase26 validate-phase27 validate-phase28 db-check packet-summary install-dev

help: ## Show available targets
	@echo "Targets:"
	@echo "  make install-dev        Install dev dependencies ($(PYTHON) -m pip install -r requirements-dev.txt)"
	@echo "  make validate           Run all validation harnesses (Phase 1 through Phase 28)"
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
	@echo "  make db-check           Alias for the Phase 11 database-scaffold check"
	@echo "  make packet-summary PACKET=/path/to/packet.json   Summarize a real packet (read-only; no LLM/API)"

install-dev: ## Install development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

validate: validate-phase1 validate-phase2 validate-phase3 validate-phase4 validate-phase5 validate-phase6 validate-phase7 validate-phase8 validate-phase9 validate-phase10 validate-phase11 validate-phase12 validate-phase13 validate-phase14 validate-phase15 validate-phase16 validate-phase17 validate-phase18 validate-phase19 validate-phase20 validate-phase21 validate-phase22 validate-phase23 validate-phase24 validate-phase25 validate-phase26 validate-phase27 validate-phase28 ## Run all validation harnesses

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

db-check: ## Validate the DB scaffold (alias for validate-phase11)
	$(PYTHON) tests/validate_phase11_db_scaffold.py

packet-summary: ## Summarize a real packet: make packet-summary PACKET=/path/to/packet.json
	@if [ -z "$(PACKET)" ]; then \
		echo "Provide PACKET=/path/to/engagement-packet.json from a controlled engagement workspace."; \
		exit 2; \
	fi
	$(PYTHON) tools/packet_runner.py --packet "$(PACKET)"
