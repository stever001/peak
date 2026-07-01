# Convenience commands for Peak's internal AI operating system.
# This machine uses `python3` (there is no bare `python`), so all targets call
# python3 explicitly. Override with `make PYTHON=/path/to/python ...` if needed.

PYTHON ?= python3

.PHONY: help validate validate-phase1 validate-phase2 install-dev

help: ## Show available targets
	@echo "Targets:"
	@echo "  make install-dev        Install dev dependencies ($(PYTHON) -m pip install -r requirements-dev.txt)"
	@echo "  make validate           Run all validation harnesses (Phase 1 + Phase 2)"
	@echo "  make validate-phase1    Run only the Phase 1 object harness"
	@echo "  make validate-phase2    Run only the Phase 2 EngagementPacket harness"

install-dev: ## Install development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

validate: validate-phase1 validate-phase2 ## Run all validation harnesses

validate-phase1: ## Run the Phase 1 schema/example validation harness
	$(PYTHON) tests/validate_phase1.py

validate-phase2: ## Run the Phase 2 EngagementPacket validation harness
	$(PYTHON) tests/validate_phase2.py
