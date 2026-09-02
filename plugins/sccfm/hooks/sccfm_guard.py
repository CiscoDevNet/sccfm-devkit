#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Gate risky SCCFM shell commands with short-lived, exact-command approvals."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal, Sequence, cast

SCCFM_EXECUTABLE = "sccfm-cli"
ANSIBLE_REVIEW_COMMANDS = {"ansible-galaxy", "ansible-playbook"}
SAFE_ANSIBLE_ENVIRONMENT = {"ANSIBLE_LOCAL_TEMP"}
SHELL_CONTROL_CHARACTERS = frozenset(";&|<>")
SHELL_SUBSTITUTION_MARKERS = ("$", "`")
SHELL_WRAPPER_EXECUTABLES = {
    "bash",
    "command",
    "env",
    "nohup",
    "nice",
    "sh",
    "sudo",
    "time",
    "xargs",
    "zsh",
}
APPROVAL_PREFIX = "EXECUTE "
APPROVAL_TTL_SECONDS = 600
PLAN_TTL_SECONDS = 3600
Host = Literal["claude", "codex"]


def shell_tokens(command: str) -> list[str] | None:
    if any(marker in command for marker in SHELL_SUBSTITUTION_MARKERS):
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    if any(set(token) <= SHELL_CONTROL_CHARACTERS for token in tokens):
        return None
    return tokens


def executable_name(token: str) -> str:
    return Path(token).name


def is_assignment_word(token: str) -> bool:
    name, separator, _value = token.partition("=")
    return bool(
        separator
        and name
        and (name[0].isalpha() or name[0] == "_")
        and all(character.isalnum() or character == "_" for character in name[1:])
    )


def contains_guarded_executable(command: str) -> bool:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return any(
            executable in command
            for executable in (SCCFM_EXECUTABLE, *sorted(ANSIBLE_REVIEW_COMMANDS))
        )
    guarded_executables = {SCCFM_EXECUTABLE, *ANSIBLE_REVIEW_COMMANDS}
    execution_index = 0
    while execution_index < len(tokens) and is_assignment_word(tokens[execution_index]):
        execution_index += 1
    if (
        execution_index < len(tokens)
        and executable_name(tokens[execution_index]) in guarded_executables
    ):
        return True
    for index, token in enumerate(tokens[1:], start=1):
        if executable_name(token) not in guarded_executables:
            continue
        previous = tokens[index - 1]
        if set(previous) <= SHELL_CONTROL_CHARACTERS or previous in {"-exec", "-execdir"}:
            return True
    first_executable = (
        executable_name(tokens[execution_index]) if execution_index < len(tokens) else ""
    )
    if first_executable in SHELL_WRAPPER_EXECUTABLES:
        return any(
            executable_name(token) in guarded_executables
            or (
                first_executable in {"bash", "sh", "zsh"}
                and any(executable in token for executable in guarded_executables)
            )
            for token in tokens[execution_index + 1 :]
        )
    return False


def is_executable_discovery(tokens: Sequence[str]) -> bool:
    guarded_executables = {SCCFM_EXECUTABLE, *ANSIBLE_REVIEW_COMMANDS}
    return bool(
        len(tokens) >= 3
        and list(tokens[:2]) == ["command", "-v"]
        and all(executable_name(token) in guarded_executables for token in tokens[2:])
    )


def strip_safe_ansible_environment(tokens: Sequence[str]) -> list[str] | None:
    remaining = list(tokens)
    seen_names: set[str] = set()
    while remaining and is_assignment_word(remaining[0]):
        name, _separator, value = remaining.pop(0).partition("=")
        local_path = Path(value)
        if (
            name not in SAFE_ANSIBLE_ENVIRONMENT
            or name in seen_names
            or not local_path.is_absolute()
            or ".." in local_path.parts
        ):
            return None
        seen_names.add(name)
    if seen_names and (
        not remaining or executable_name(remaining[0]) not in ANSIBLE_REVIEW_COMMANDS
    ):
        return None
    return remaining


