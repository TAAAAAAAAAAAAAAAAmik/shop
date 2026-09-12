.PHONY: install run seed test lint fmt

install:
	python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

run:
	.venv/bin/python -m kinetix

seed:
	.venv/bin/python -m kinetix.db.seed

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check kinetix tests

fmt:
	.venv/bin/ruff check --fix kinetix tests
