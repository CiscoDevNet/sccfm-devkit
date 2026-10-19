#!/usr/bin/env bash
# PreToolUse hook (Read|Edit|MultiEdit|Write): block access to secret-bearing files.
# Covers the .env family AND ansible vault secrets. Always allows *.example templates.
# Matches on the tool's file_path only -- Bash commands are NOT scanned (gitleaks and
# .gitignore are the barriers against committing secrets). Emits a PreToolUse "deny"
# decision as JSON; silent (allow) otherwise.
#
# Fails OPEN (allows) if no Python interpreter is available: this is a defense-in-depth
# layer, and denying every file read on a machine without the venv would be worse than
# the brief window before cisco_sccfm_scripts/setup_environment.sh runs.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-.}"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  exit 0
fi

cat | "$PYTHON_BIN" -c '
import json
import os
import sys

# Exact basenames that are always secrets, plus the .env.* family handled below.
PROTECTED_NAMES = (".env", ".vault_pass", "vault.yml", "vault.yaml")


def deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def is_protected(file_path):
    # Case-insensitive: macOS/Windows filesystems resolve Vault.yml to vault.yml.
    basename = os.path.basename(file_path).lower()
    if basename.endswith(".example"):
        return False
    if basename in PROTECTED_NAMES:
        return True
    return basename.startswith(".env.")


try:
    payload = json.load(sys.stdin)
    tool_input = payload["tool_input"]
    file_path = tool_input.get("file_path")
except (json.JSONDecodeError, KeyError, TypeError):
    # Malformed payload: allow (file tools always send tool_input.file_path; a missing
    # one means there is no path to protect).
    sys.exit(0)

if isinstance(file_path, str) and file_path and is_protected(file_path):
    deny(
        "Access to "
        + os.path.basename(file_path)
        + " is blocked by project policy: this file may contain secrets. "
        + "Use the corresponding .example template instead."
    )
'
