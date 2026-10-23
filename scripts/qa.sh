#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m compileall -q leskdoo tests run.py
python -m ruff check --select E9,F63,F7,F82 leskdoo tests run.py
python scripts/check_yaml.py
python -m pytest -q --cov=leskdoo --cov-report=term-missing
