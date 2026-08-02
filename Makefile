PYTHON ?= python3.11
PYTHONPATH := runtime
CARGO ?= $(shell command -v cargo 2>/dev/null || echo $(HOME)/.cargo/bin/cargo)

.PHONY: format lint typecheck test test-contract test-integration check check-desktop contracts check-contracts run run-mcp

format:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/quality.py format

lint:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/quality.py lint

typecheck:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/quality.py typecheck

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s runtime/tests -p 'test_*.py' -v

test-contract:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest runtime.tests.test_device_contract -v

test-integration:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest runtime.tests.test_runtime_service -v

contracts:
	$(PYTHON) scripts/generate_ts_contracts.py

check-contracts:
	$(PYTHON) scripts/generate_ts_contracts.py --check

check: lint typecheck test check-contracts

check-desktop:
	cd apps/desktop && npm run lint && npm run typecheck
	cd apps/desktop/src-tauri && $(CARGO) fmt --check && $(CARGO) clippy --all-targets -- -D warnings && $(CARGO) test

run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mobile_agent.api.server

run-mcp:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mobile_agent.mcp
