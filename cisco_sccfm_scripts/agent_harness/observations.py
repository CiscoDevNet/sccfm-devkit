# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Normalize Codex shell records into typed SCCFM harness events."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from .models import BlockedCommand, CommandRecord, ToolEvent

SHELLS = {"bash", "sh", "zsh"}
CONTROL_TOKENS = {";", "&&", "||", "|", "&", "\n"}
PUNCTUATION_CHARS = ";&|\n"
# Longest first, so a run of punctuation splits into the operators a shell sees.
CONTROL_OPERATORS = ("&&", "||", ";", "|", "&", "\n")
# A terminator at either end of a command separates nothing, so it neither hides
# nor introduces a second segment.
TERMINATORS = {";", "\n"}
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
# setup_runtime.py is deliberately excluded from the absolute-path escape check
# below: the harness's python3 wrapper intercepts it by basename regardless of
# directory, and Codex's explicit-skill mode legitimately points the agent at
# the script's real, unstaged checkout path (see runner._prompt), which sits
# outside every allowed root. A genuine escape for it is still caught by the
# generic consume-based check, since a real invocation never records a stub
# event.
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
REDIRECTION = re.compile(r"^\d*(?:>>|>|<<|<)(?P<target>[^<>]*)$")
REDIRECTION_OPERATOR = re.compile(r"^\d*(?:>>|>|<<|<)$")
EXPANSION = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)|`[^`]*`|\$[A-Za-z_][A-Za-z0-9_]*|^~")


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


def is_single_operation_command(command: str, expected_operation: str) -> bool:
    """Return whether command is exactly one domain-tool operation.

    Confirmation commands deliberately exclude shell composition. This keeps an
    approval bound to one executable invocation rather than also authorizing a
    preceding ``cd``, pipeline, or second command.
    """

    tokens = _tokenize(command)
    if tokens is None or any(token in CONTROL_TOKENS for token in tokens):
        return False
    invocations = _invocations(command)
    if len(invocations) != 1:
        return False
    executable, argv = invocations[0]
    operation, _classification = _classify(Path(executable).name, argv)
    return operation == expected_operation


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
        # A double publishes structured output here when scoring has to read the
        # payload itself rather than whatever survived the agent's shell: a
        # schema piped through a filter reaches the agent as a projection, while
        # the event log still carries what the double actually served.
        published = payload.get("schema")
        events.append(
            ToolEvent(
                tool=tool,
                operation=operation,
                argv=tuple(argv),
                classification=classification,
                command=command,
                output=json.dumps(published) if isinstance(published, dict) else "",
                exit_code=exit_code if isinstance(exit_code, int) else None,
                origin="stub-event-log",
            )
        )
    return events, errors


def credential_leaks(path: Path) -> list[str]:
    """Return credential variable names any command double could still read.

    The doubles run inside real Bash subprocesses of the evaluated session, so an
    empty result is per-sample evidence that credential scrubbing held. Only
    variable names are recorded, never values.
    """

    if not path.exists():
        return []
    leaked: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        visible = payload.get("visible_credentials")
        if isinstance(visible, list):
            leaked.update(name for name in visible if isinstance(name, str))
    return sorted(leaked)


def unobserved_tool_commands(
    records: list[CommandRecord],
    observed: list[ToolEvent],
    blocked: list[BlockedCommand] | None = None,
    allowed_roots: tuple[Path, ...] = (),
) -> list[str]:
    """Return guarded invocations that did not execute through a command double."""

    remaining = list(observed)
    blocked_commands = {item.command for item in (blocked or [])}
    escaped: list[str] = []
    for record in records:
        if record.command in blocked_commands:
            continue
        invocations = _invocations_with_context(record.command)
        for executable, argv, conditional in invocations:
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
            # An allowed absolute path can be mentioned even though the shell
            # cannot execute it (for example, a missing optional companion
            # runtime). Such an attempt cannot have escaped to a real domain
            # tool and must not consume the event emitted by a later fallback.
            failed_before_execution = (
                executable_path.is_absolute()
                and any(resolved_executable.is_relative_to(root) for root in resolved_roots)
                and record.exit_code in {126, 127}
                and not executable_path.exists()
            )
            if failed_before_execution:
                continue
            expected_exit_code = (
                _reported_process_exit_code(record)
                if len(invocations) == 1 and not _has_shell_composition(record.command)
                else None
            )
            if (
                not _consume(remaining, operation, tuple(argv), expected_exit_code)
                and not conditional
            ):
                escaped.append(record.command)
    return escaped


def _consume(
    remaining: list[ToolEvent],
    operation: str,
    argv: tuple[str, ...],
    expected_exit_code: int | None = None,
) -> bool:
    """Remove one recorded invocation that this parsed command accounts for."""

    for index, event in enumerate(remaining):
        if event.operation != operation or len(event.argv) != len(argv):
            continue
        if expected_exit_code is not None and event.exit_code != expected_exit_code:
            continue
        if all(_token_matches(parsed, recorded) for parsed, recorded in zip(argv, event.argv)):
            del remaining[index]
            return True
    return False


def _reported_process_exit_code(record: CommandRecord) -> int | None:
    """Return the real exit code when an agent wrapper collapses failures.

    Claude reports a failed Bash tool call itself as exit code 1 and prefixes
    the captured output with the subprocess's real ``Exit code N``. Matching
    against that embedded code preserves correlation with the command-double
    event without weakening boundary checks for other failures.
    """

    if record.exit_code == 1:
        match = re.match(r"Exit code (?P<code>\d+)(?:\r?\n|$)", record.output)
        if match:
            return int(match.group("code"))
    return record.exit_code


def _has_shell_composition(command: str) -> bool:
    """Return whether another shell segment can determine the process exit code."""

    tokens = _tokenize(command)
    if tokens is None:
        return True
    return any(token in CONTROL_TOKENS for token in tokens)


def _tokenize(command: str) -> list[str] | None:
    """Split a command into words and the individual control operators a shell sees.

    ``shlex`` groups a run of punctuation characters into one token, so
    ``"sccfm-cli status ;\\n sccfm-cli objects network delete"`` arrives with a
    single ``";\\n"`` token that matches no control operator: the composition is
    invisible and the second invocation is absorbed into the first command's
    argv. Every run is expanded here so that cannot happen.

    Two shapes are normalized in the other direction, because they compose
    nothing and must not suppress exit-code correlation: a ``>&`` descriptor
    duplication is rejoined onto its redirection word, and a terminator at
    either end of the command is dropped.

    Returns ``None`` when the command cannot be lexed, leaving the decision
    about unparseable input to each caller.
    """

    source = _unwrap_shell(command)
    try:
        lexer = shlex.shlex(source, posix=True, punctuation_chars=PUNCTUATION_CHARS)
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexed = list(lexer)
    except ValueError:
        return None

    tokens: list[str] = []
    descriptor_pending = False
    for token in lexed:
        if token and set(token) <= set(PUNCTUATION_CHARS):
            for operator in _control_operators(token):
                if operator == "&" and tokens and REDIRECTION_OPERATOR.match(tokens[-1]):
                    tokens[-1] += operator
                    descriptor_pending = True
                    continue
                tokens.append(operator)
                descriptor_pending = False
            continue
        if descriptor_pending:
            tokens[-1] += token
            descriptor_pending = False
            continue
        tokens.append(token)

    start = 0
    end = len(tokens)
    while start < end and tokens[start] in TERMINATORS:
        start += 1
    while end > start and tokens[end - 1] in TERMINATORS:
        end -= 1
    return tokens[start:end]


def _control_operators(run: str) -> list[str]:
    """Split one run of punctuation characters into separate control operators."""

    operators: list[str] = []
    position = 0
    while position < len(run):
        for operator in CONTROL_OPERATORS:
            if run.startswith(operator, position):
                operators.append(operator)
                position += len(operator)
                break
        else:  # pragma: no cover - every punctuation character is an operator
            operators.append(run[position])
            position += 1
    return operators


def _token_matches(parsed: str, recorded: str) -> bool:
    """Compare one argument, tolerating expansions the shell resolved at runtime.

    The transcript holds the command as written, so a token such as
    ``"$TMPDIR/play.yml"`` can never equal the path the command double received.
    Every literal fragment around an expansion still has to match in order, so an
    argument that genuinely differs is still reported as an escape.
    """

    if parsed == recorded:
        return True
    if not EXPANSION.search(parsed):
        return False
    pattern = ""
    position = 0
    for match in EXPANSION.finditer(parsed):
        pattern += re.escape(parsed[position : match.start()]) + ".*"
        position = match.end()
    pattern += re.escape(parsed[position:])
    return re.fullmatch(pattern, recorded) is not None


def _invocations(command: str) -> list[tuple[str, list[str]]]:
    return [(executable, argv) for executable, argv, _ in _invocations_with_context(command)]


def _invocations_with_context(command: str) -> list[tuple[str, list[str], bool]]:
    tokens = _tokenize(command)
    if tokens is None:
        return []

    invocations = []
    expect_command = True
    conditional = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in CONTROL_TOKENS:
            expect_command = True
            conditional = token in {"&&", "||"}
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
            invocations.append((token, argv, conditional))
            expect_command = False
            continue
        if name.startswith("python") and index + 1 < len(tokens):
            script_token = tokens[index + 1]
            script_name = Path(script_token).name
            if script_name == "setup_runtime.py":
                argv, index = _arguments(tokens, index + 2)
                invocations.append((script_token, argv, conditional))
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
    if outer and Path(outer[0]).name in SHELLS:
        for flag in ("-lc", "-c"):
            if flag in outer:
                position = outer.index(flag)
                if position + 1 < len(outer):
                    return outer[position + 1]
    return command


def _arguments(tokens: list[str], start: int) -> tuple[list[str], int]:
    end = start
    argv: list[str] = []
    while end < len(tokens) and tokens[end] not in CONTROL_TOKENS:
        redirection = REDIRECTION.match(tokens[end])
        if redirection:
            # A redirection is shell syntax, not a tool argument. Dropping the
            # operator and any separate target keeps the parsed argv equal to the
            # argv the command double actually received.
            end += 1
            if not redirection.group("target") and (
                end < len(tokens) and tokens[end] not in CONTROL_TOKENS
            ):
                end += 1
            continue
        argv.append(tokens[end])
        end += 1
    return argv, end


def _classify(tool: str, argv: list[str]) -> tuple[str, str]:
    if tool == "sccfm-cli":
        return _classify_sccfm(argv)
    if not argv or any(argument in {"--help", "-h"} for argument in argv) or argv == ["--version"]:
        operation = (
            "setup.discovery"
            if tool in {"brew", "pipx", "setup_runtime.py"}
            else f"{tool}.discovery"
        )
        return operation, "discovery"
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
    if not argv or any(argument in {"--help", "-h"} for argument in argv):
        return "sccfm.help", "discovery"
    if argv in (["--version"], ["version"]):
        return "sccfm.version", "discovery"
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
    if not argv or any(argument in {"--help", "-h"} for argument in argv) or argv == ["--version"]:
        return "setup.discovery", "discovery"
    if any(argument in {"info", "list", "environment"} for argument in argv):
        return "setup.discovery", "discovery"
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