def load_schema() -> dict[str, Any] | None:
    executable = shutil.which(SCCFM_EXECUTABLE)
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, "schema", "export", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        return None
    return payload if isinstance(payload, dict) else None


def strip_global_options(tokens: Sequence[str], schema: dict[str, Any]) -> list[str] | None:
    options: dict[str, dict[str, Any]] = {}
    for option in schema.get("global_options", []):
        for alias in option.get("aliases", []):
            options[alias] = option

    remaining = list(tokens)
    while remaining and remaining[0].startswith("-"):
        token = remaining.pop(0)
        if token in {"--help", "-h"}:
            return ["--help"]
        flag, separator, _value = token.partition("=")
        option = options.get(flag)
        if option is None:
            return None
        if not separator and not option.get("is_flag", False):
            if not remaining:
                return None
            remaining.pop(0)
    return remaining


def enabled_command_flag(
    arguments: Sequence[str], command: dict[str, Any], option_name: str
) -> bool:
    options_by_alias = {
        alias: option
        for option in command.get("options", [])
        for alias in option.get("aliases", [])
    }
    argument_index = 0
    while argument_index < len(arguments):
        token = arguments[argument_index]
        flag, separator, _value = token.partition("=")
        option = options_by_alias.get(flag)
        if option is None:
            argument_index += 1
            continue
        if not separator and option.get("is_flag") is True and option.get("name") == option_name:
            return True
        if not separator and option.get("is_flag") is not True:
            nargs = option.get("nargs", 1)
            argument_index += nargs if isinstance(nargs, int) and nargs > 0 else 1
        argument_index += 1
    return False


def is_schema_declared_preflight(arguments: Sequence[str], command: dict[str, Any]) -> bool:
    for constraint in command.get("constraints", []):
        effect = constraint.get("effect", "")
        option_name = constraint.get("option")
        if (
            constraint.get("type") == "mode"
            and isinstance(option_name, str)
            and isinstance(effect, str)
            and "preflight only" in effect.casefold()
            and "do not perform" in effect.casefold()
            and enabled_command_flag(arguments, command, option_name)
        ):
            return True
    return False


def classify_sccfm(tokens: Sequence[str], schema: dict[str, Any]) -> tuple[str, str]:
    executable_indexes = [
        index for index, token in enumerate(tokens) if executable_name(token) == SCCFM_EXECUTABLE
    ]
    if len(executable_indexes) != 1 or executable_indexes[0] != 0:
        return "review", "SCCFM command composition could not be proven safe"

    remaining = strip_global_options(tokens[1:], schema)
    if remaining is None:
        return "review", "SCCFM global options could not be classified"
    if remaining == ["--help"] or not remaining:
        return "readonly", "SCCFM help invocation"

    commands = sorted(
        schema.get("commands", []),
        key=lambda command: len(command.get("path", [])),
        reverse=True,
    )
    for command in commands:
        path = command.get("path", [])
        if list(remaining[: len(path)]) != path:
            continue
        arguments = remaining[len(path) :]
        if is_schema_declared_preflight(arguments, command):
            return "readonly", f"Schema-declared SCCFM preflight: {' '.join(path)}"
        if not command.get("readonly", False):
            return "review", f"Mutating SCCFM command: {' '.join(path)}"
        if path == ["schema", "export"] and not ({"--output", "-o"} & set(remaining)):
            return "readonly", "Schema export to standard output"
        if command.get("side_effects"):
            return "review", f"SCCFM command has local side effects: {' '.join(path)}"
        return "readonly", f"Read-only SCCFM command: {' '.join(path)}"
    return "review", "SCCFM command path is absent from the installed schema"


