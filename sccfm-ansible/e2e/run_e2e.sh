#!/usr/bin/env bash
# E2E runner for SCCFM Ansible collection integration tests.
#
# Runs pytest against playbooks targeting a real SCCFM tenant.
# Generates JUnit XML for Jenkins test result reporting.
#
# Prerequisites:
#   - Configure the selected profile with sccfm-cli configure
#   - Create vault.yml and .vault_pass for Ansible-specific device secrets
#   - Virtualenv active (source cisco_sccfm_scripts/activate.sh)
#
# Usage:
#    ./sccfm-ansible/e2e/run_e2e.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COLLECTION_DIR="${REPO_ROOT}/sccfm-ansible"
EXAMPLES_DIR="${COLLECTION_DIR}/examples"
VAULT_PASS="${VAULT_PASS:-${EXAMPLES_DIR}/.vault_pass}"
RESULTS_DIR="${RESULTS_DIR:-${REPO_ROOT}/results}"

if ! command -v poetry >/dev/null 2>&1; then
  echo "ERROR: poetry is required to run the integration tests." >&2
  exit 1
fi

# ── Preflight checks ──────────────────────────────────────────────
if [[ ! -f "${VAULT_PASS}" ]]; then
  echo "ERROR: ${VAULT_PASS} not found. Create it for Ansible device secrets first." >&2
  exit 1
fi

if [[ ! -f "${EXAMPLES_DIR}/group_vars/all/vault.yml" ]]; then
  echo "ERROR: group_vars/all/vault.yml not found. Create it for device secrets first." >&2
  exit 1
fi

# ── Install collection ────────────────────────────────────────────
echo "Installing cisco.sccfm collection..."
poetry run ansible-galaxy collection install "${COLLECTION_DIR}" --force

# ── Run integration tests ─────────────────────────────────────────
echo "Running network object lifecycle e2e tests..."
mkdir -p "${RESULTS_DIR}"
poetry run python -m pytest "${SCRIPT_DIR}" \
  -v \
  --tb=short \
  --junitxml="${RESULTS_DIR}/ci-ansible-tests.xml"
