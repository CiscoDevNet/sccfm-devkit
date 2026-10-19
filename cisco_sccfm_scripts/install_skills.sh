#!/usr/bin/env bash
#
# Install the sccfm-devkit agent skills into a user-level skills directory
# so that Claude Code (and other agent tools that read ~/.claude/skills/)
# can discover them outside of this repository.
#
# Usage:
#   ./cisco_sccfm_scripts/install_skills.sh                    # install to ~/.claude/skills
#   ./cisco_sccfm_scripts/install_skills.sh /path/to/skills    # install to a custom dir
#   ./cisco_sccfm_scripts/install_skills.sh --uninstall        # remove installed skills
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${PROJECT_ROOT}/skills"
DEFAULT_TARGET="${HOME}/.claude/skills"
SKILLS=(sccfm-cli sccfm-ansible)

usage() {
  sed -n '2,12p' "${BASH_SOURCE[0]}"
  exit "${1:-0}"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage 0
fi

if [[ "${1:-}" == "--uninstall" ]]; then
  TARGET_DIR="${2:-${DEFAULT_TARGET}}"
  for skill in "${SKILLS[@]}"; do
    if [[ -e "${TARGET_DIR}/${skill}" || -L "${TARGET_DIR}/${skill}" ]]; then
      rm -rf "${TARGET_DIR}/${skill}"
      echo "Removed ${TARGET_DIR}/${skill}"
    fi
  done
  exit 0
fi

TARGET_DIR="${1:-${DEFAULT_TARGET}}"

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "Error: source skills directory not found: ${SOURCE_DIR}" >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"

for skill in "${SKILLS[@]}"; do
  src="${SOURCE_DIR}/${skill}"
  dst="${TARGET_DIR}/${skill}"
  if [[ ! -d "${src}" ]]; then
    echo "Warning: missing source skill ${src}, skipping" >&2
    continue
  fi
  rm -rf "${dst}"
  cp -R "${src}" "${dst}"
  echo "Installed ${skill} -> ${dst}"
done

echo
echo "Done. Restart Claude Code (or your agent) to pick up the new skills."
