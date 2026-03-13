#!/usr/bin/env bash
# Fetch a fresh CI token and run the e2e integration test suite.
#
# Automates the full flow:
#   1. Fetch a fresh API token from the CI auth endpoint
#   2. Run setup-tokens to write .env, vault, vars, CLI config
#   3. Verify the token works by decrypting the vault and printing metadata
#   4. Run the e2e test suite
#
# Required environment variables (or edit defaults below):
#   SCCFM_CI_USERNAME   (default: sccfm-ansible-e2e@lockhart.io)
#   SCCFM_CI_PASSWORD   (default: 1234567890)
#   SCCFM_CI_CLIENT_ID  (default: my-trusted-client)
#   SCCFM_VAULT_PASS    (default: 1234567890)
#
# Usage:
#   bash sccfm-ansible/e2e/fetch_token_and_run.sh          # full run
#   bash sccfm-ansible/e2e/fetch_token_and_run.sh --token-only  # fetch + setup only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EXAMPLES_DIR="${REPO_ROOT}/sccfm-ansible/examples"

# ── Configurable defaults ─────────────────────────────────────────
CI_USERNAME="${SCCFM_CI_USERNAME:-sccfm-ansible-e2e@lockhart.io}"
CI_PASSWORD="${SCCFM_CI_PASSWORD:-1234567890}"
CI_CLIENT_ID="${SCCFM_CI_CLIENT_ID:-my-trusted-client}"
VAULT_PASSWORD="${SCCFM_VAULT_PASS:-1234567890}"
AUTH_URL="https://ci.manage.security.cisco.com/anubis/oauth/token"
REGION="ci"

# ── Step 1: Fetch token ──────────────────────────────────────────
echo "=== Fetching fresh API token from ${AUTH_URL} ==="
TOKEN_RESPONSE=$(curl -s -f -XPOST \
  -d "username=${CI_USERNAME}&password=${CI_PASSWORD}&client_id=${CI_CLIENT_ID}&grant_type=password" \
  "${AUTH_URL}")

API_TOKEN=$(echo "${TOKEN_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [[ -z "${API_TOKEN}" ]]; then
  echo "ERROR: Failed to extract access_token from auth response." >&2
  echo "Response: ${TOKEN_RESPONSE}" >&2
  exit 1
fi

TOKEN_LEN=${#API_TOKEN}
echo "Token fetched (length=${TOKEN_LEN}, starts=${API_TOKEN:0:10}...)"

# ── Step 2: Run setup-tokens ─────────────────────────────────────
echo ""
echo "=== Running setup-tokens (region=${REGION}) ==="
cd "${REPO_ROOT}"
poetry run setup-tokens \
  --region="${REGION}" \
  --api-token="${API_TOKEN}" \
  --vault-password="${VAULT_PASSWORD}" \
  --name="ci-e2e"

# ── Step 3: Verify the vault ─────────────────────────────────────
echo ""
echo "=== Verifying vault token ==="
VAULT_PASS_FILE="${EXAMPLES_DIR}/.vault_pass"
VAULT_FILE="${EXAMPLES_DIR}/group_vars/all/vault.yml"

if [[ ! -f "${VAULT_PASS_FILE}" ]]; then
  echo "ERROR: .vault_pass not found at ${VAULT_PASS_FILE}" >&2
  exit 1
fi

if [[ ! -f "${VAULT_FILE}" ]]; then
  echo "ERROR: vault.yml not found at ${VAULT_FILE}" >&2
  exit 1
fi

VAULT_TOKEN=$(ansible-vault view "${VAULT_FILE}" --vault-password-file "${VAULT_PASS_FILE}" \
  | python3 -c "import sys,yaml; d=yaml.safe_load(sys.stdin); t=d.get('sccfm_api_token',''); print(t)")

VAULT_TOKEN_LEN=${#VAULT_TOKEN}
echo "Vault token length: ${VAULT_TOKEN_LEN}"
echo "Vault token starts: ${VAULT_TOKEN:0:10}..."

if [[ "${API_TOKEN}" == "${VAULT_TOKEN}" ]]; then
  echo "PASS: Vault token matches the fetched token."
else
  echo "FAIL: Vault token does NOT match the fetched token!" >&2
  echo "  Fetched: ${API_TOKEN:0:20}..."
  echo "  Vault:   ${VAULT_TOKEN:0:20}..."
  exit 1
fi

# Verify region in vars.yml
VARS_FILE="${EXAMPLES_DIR}/group_vars/all/vars.yml"
VARS_REGION=$(grep 'sccfm_region:' "${VARS_FILE}" | awk '{print $2}')
echo "vars.yml region: ${VARS_REGION}"

if [[ "${VARS_REGION}" != "${REGION}" ]]; then
  echo "FAIL: vars.yml region '${VARS_REGION}' does not match expected '${REGION}'" >&2
  exit 1
fi

echo ""
echo "=== Token setup verified successfully ==="

# ── Step 4: Run e2e (unless --token-only) ─────────────────────────
if [[ "${1:-}" == "--token-only" ]]; then
  echo "Skipping e2e tests (--token-only)."
  exit 0
fi

echo ""
echo "=== Running e2e tests ==="
exec bash "${SCRIPT_DIR}/run_e2e.sh"
