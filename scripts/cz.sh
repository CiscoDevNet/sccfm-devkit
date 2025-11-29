#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [[ ! -x "${VENV_DIR}/bin/cz" ]]; then
  echo "Commitizen not found in ${VENV_DIR}. Run scripts/setup_environment.sh first." >&2
  exit 1
fi

if [[ -x "${VENV_DIR}/bin/pre-commit" ]]; then
  echo "Running pre-commit hooks before commit..."
  "${VENV_DIR}/bin/pre-commit" run --all-files
  echo "Pre-commit hooks completed."
fi

exec "${VENV_DIR}/bin/cz" "$@"
