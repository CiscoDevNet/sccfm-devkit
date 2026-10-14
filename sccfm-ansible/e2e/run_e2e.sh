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

# ── Debug hold (opt-in via HOLD_VASA_MINUTES) ─────────────────────
# Jenkins onboards the vASA before this script and always deletes it, with
# its CloudFormation stack, after the job.  When the marker file exists,
# skip the tests and keep the job, and so the device, alive for that many
# minutes.  Abort the job to tear down early.  Keep the hold short enough
# for setup + hold + teardown to fit in the job's 1h timeout.
HOLD_FILE="${SCRIPT_DIR}/HOLD_VASA_MINUTES"
if [[ -f "${HOLD_FILE}" ]]; then
  hold_minutes="$(tr -dc '0-9' < "${HOLD_FILE}")"
  hold_minutes="${hold_minutes:-0}"
  host="${ASA_HOST:-unknown}"
  until_utc="$(date -u -d "+${hold_minutes} min" +%H:%M 2>/dev/null || echo '?')"
  echo "HOLD: skipping tests. vASA ${host} is onboarded as" \
       "ci-e2e-asa-${host//[^a-zA-Z0-9]/-} and stays up for ${hold_minutes} min" \
       "(until ${until_utc} UTC)."
  sleep "$(( hold_minutes * 60 ))"
  exit 0
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
