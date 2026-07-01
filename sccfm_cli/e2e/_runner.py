# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared subprocess runner for the sccfm-cli e2e suite.

Each lifecycle phase invokes the installed ``sccfm-cli`` binary in a
subprocess so the tests exercise the same entrypoint, argv parsing and
exit codes that real users see.  Phases pass ``--format json`` and the
runner parses stdout, returning a :class:`CLIResult` that test code can
assert against.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SENSITIVE_FLAGS = frozenset(("--cli-key", "--ftd-password", "--jump-password"))
_REDACTED = "<redacted>"


@dataclass(frozen=True)
class CLIResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    json: Any | None = field(repr=False)


def _redact_args(args: list[str], sensitive_values: tuple[str, ...]) -> tuple[str, ...]:
    """Return log-safe argv with secret options and values removed."""
    values = {value for value in sensitive_values if value}
    redacted: list[str] = []
    redact_next = False
    for arg in args:
        if redact_next or arg in values:
            redacted.append(_REDACTED)
            redact_next = False
            continue
        redacted.append(arg)
        redact_next = arg in _SENSITIVE_FLAGS
    return tuple(redacted)


def _redact_text(value: str, sensitive_values: tuple[str, ...]) -> str:
    """Remove explicit secrets from captured subprocess output."""
    redacted = value
    for sensitive_value in sensitive_values:
        if sensitive_value:
            redacted = redacted.replace(sensitive_value, _REDACTED)
    return redacted


def _json_field_secrets(payload: Any, field_names: frozenset[str]) -> tuple[str, ...]:
    if isinstance(payload, dict):
        secrets: list[str] = []
        for key, value in payload.items():
            if key in field_names and isinstance(value, str):
                secrets.append(value)
            secrets.extend(_json_field_secrets(value, field_names))
        return tuple(secrets)
    if isinstance(payload, list):
        return tuple(
            secret for item in payload for secret in _json_field_secrets(item, field_names)
        )
    return ()


def _redact_json_fields(value: str, field_names: tuple[str, ...]) -> str:
    """Mask named JSON string fields even when the complete payload is malformed."""
    redacted = value
    for field_name in field_names:
        pattern = re.compile(
            rf'("{re.escape(field_name)}"\s*:\s*)"(?:\\.|[^"\\])*"',
            re.IGNORECASE,
        )
        redacted = pattern.sub(rf'\1"{_REDACTED}"', redacted)
    return redacted


def _redact_payload(payload: Any, sensitive_values: tuple[str, ...]) -> Any:
    """Return a copy of parsed output with explicit secrets removed."""
    if isinstance(payload, dict):
        return {key: _redact_payload(value, sensitive_values) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_redact_payload(value, sensitive_values) for value in payload]
    if isinstance(payload, str):
        return _redact_text(payload, sensitive_values)
    return payload


