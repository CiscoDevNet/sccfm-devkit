#!/usr/bin/env bash
#
# Activate the sccfm-devkit development environment.
#
# Usage: source scripts/activate.sh
#

# Handle both bash and zsh
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  _SCRIPT_PATH="${BASH_SOURCE[0]}"
elif [[ -n "${(%):-%x}" ]]; then
  _SCRIPT_PATH="${(%):-%x}"
else
  _SCRIPT_PATH="$0"
fi

PROJECT_ROOT="$(cd "$(dirname "$_SCRIPT_PATH")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
unset _SCRIPT_PATH

# Ensure script is sourced, not executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Error: This script must be sourced, not executed." >&2
  echo "Usage: source scripts/activate.sh" >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Virtualenv not found at ${VENV_DIR}. Run scripts/setup_environment.sh first." >&2
  return 1
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo "Activated environment at ${VENV_DIR}"
