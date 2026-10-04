.PHONY: test lint typecheck check assurance verify

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else command -v python3; fi)
RUFF ?= $(shell if [ -x .venv/bin/ruff ]; then echo .venv/bin/ruff; else command -v ruff; fi)
MYPY ?= $(shell if [ -x .venv/bin/mypy ]; then echo .venv/bin/mypy; else command -v mypy; fi)

test:
	PYTHONPATH=backend/src $(PYTHON) -m pytest -q backend/tests

lint:
	@if [ -n "$(RUFF)" ]; then $(RUFF) check backend/src backend/tests scripts; else echo "ruff is not installed; install backend[dev]"; exit 1; fi

typecheck:
	@if [ -n "$(MYPY)" ]; then MYPYPATH=backend/src $(MYPY) --ignore-missing-imports --follow-imports=skip backend/src scripts; else echo "mypy is not installed; install backend[dev]"; exit 1; fi

# Assurance records chain: the Phase 4 manifest pins the Phase 3 manifest, so the
# Phase 3 record must be rebuilt first. Both fail closed if offline replay diverges.
assurance:
	PYTHONPATH=backend/src $(PYTHON) scripts/build_phase3_assurance.py
	PYTHONPATH=backend/src $(PYTHON) scripts/build_phase4_assurance.py

check: test lint typecheck

# Single source of truth for pass/fail. Each stage's exit code is captured and
# the target fails if any stage failed, so success cannot be misread from
# filtered console output. Grepping test output for "passed" hid real failures
# twice in this project's history, including a scientific-integrity regression.
verify:
	@fail=0; \
	for stage in test lint typecheck; do \
		printf '\n=== %s ===\n' "$$stage"; \
		$(MAKE) --no-print-directory $$stage || { echo "FAILED: $$stage"; fail=1; }; \
	done; \
	printf '\n=== assurance (offline rebuild) ===\n'; \
	$(MAKE) --no-print-directory assurance >/dev/null || { echo "FAILED: assurance"; fail=1; }; \
	if [ $$fail -ne 0 ]; then echo "\nVERIFY: FAILED"; exit 1; fi; \
	echo "\nVERIFY: ALL STAGES PASSED"