def _resolve_binary() -> list[str]:
    binary = shutil.which("sccfm-cli")
    if binary:
        return [binary]
    return [sys.executable, "-m", "sccfm_cli.cli"]


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _parse_json_payload(stdout: str) -> Any | None:
    """Parse JSON from stdout, tolerating any non-JSON prefix."""
    if not stdout.strip():
        return None
    for opener in ("{", "["):
        idx = stdout.find(opener)
        if idx == -1:
            continue
        try:
            return json.loads(stdout[idx:])
        except json.JSONDecodeError:
            continue
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def run_cli(
    *args: str,
    profile: str,
    config_path: Path,
    timeout: int = 300,
    expect_failure: bool = False,
    expected_error: str | tuple[str, ...] | None = None,
    tolerate_any_rc: bool = False,
    parse_json: bool = True,
    sensitive_values: tuple[str, ...] = (),
    redact_json_fields: tuple[str, ...] = (),
    extra_env: Mapping[str, str] | None = None,
) -> CLIResult:
    """Invoke ``sccfm-cli`` and return the parsed result.

    The runner prepends ``--profile <profile> --silent`` to mirror how the
    e2e suite always operates (machine-parseable output, no spinners).
    Phases append ``--format json`` themselves when they need a parsed
    payload — keeping the choice with the phase makes the invocation read
    the same as a copy-pasted command.

    Set ``expect_failure=True`` to assert that rc != 0 (used by idempotency
    phases that re-create / re-delete and expect "already exists" / "not
    found").  Pair it with ``expected_error`` — a substring or tuple of
    substrings, matched case-insensitively against stdout+stderr — so a
    transient 401/500/config failure can't masquerade as the specific
    "already exists" / "not found" rejection the phase is asserting.

    Set ``tolerate_any_rc=True`` for cleanup paths where a fresh
    tenant has nothing to remove and rc != 0 is fine.

    Pass one-time credentials through ``sensitive_values``. When a command
    creates a secret, name its response fields in ``redact_json_fields``. The
    parsed payload remains available to the phase, but captured output, args,
    reprs, and every assertion message contain only a redacted placeholder.
    """
    cmd: list[str] = [
        *_resolve_binary(),
        "--profile",
        profile,
        "--silent",
        *args,
    ]
    display_args = _redact_args(cmd, sensitive_values)
    display_command = " ".join(display_args)

    env = os.environ.copy()
    env["SCCFM_CONFIG"] = str(config_path)
    env.update(extra_env or {})

    try:
        completed = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        safe_stdout = _redact_json_fields(
            _redact_text(_decode(exc.stdout), sensitive_values), redact_json_fields
        )
        safe_stderr = _redact_json_fields(
            _redact_text(_decode(exc.stderr), sensitive_values), redact_json_fields
        )
        raise AssertionError(
            f"sccfm-cli command timed out after {exc.timeout}s: {display_command}\n"
            f"--- stdout ---\n{safe_stdout}\n"
            f"--- stderr ---\n{safe_stderr}"
        ) from None

    payload = _parse_json_payload(completed.stdout) if parse_json else None
    response_secrets = _json_field_secrets(payload, frozenset(redact_json_fields))
    all_sensitive_values = (*sensitive_values, *response_secrets)
    safe_stdout = _redact_json_fields(
        _redact_text(completed.stdout, all_sensitive_values), redact_json_fields
    )
    safe_stderr = _redact_json_fields(
        _redact_text(completed.stderr, all_sensitive_values), redact_json_fields
    )
    result = CLIResult(
        args=display_args,
        returncode=completed.returncode,
        stdout=safe_stdout,
        stderr=safe_stderr,
        json=_redact_payload(payload, sensitive_values),
    )

    if tolerate_any_rc:
        return result
    if expect_failure:
        if completed.returncode == 0:
            raise AssertionError(
                f"sccfm-cli command unexpectedly succeeded: {display_command}\n"
                f"--- stdout ---\n{safe_stdout}\n"
                f"--- stderr ---\n{safe_stderr}"
            )
        if expected_error is not None:
            needles = (expected_error,) if isinstance(expected_error, str) else expected_error
            haystack = (safe_stdout + "\n" + safe_stderr).lower()
            if not any(needle.lower() in haystack for needle in needles):
                raise AssertionError(
                    f"sccfm-cli failed (rc={completed.returncode}) but the output "
                    f"did not contain any expected error marker {needles!r}: "
                    f"{display_command}\n"
                    f"--- stdout ---\n{safe_stdout}\n"
                    f"--- stderr ---\n{safe_stderr}"
                )
    elif completed.returncode != 0:
        raise AssertionError(
            f"sccfm-cli command failed (rc={completed.returncode}): {display_command}\n"
            f"--- stdout ---\n{safe_stdout}\n"
            f"--- stderr ---\n{safe_stderr}"
        )

    return result


def get_json(result: CLIResult) -> Any:
    """Return ``result.json`` or raise a descriptive AssertionError."""
    if result.json is None:
        raise AssertionError(
            f"Expected JSON output for: {' '.join(result.args)}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    return result.json
