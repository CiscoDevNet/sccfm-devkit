#!/usr/bin/env bash
# PostToolUse hook (Write|Edit|MultiEdit): keep Claude's Python edits CI-clean.
#   1. Stamp the Apache-2.0 SPDX header on new files (reuse gate)
#   2. isort + black (formatting / import-order gates)
#   3. flake8 as ADVISORY context fed back to Claude (never blocks)
# Reads the hook JSON on stdin; resolves the project root from CLAUDE_PROJECT_DIR.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-.}"

# Extract the edited file path from the hook payload.
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  exit 0
fi

payload=$(cat)
if ! f=$(printf '%s' "$payload" | "$PYTHON_BIN" -c '
import json
import sys

payload = json.load(sys.stdin)
tool_input = payload.get("tool_input", {})
tool_response = payload.get("tool_response", {})
print(tool_input.get("file_path") or tool_response.get("filePath") or "")
' 2>/dev/null); then
  exit 0
fi
[ -n "$f" ] || exit 0
case "$f" in
  *.py) ;;
  *) exit 0 ;;
esac
case "$f" in
  /*) target="$f" ;;
  *) target="$ROOT/$f" ;;
esac
[ -f "$target" ] || exit 0

# --- 1. License header (idempotent, shebang-aware) ---
if ! grep -q "SPDX-License-Identifier:" "$target" 2>/dev/null; then
  header=$'# Copyright 2026 Cisco Systems, Inc. and its affiliates\n#\n# SPDX-License-Identifier: Apache-2.0\n'
  first=$(head -1 "$target")
  second=$(sed -n '2p' "$target")
  tmp=$(mktemp)
  encoding_re='coding[:=][[:space:]]*[-_.[:alnum:]]+'
  if printf '%s' "$first" | grep -q '^#!'; then
    if printf '%s' "$second" | grep -Eq "$encoding_re"; then
      { printf '%s\n' "$first"; printf '%s\n' "$second"; printf '%s\n' "$header"; tail -n +3 "$target"; } > "$tmp"
    else
      { printf '%s\n' "$first"; printf '%s\n' "$header"; tail -n +2 "$target"; } > "$tmp"
    fi
  elif printf '%s' "$first" | grep -Eq "$encoding_re"; then
    { printf '%s\n' "$first"; printf '%s\n' "$header"; tail -n +2 "$target"; } > "$tmp"
  else
    { printf '%s\n' "$header"; cat "$target"; } > "$tmp"
  fi
  cat "$tmp" > "$target"
  rm -f "$tmp"
fi

# --- 2. Formatters (silent; pre-commit/CI are the hard gate) ---
if [ -x "$ROOT/.venv/bin/isort" ]; then "$ROOT/.venv/bin/isort" -q "$target" >/dev/null 2>&1 || true
elif command -v isort >/dev/null 2>&1; then isort -q "$target" >/dev/null 2>&1 || true; fi

if [ -x "$ROOT/.venv/bin/black" ]; then "$ROOT/.venv/bin/black" -q "$target" >/dev/null 2>&1 || true
elif command -v black >/dev/null 2>&1; then black -q "$target" >/dev/null 2>&1 || true; fi

# --- 3. Advisory flake8 -> fed back to Claude as context, never blocks ---
flake8_bin=""
if [ -x "$ROOT/.venv/bin/flake8" ]; then flake8_bin="$ROOT/.venv/bin/flake8"
elif command -v flake8 >/dev/null 2>&1; then flake8_bin="flake8"; fi

if [ -n "$flake8_bin" ]; then
  issues=$("$flake8_bin" "$target" 2>/dev/null)
  if [ -n "$issues" ]; then
    ctx="flake8 findings on $f (advisory — fix before committing; reuse/black already applied):"$'\n'"$issues"
    HOOK_CONTEXT="$ctx" "$PYTHON_BIN" -c '
import json
import os

print(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": os.environ["HOOK_CONTEXT"],
            }
        }
    )
)
'
  fi
fi
exit 0
