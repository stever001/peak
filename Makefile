# Convenience commands for Peak's internal AI operating system.
# This machine uses `python3` (there is no bare `python`), so all targets call
# python3 explicitly. Override with `make PYTHON=/path/to/python ...` if needed.

PYTHON ?= python3

.PHONY: help validate validate-phase1 validate-phase2 validate-phase3 validate-phase4 validate-phase5 validate-phase6 validate-phase7 packet-summary install-dev

help: ## Show available targets
	@echo "Targets:"
	@echo "  make install-dev        Install dev dependencies ($(PYTHON) -m pip install -r requirements-dev.txt)"
	@echo "  make validate           Run all validation harnesses (Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 + Phase 6 + Phase 7)"
	@echo "  make validate-phase1    Run only the Phase 1 object harness"
	@echo "  make validate-phase2    Run only the Phase 2 EngagementPacket harness"
	@echo "  make validate-phase3    Run only the Phase 3 prompt-contract inventory check"
	@echo "  make validate-phase4    Run only the Phase 4 example-output inventory check"
	@echo "  make validate-phase5    Run only the Phase 5 packet-runner smoke check"
	@echo "  make validate-phase6    Run only the Phase 6 consultant-guide doc check"
	@echo "  make validate-phase7    Run only the Phase 7 repo-hygiene / data-artifact guard"
	@echo "  make packet-summary PACKET=/path/to/packet.json   Summarize a real packet (read-only; no LLM/API)"

install-dev: ## Install development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

validate: validate-phase1 validate-phase2 validate-phase3 validate-phase4 validate-phase5 validate-phase6 validate-phase7 ## Run all validation harnesses

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

packet-summary: ## Summarize a real packet: make packet-summary PACKET=/path/to/packet.json
	@if [ -z "$(PACKET)" ]; then \
		echo "Provide PACKET=/path/to/engagement-packet.json from a controlled engagement workspace."; \
		exit 2; \
	fi
	$(PYTHON) tools/packet_runner.py --packet "$(PACKET)"
