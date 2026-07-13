#!/usr/bin/env bash
# E2E runner for the sccfm-cli integration tests.
#
# Runs pytest against the installed `sccfm-cli` binary, exercising it
# against a real SCCFM tenant.  Generates JUnit XML for Jenkins test
# result reporting.
#
# When ASA_HOST and VASA_PASSWORD are set, this script onboards a
# CLI-dedicated vASA (named `ci-e2e-cli-asa-<host>`) before pytest and
# removes it afterward — see playbooks/{onboard,remove}_vasa.yml.  The
# CLI suite has its own device so it doesn't fight the Ansible suite,
# whose mutations would otherwise leave the shared device NOT_SYNCED
# and block our ASA CLI script pushes.
#
# Prerequisites:
#   - Run cisco_sccfm_scripts/setup_tokens.py first (creates vault.yml and .vault_pass)
#   - Virtualenv active (or poetry will manage one)
#   - For onboarding: ASA_HOST + VASA_PASSWORD env vars
#
# Usage:
#    ./cisco_sccfm_cli/e2e/run_e2e.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COLLECTION_DIR="${REPO_ROOT}/sccfm-ansible"
EXAMPLES_DIR="${COLLECTION_DIR}/examples"
PLAYBOOKS_DIR="${SCRIPT_DIR}/playbooks"
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
  echo "ERROR: ${VAULT_PASS} not found. Run cisco_sccfm_scripts/setup_tokens.py first." >&2
  exit 1
fi

if [[ ! -f "${VAULT_FILE}" ]]; then
  echo "ERROR: ${VAULT_FILE} not found. Run cisco_sccfm_scripts/setup_tokens.py first." >&2
  exit 1
fi

if [[ ! -f "${VARS_FILE}" ]]; then
  echo "ERROR: ${VARS_FILE} not found." >&2
  exit 1
fi

# ── Install the package so sccfm-cli is on PATH ───────────────────
echo "Installing sccfm package (with dev extras)..."
poetry install --no-interaction --with dev

# ── Onboard a CLI-dedicated vASA (opt-in via ASA_HOST) ────────────
ONBOARDED_VASA=0

remove_cli_vasa() {
  if [[ "${ONBOARDED_VASA}" -eq 1 ]]; then
    echo "Removing CLI-dedicated vASA..."
    poetry run ansible-playbook \
      "${PLAYBOOKS_DIR}/remove_vasa.yml" \
      --vault-password-file "${VAULT_PASS}" \
      -e "@${VARS_FILE}" \
      -e "@${VAULT_FILE}" \
      || echo "WARNING: vASA removal failed; continuing." >&2
  fi
}
trap remove_cli_vasa EXIT

if [[ -n "${ASA_HOST:-}" && -n "${VASA_PASSWORD:-}" ]]; then
  echo "Installing cisco.sccfm collection (needed by onboard playbook)..."
  poetry run ansible-galaxy collection install "${COLLECTION_DIR}" --force

  # Mark first so the EXIT trap cleans up even if the playbook
  # fails after registering the device.  remove_vasa.yml is a no-op
  # when nothing matches `ci-e2e-cli-asa-*`.
  ONBOARDED_VASA=1
  echo "Onboarding CLI-dedicated vASA (ci-e2e-cli-asa-${ASA_HOST//[^a-zA-Z0-9]/-})..."
  poetry run ansible-playbook \
    "${PLAYBOOKS_DIR}/onboard_vasa.yml" \
    --vault-password-file "${VAULT_PASS}" \
    -e "@${VARS_FILE}" \
    -e "@${VAULT_FILE}"
else
  echo "ASA_HOST/VASA_PASSWORD not set; skipping vASA onboarding." \
       "Tests will use whatever devices already match ci-e2e-cli-asa-*."
fi

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
