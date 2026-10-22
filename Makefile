.PHONY: check check-full hooks data run paper

# Fast gate, run by the pre-commit hook: lint, then every test not marked slow. That
# includes tests/leakage and the writing lint in tests/test_writing.py.
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest tests -m "not slow" -q

check-full:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest tests -q

hooks:
	printf '#!/bin/sh\n# Installed by make hooks. Every commit must pass the fast gate.\nexec make check\n' > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

# DAYS is train, val, test or one YYYY-MM-DD. Test days refuse until prereg-v1 is public.
data:
	@test -n "$(DAYS)" || (echo "usage: make data DAYS=train|val|test|YYYY-MM-DD" && exit 2)
	uv run python -m toxic_flow.data.download $(DAYS)
	uv run python -m toxic_flow.data.convert $(DAYS)

run:
	@echo "make run is a stub until M2 (engine/run.py)." && exit 1

paper:
	@echo "make paper is a stub until M6." && exit 1