def classify_command(command: str, schema: dict[str, Any] | None = None) -> tuple[str, str]:
    tokens = shell_tokens(command)
    if tokens is not None and is_executable_discovery(tokens):
        return "readonly", "SCCFM executable discovery"
    if not contains_guarded_executable(command):
        return "unrelated", "Command is outside the SCCFM guard scope"
    if tokens is None:
        return "review", "Compound or unparseable SCCFM command requires review"
    execution_tokens = strip_safe_ansible_environment(tokens)
    if execution_tokens is None:
        return "review", "Command environment or composition could not be proven safe"
    executable = executable_name(execution_tokens[0]) if execution_tokens else ""
    if executable == "ansible-playbook" and "--syntax-check" in execution_tokens[1:]:
        return "readonly", "Ansible local syntax check"
    if executable in ANSIBLE_REVIEW_COMMANDS:
        return "review", f"{executable} can change local or managed state"
    if executable != SCCFM_EXECUTABLE:
        return "review", "Nested SCCFM invocation requires review"
    active_schema = schema if schema is not None else load_schema()
    if active_schema is None:
        return "review", "The installed SCCFM schema was unavailable"
    if uses_sensitive_flag(tokens, active_schema):
        return "review", "SCCFM command includes a sensitive option"
    return classify_sccfm(tokens, active_schema)


def sensitive_flags(schema: dict[str, Any]) -> set[str]:
    flags: set[str] = set()
    command_options = [
        option for command in schema.get("commands", []) for option in command.get("options", [])
    ]
    for option in [*schema.get("global_options", []), *command_options]:
        if option.get("sensitive"):
            flags.update(option.get("aliases", []))
    return flags


def uses_sensitive_flag(tokens: Sequence[str], schema: dict[str, Any]) -> bool:
    protected_flags = sensitive_flags(schema)
    return any(token.partition("=")[0] in protected_flags for token in tokens)


def approval_eligible(command: str, schema: dict[str, Any] | None = None) -> bool:
    tokens = shell_tokens(command)
    if not tokens:
        return False
    execution_tokens = strip_safe_ansible_environment(tokens)
    if not execution_tokens:
        return False
    executable = executable_name(execution_tokens[0])
    if executable in ANSIBLE_REVIEW_COMMANDS:
        classification, _reason = classify_command(command, schema)
        return classification == "review"
    if executable != SCCFM_EXECUTABLE:
        return False
    active_schema = schema if schema is not None else load_schema()
    if active_schema is None or uses_sensitive_flag(tokens, active_schema):
        return False
    classification, reason = classify_sccfm(tokens, active_schema)
    return classification == "review" and reason.startswith(
        ("Mutating SCCFM command:", "SCCFM command has local side effects:")
    )


def plugin_data_directory() -> Path | None:
    configured = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(configured) if configured else None


def detected_host() -> Host:
    return "claude" if os.environ.get("CLAUDE_PLUGIN_ROOT") else "codex"


def approval_path(state_directory: Path, session_id: str) -> Path:
    session_digest = hashlib.sha256(session_id.encode()).hexdigest()
    return state_directory / "sccfm-command-approvals" / f"{session_digest}.json"


def plan_path(state_directory: Path, session_id: str) -> Path:
    session_digest = hashlib.sha256(session_id.encode()).hexdigest()
    return state_directory / "sccfm-command-plans" / f"{session_digest}.json"


def command_digest(command: str) -> str:
    return hashlib.sha256(command.encode()).hexdigest()


def store_command_digest(
    receipt_path: Path,
    command: str,
    ttl_seconds: int,
    *,
    now: float | None = None,
) -> None:
    directory = receipt_path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        directory.chmod(0o700)
    receipt = {
        "command_sha256": command_digest(command),
        "expires_at": (time.time() if now is None else now) + ttl_seconds,
    }
    temporary_path = receipt_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(receipt), encoding="utf-8")
    if os.name != "nt":
        temporary_path.chmod(0o600)
    temporary_path.replace(receipt_path)


def store_approval(
    state_directory: Path, session_id: str, command: str, *, now: float | None = None
) -> None:
    store_command_digest(
        approval_path(state_directory, session_id),
        command,
        APPROVAL_TTL_SECONDS,
        now=now,
    )


def store_plan(
    state_directory: Path, session_id: str, command: str, *, now: float | None = None
) -> None:
    store_command_digest(
        plan_path(state_directory, session_id),
        command,
        PLAN_TTL_SECONDS,
        now=now,
    )


