# The whole developer interface. If a step isn't a target here, it isn't a step.

PY := .venv/bin/python

# Where the library lives. Defaults to the sample entries in this repo so that a
# clean clone runs with no data repo present. For real use, point this at your
# private data repo:  make run TL_DATA_DIR=../library_of_tabel_data
TL_DATA_DIR ?= samples
export TL_DATA_DIR

.PHONY: setup install_precommit_hooks lint format run test check hash clean

setup: install_precommit_hooks  ## create .venv, install from uv.lock, install git hooks
	@:

.venv/bin/pre-commit:
	uv venv
	uv sync --frozen

install_precommit_hooks: .venv/bin/pre-commit  ## install the git pre-commit hooks
	.venv/bin/pre-commit install

lint: | $(PY)         ## ruff check + format check, without writing anything
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

format: | $(PY)       ## apply ruff fixes and formatting
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .

run: | $(PY)          ## serve locally with reload
	$(PY) -m flask --app wsgi run --debug

test: | $(PY)         ## run the test suite
	$(PY) -m pytest

check: lint test      ## everything verifiable offline (extended in PR 4 with
                      ## vendored-asset hash verification)

hash: | $(PY)         ## prompt for a password, print its hash for instance/config.py
	$(PY) scripts/make_password_hash.py

clean:                ## remove the venv and caches
	rm -rf .venv .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

$(PY):
	@echo "No .venv found -- run 'make setup' first." >&2
	@exit 1
