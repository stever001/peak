# Convenience commands for Peak's internal AI operating system.
# This machine uses `python3` (there is no bare `python`), so all targets call
# python3 explicitly. Override with `make PYTHON=/path/to/python ...` if needed.

PYTHON ?= python3

.PHONY: help validate install-dev

help: ## Show available targets
	@echo "Targets:"
	@echo "  make install-dev   Install dev dependencies ($(PYTHON) -m pip install -r requirements-dev.txt)"
	@echo "  make validate      Run the Phase 1 validation harness ($(PYTHON) tests/validate_phase1.py)"

install-dev: ## Install development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

validate: ## Run the Phase 1 schema/example validation harness
	$(PYTHON) tests/validate_phase1.py
