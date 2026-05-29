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
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CLIResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    json: Any | None


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
    """
    cmd: list[str] = [
        *_resolve_binary(),
        "--profile",
        profile,
        "--silent",
        *args,
    ]

    env = os.environ.copy()
    env["SCCFM_CONFIG"] = str(config_path)

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
        raise AssertionError(
            f"sccfm-cli command timed out after {exc.timeout}s: {' '.join(cmd)}\n"
            f"--- stdout ---\n{_decode(exc.stdout)}\n"
            f"--- stderr ---\n{_decode(exc.stderr)}"
        ) from exc

    payload = _parse_json_payload(completed.stdout) if parse_json else None
    result = CLIResult(
        args=tuple(cmd),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        json=payload,
    )

    if tolerate_any_rc:
        return result
    if expect_failure:
        if completed.returncode == 0:
            raise AssertionError(
                f"sccfm-cli command unexpectedly succeeded: {' '.join(cmd)}\n"
                f"--- stdout ---\n{completed.stdout}\n"
                f"--- stderr ---\n{completed.stderr}"
            )
        if expected_error is not None:
            needles = (expected_error,) if isinstance(expected_error, str) else expected_error
            haystack = (completed.stdout + "\n" + completed.stderr).lower()
            if not any(needle.lower() in haystack for needle in needles):
                raise AssertionError(
                    f"sccfm-cli failed (rc={completed.returncode}) but the output "
                    f"did not contain any expected error marker {needles!r}: "
                    f"{' '.join(cmd)}\n"
                    f"--- stdout ---\n{completed.stdout}\n"
                    f"--- stderr ---\n{completed.stderr}"
                )
    elif completed.returncode != 0:
        raise AssertionError(
            f"sccfm-cli command failed (rc={completed.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{completed.stdout}\n"
            f"--- stderr ---\n{completed.stderr}"
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
