#!/usr/bin/env bash
# E2E runner for the sccfm-cli integration tests.
#
# Runs pytest against the installed `sccfm-cli` binary, exercising it
# against a real SCCFM tenant.  Generates JUnit XML for Jenkins test
# result reporting.
#
# Prerequisites:
#   - Run scripts/setup_tokens.py first (creates vault.yml and .vault_pass)
#   - Virtualenv active (or poetry will manage one)
#
# Usage:
#    ./sccfm_cli/e2e/run_e2e.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EXAMPLES_DIR="${REPO_ROOT}/sccfm-ansible/examples"
VAULT_PASS="${VAULT_PASS:-${EXAMPLES_DIR}/.vault_pass}"
VAULT_FILE="${VAULT_FILE:-${EXAMPLES_DIR}/group_vars/all/vault.yml}"
VARS_FILE="${VARS_FILE:-${EXAMPLES_DIR}/group_vars/all/vars.yml}"
RESULTS_DIR="${RESULTS_DIR:-${REPO_ROOT}/results}"

if ! command -v poetry >/dev/null 2>&1; then
  echo "ERROR: poetry is required to run the integration tests." >&2
  exit 1
fi

# ── Preflight checks ──────────────────────────────────────────────
if [[ ! -f "${VAULT_PASS}" ]]; then
  echo "ERROR: ${VAULT_PASS} not found. Run scripts/setup_tokens.py first." >&2
  exit 1
fi

if [[ ! -f "${VAULT_FILE}" ]]; then
  echo "ERROR: ${VAULT_FILE} not found. Run scripts/setup_tokens.py first." >&2
  exit 1
fi

if [[ ! -f "${VARS_FILE}" ]]; then
  echo "ERROR: ${VARS_FILE} not found." >&2
  exit 1
fi

# ── Install the package so sccfm-cli is on PATH ───────────────────
echo "Installing sccfm package (with dev extras)..."
poetry install --no-interaction --with dev

# ── Run integration tests ─────────────────────────────────────────
echo "Running sccfm-cli e2e tests..."
mkdir -p "${RESULTS_DIR}"

export SCCFM_E2E_VAULT_FILE="${VAULT_FILE}"
export SCCFM_E2E_VAULT_PASS="${VAULT_PASS}"
export SCCFM_E2E_VARS_FILE="${VARS_FILE}"

poetry run python -m pytest "${SCRIPT_DIR}" \
  -v \
  --tb=short \
  --junitxml="${RESULTS_DIR}/ci-cli-tests.xml"
