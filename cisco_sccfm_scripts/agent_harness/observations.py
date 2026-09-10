# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Normalize Codex shell records into typed SCCFM harness events."""

from __future__ import annotations

import json
import re
import shlex
from collections import Counter
from pathlib import Path

from .models import BlockedCommand, CommandRecord, ToolEvent

SHELLS = {"bash", "sh", "zsh"}
CONTROL_TOKENS = {";", "&&", "||", "|", "&", "\n"}
SHELL_KEYWORDS = {"then", "else", "elif", "do"}
TOOLS = {
    "sccfm-cli",
    "ansible-doc",
    "ansible-playbook",
    "ansible-inventory",
    "ansible-galaxy",
    "brew",
    "pipx",
}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def normalize_tool_events(records: list[CommandRecord]) -> list[ToolEvent]:
    """Infer typed tool invocations only from shell command positions."""

    events = []
    for record in records:
        for executable, argv in _invocations(record.command):
            tool = Path(executable).name
            operation, classification = _classify(tool, argv)
            events.append(
                ToolEvent(
                    tool=tool,
                    operation=operation,
                    argv=tuple(argv),
                    classification=classification,
                    command=record.command,
                    output=record.output,
                    exit_code=record.exit_code,
                )
            )
    return events


def load_stub_events(path: Path) -> tuple[list[ToolEvent], list[str]]:
    """Load ground-truth command-double invocations from an isolated run."""

    if not path.exists():
        return [], []
    events: list[ToolEvent] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"invalid stub event at line {line_number}: {error.msg}")
            continue
        if not isinstance(payload, dict) or payload.get("origin") != "agent":
            continue
        tool = payload.get("tool")
        argv = payload.get("argv")
        exit_code = payload.get("exit_code")
        if (
            not isinstance(tool, str)
            or not isinstance(argv, list)
            or not all(isinstance(item, str) for item in argv)
        ):
            errors.append(f"invalid stub event shape at line {line_number}")
            continue
        operation, classification = _classify(tool, argv)
        command = shlex.join([tool, *argv])
        events.append(
            ToolEvent(
                tool=tool,
                operation=operation,
                argv=tuple(argv),
                classification=classification,
                command=command,
                output="",
                exit_code=exit_code if isinstance(exit_code, int) else None,
                origin="stub-event-log",
            )
        )
    return events, errors


def unobserved_tool_commands(
    records: list[CommandRecord],
    observed: list[ToolEvent],
    blocked: list[BlockedCommand] | None = None,
    allowed_roots: tuple[Path, ...] = (),
) -> list[str]:
    """Return guarded invocations that did not execute through a command double."""

    remaining = Counter((event.operation, event.argv) for event in observed)
    blocked_commands = [item.command for item in (blocked or [])]
    escaped: list[str] = []
    for record in records:
        for executable, argv in _invocations(record.command):
            if any(command in record.command for command in blocked_commands):
                continue
            tool = Path(executable).name
            operation, _classification = _classify(tool, argv)
            executable_path = Path(executable)
            resolved_executable = executable_path.resolve(strict=False)
            resolved_roots = tuple(root.resolve(strict=False) for root in allowed_roots)
            if (
                tool in TOOLS
                and executable_path.is_absolute()
                and not any(resolved_executable.is_relative_to(root) for root in resolved_roots)
            ):
                escaped.append(record.command)
                continue
            key = (operation, tuple(argv))
            if remaining[key]:
                remaining[key] -= 1
            else:
                escaped.append(record.command)
    return escaped


def _invocations(command: str) -> list[tuple[str, list[str]]]:
    source = _unwrap_shell(command)
    try:
        lexer = shlex.shlex(source, posix=True, punctuation_chars=";&|\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []

    invocations = []
    expect_command = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in CONTROL_TOKENS:
            expect_command = True
            index += 1
            continue
        if not expect_command:
            index += 1
            continue
        if token in SHELL_KEYWORDS or ENV_ASSIGNMENT.match(token):
            index += 1
            continue
        if token == "command" and index + 1 < len(tokens):
            if tokens[index + 1] == "-v":
                expect_command = False
                index += 1
                continue
            index += 1
            token = tokens[index]

        name = Path(token).name
        if name in TOOLS:
            argv, index = _arguments(tokens, index + 1)
            invocations.append((token, argv))
            expect_command = False
            continue
        if name.startswith("python") and index + 1 < len(tokens):
            script_token = tokens[index + 1]
            script_name = Path(script_token).name
            if script_name == "setup_runtime.py":
                argv, index = _arguments(tokens, index + 2)
                invocations.append((script_token, argv))
                expect_command = False
                continue
        expect_command = False
        index += 1
    return invocations


def _unwrap_shell(command: str) -> str:
    try:
        outer = shlex.split(command)
    except ValueError:
        return command
    if outer and Path(outer[0]).name in SHELLS and "-lc" in outer:
        position = outer.index("-lc")
        if position + 1 < len(outer):
            return outer[position + 1]
    return command


def _arguments(tokens: list[str], start: int) -> tuple[list[str], int]:
    end = start
    while end < len(tokens) and tokens[end] not in CONTROL_TOKENS:
        end += 1
    return tokens[start:end], end


def _classify(tool: str, argv: list[str]) -> tuple[str, str]:
    if tool == "sccfm-cli":
        return _classify_sccfm(argv)
    if tool == "ansible-doc":
        if "-l" in argv:
            return "ansible.module.list", "discovery"
        return "ansible.module.docs", "discovery"
    if tool == "ansible-playbook":
        if "--syntax-check" in argv:
            return "ansible.playbook.syntax_check", "local_validation"
        if "--check" in argv:
            return "ansible.playbook.check", "preflight"
        return "ansible.playbook.execute", "mutation"
    if tool == "ansible-inventory":
        return "ansible.inventory.inspect", "readonly"
    return _classify_setup(argv)


def _classify_sccfm(argv: list[str]) -> tuple[str, str]:
    joined = " ".join(argv)
    if re.search(r"(?:^| )schema export(?: |$)", joined):
        return "sccfm.schema.export", "discovery"
    if re.search(r"(?:^| )status(?: |$)", joined):
        return "sccfm.status", "readonly"
    if re.search(r"(?:^| )inventory devices asa list(?: |$)", joined):
        return "sccfm.inventory.devices.asa.list", "readonly"
    if re.search(r"(?:^| )objects network delete(?: |$)", joined):
        classification = "preflight" if "--check" in argv else "mutation"
        suffix = ".check" if classification == "preflight" else ""
        return f"sccfm.objects.network.delete{suffix}", classification
    if re.search(r"(?:^| )configure(?: |$)", joined):
        return "sccfm.configure", "local_mutation"
    return "sccfm.unknown", "unknown"


def _classify_setup(argv: list[str]) -> tuple[str, str]:
    if "cleanup-plan" in argv:
        return "setup.cleanup_plan", "discovery"
    if "cleanup" in argv:
        return "setup.cleanup", "local_mutation"
    if "doctor" in argv:
        return "setup.doctor", "readonly"
    if "plan" in argv:
        return "setup.install_plan", "discovery"
    if "install" in argv:
        return "setup.install", "local_mutation"
    return "setup.unknown", "unknown"
