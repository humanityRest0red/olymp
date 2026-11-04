PYTHON ?= python

.PHONY: run fmt lint static clean

run:
	$(PYTHON) src/main.py

fmt:
	pylint src/

static:
	mypy src/

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache
