PYTHON ?= python3.11
PYTHONPATH := runtime

.PHONY: format lint typecheck test test-contract test-integration check run run-mcp

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

check: lint typecheck test

run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mobile_agent.api.server

run-mcp:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mobile_agent.mcp