def remove_receipt(receipt_path: Path) -> bool:
    try:
        receipt_path.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def consume_approval(
    state_directory: Path, session_id: str, command: str, *, now: float | None = None
) -> bool:
    receipt_path = approval_path(state_directory, session_id)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not remove_receipt(receipt_path):
        return False
    current_time = time.time() if now is None else now
    expected_digest = receipt.get("command_sha256")
    expires_at = receipt.get("expires_at")
    return bool(
        isinstance(expected_digest, str)
        and isinstance(expires_at, (int, float))
        and current_time <= expires_at
        and hmac.compare_digest(expected_digest, command_digest(command))
    )


def consume_matching_plan(
    state_directory: Path, session_id: str, command: str, *, now: float | None = None
) -> bool:
    receipt_path = plan_path(state_directory, session_id)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    current_time = time.time() if now is None else now
    expected_digest = receipt.get("command_sha256")
    expires_at = receipt.get("expires_at")
    valid = bool(
        isinstance(expected_digest, str)
        and isinstance(expires_at, (int, float))
        and current_time <= expires_at
    )
    if not valid:
        remove_receipt(receipt_path)
        return False
    if not hmac.compare_digest(expected_digest, command_digest(command)):
        return False
    return remove_receipt(receipt_path)


def exact_approval_command(prompt: str) -> str | None:
    normalized = prompt.strip()
    if "\n" in normalized or not normalized.startswith(APPROVAL_PREFIX):
        return None
    command = normalized.removeprefix(APPROVAL_PREFIX).strip()
    return command or None


def planned_command(message: str) -> str | None:
    candidates = [
        line.removeprefix(APPROVAL_PREFIX).strip()
        for line in message.splitlines()
        if line.startswith(APPROVAL_PREFIX)
    ]
    if len(candidates) != 1:
        return None
    return candidates[0] or None


def deny_decision(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{reason}. The user must send the exact `EXECUTE <shell command>` "
                "from the reviewed plan in a separate message."
            ),
        }
    }


def process_user_prompt(
    event: dict[str, Any], state_directory: Path, schema: dict[str, Any] | None = None
) -> bool:
    prompt = event.get("prompt")
    session_id = event.get("session_id")
    if not isinstance(prompt, str) or not isinstance(session_id, str):
        return False
    command = exact_approval_command(prompt)
    if command is None or not approval_eligible(command, schema):
        return False
    if not consume_matching_plan(state_directory, session_id, command):
        return False
    store_approval(state_directory, session_id, command)
    return True


def process_assistant_plan(
    event: dict[str, Any], state_directory: Path, schema: dict[str, Any] | None = None
) -> bool:
    message = event.get("last_assistant_message")
    session_id = event.get("session_id")
    if not isinstance(message, str) or not isinstance(session_id, str):
        return False
    remove_receipt(approval_path(state_directory, session_id))
    command = planned_command(message)
    if command is None or not approval_eligible(command, schema):
        remove_receipt(plan_path(state_directory, session_id))
        return False
    store_plan(state_directory, session_id, command)
    return True


def process_tool_use(
    event: dict[str, Any],
    host: Host,
    state_directory: Path | None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    command = event.get("tool_input", {}).get("command")
    if not isinstance(command, str):
        return None
    classification, reason = classify_command(command, schema)
    if classification != "review":
        return None
    session_id = event.get("session_id")
    approved = bool(
        state_directory is not None
        and isinstance(session_id, str)
        and approval_eligible(command, schema)
        and consume_approval(state_directory, session_id, command)
    )
    if not approved:
        return deny_decision(reason)
    return None


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=("claude", "codex"))
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--record-plan", action="store_true")
    action.add_argument("--record-approval", action="store_true")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    state_directory = plugin_data_directory()
    if arguments.record_plan:
        if state_directory is not None:
            process_assistant_plan(event, state_directory)
        return
    if arguments.record_approval:
        if state_directory is not None:
            process_user_prompt(event, state_directory)
        return
    host = detected_host() if arguments.host is None else cast(Host, arguments.host)
    decision = process_tool_use(event, host, state_directory)
    if decision is not None:
        print(json.dumps(decision))


if __name__ == "__main__":
    main()
