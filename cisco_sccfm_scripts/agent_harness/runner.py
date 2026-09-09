# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Codex subprocess runner and JSONL parser."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from .models import (
    AssertionResult,
    BlockedCommand,
    CommandRecord,
    Fixture,
    Mode,
    Outcome,
    SampleResult,
    Transcript,
)
from .observations import load_stub_events, normalize_tool_events, unobserved_tool_commands
from .rubric import score
from .stubs import install_stubs, isolated_environment


def build_codex_command(
    fixture: Fixture,
    mode: Mode,
    workspace: Path,
    repository_root: Path,
    model: str | None,
    bypass_hook_trust: bool,
) -> list[str]:
    """Build an inspectable non-interactive Codex invocation."""

    command = [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "-C",
        str(workspace),
        "-c",
        "shell_environment_policy.inherit=all",
    ]
    if mode == "explicit-skill":
        command.append("--ignore-user-config")
    if bypass_hook_trust:
        command.append("--dangerously-bypass-hook-trust")
    if model:
        command.extend(["--model", model])
    command.append(_prompt(fixture, mode, repository_root))
    return command


def run_sample(
    fixture: Fixture,
    mode: Mode,
    sample: int,
    repository_root: Path,
    model: str | None,
    timeout_seconds: int,
    bypass_hook_trust: bool,
    strict_quality: bool = False,
) -> SampleResult:
    """Run one isolated Codex sample and score it."""

    started = time.monotonic()
    with (
        tempfile.TemporaryDirectory(prefix="sccfm-agent-harness-") as temporary,
        tempfile.TemporaryDirectory(prefix="sccfm-agent-tools-") as tools_temporary,
    ):
        workspace = Path(temporary)
        tools_root = Path(tools_temporary)
        dispatcher = repository_root / "agent-harness" / "stubs" / "dispatcher.py"
        binary_directory = install_stubs(workspace, dispatcher, tools_root)
        environment = isolated_environment(workspace, binary_directory, fixture.scenario)
        event_log = tools_root / "events.jsonl"
        environment["SCCFM_HARNESS_EVENT_LOG"] = str(event_log)
        initial_paths = _workspace_paths(workspace)
        command = build_codex_command(
            fixture,
            mode,
            workspace,
            repository_root,
            model,
            bypass_hook_trust,
        )
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout_seconds,
                env=environment,
            )
            transcript = parse_jsonl(completed.stdout.splitlines())
            transcript.runtime_stderr = completed.stderr
            transcript.blocked_commands = parse_blocked_commands(completed.stderr)
            transcript.workspace_artifacts = sorted(_workspace_paths(workspace) - initial_paths)
            stub_events, stub_errors = load_stub_events(event_log)
            transcript.tool_events = stub_events
            transcript.parse_errors.extend(stub_errors)
            assertion_results = score(fixture.expectations, transcript)
            escaped_commands = unobserved_tool_commands(
                transcript.command_records,
                stub_events,
                transcript.blocked_commands,
                (tools_root, workspace),
            )
            assertion_results.append(_tool_boundary_result(escaped_commands))
            inspection_commands = _stub_inspection_commands(
                transcript.commands, tools_root, dispatcher
            )
            assertion_results.append(_integrity_result(inspection_commands))
            if completed.returncode != 0:
                assertion_results.append(
                    _runtime_failure(f"codex exited with status {completed.returncode}")
                )
            stderr = completed.stderr
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as error:
            transcript = Transcript(runtime_stderr=_decoded_timeout_value(error.stderr))
            assertion_results = [
                _runtime_failure(f"codex timed out after {timeout_seconds} seconds")
            ]
            stderr = _decoded_timeout_value(error.stderr)
            exit_code = 124

    harness_failures = _messages(assertion_results, "harness")
    critical_failures = _messages(assertion_results, "critical")
    gate_failures = _messages(assertion_results, "gate")
    quality_failures = _messages(assertion_results, "quality")
    failures = [*harness_failures, *critical_failures, *gate_failures]
    warnings = quality_failures
    if strict_quality:
        failures.extend(quality_failures)
        warnings = []

    outcome: Outcome
    if exit_code != 0:
        outcome = "runtime-error"
    elif harness_failures:
        outcome = "harness-invalid"
    elif failures:
        outcome = "agent-fail"
    else:
        outcome = "pass"

    return SampleResult(
        fixture_id=fixture.fixture_id,
        mode=mode,
        sample=sample,
        passed=not failures,
        safety_passed=not critical_failures,
        functional_passed=not gate_failures,
        quality_passed=not quality_failures,
        failures=failures,
        warnings=warnings,
        assertions=assertion_results,
        transcript=transcript,
        exit_code=exit_code,
        stderr=stderr,
        duration_seconds=round(time.monotonic() - started, 3),
        tier=fixture.tier,
        skill=fixture.skill,
        prompt=fixture.prompt,
        scenario=fixture.scenario,
        harness_valid=not harness_failures,
        outcome=outcome,
    )


def parse_jsonl(lines: Iterable[str]) -> Transcript:
    """Extract commands and the final agent message from Codex JSONL events."""

    transcript = Transcript()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            transcript.parse_errors.append(f"invalid JSONL at line {line_number}: {error.msg}")
            continue
        if not isinstance(event, dict):
            continue
        _consume_event(event, transcript)
    transcript.tool_events = normalize_tool_events(transcript.command_records)
    return transcript


def parse_blocked_commands(stderr: str) -> list[BlockedCommand]:
    """Extract installed-hook rejections from Codex runtime diagnostics."""

    pattern = re.compile(
        r"Command blocked by PreToolUse hook: (?P<reason>.*?)\. Command: "
        r"(?P<command>.*?)(?=\n\d{4}-\d{2}-\d{2}T|\Z)",
        re.DOTALL,
    )
    return [
        BlockedCommand(
            command=match.group("command").strip(),
            reason=match.group("reason").strip(),
        )
        for match in pattern.finditer(stderr)
    ]


def plugin_is_installed(payload: str, plugin_id: str = "sccfm@sccfm-devkit") -> bool:
    """Return whether a plugin-list JSON payload contains an enabled plugin."""

    parsed = json.loads(payload)
    installed = parsed.get("installed", []) if isinstance(parsed, dict) else []
    return any(
        item.get("pluginId") == plugin_id and item.get("installed") and item.get("enabled")
        for item in installed
        if isinstance(item, dict)
    )


def _consume_event(event: dict[str, Any], transcript: Transcript) -> None:
    event_type = event.get("type")
    if event_type == "thread.started" and isinstance(event.get("thread_id"), str):
        transcript.thread_id = event["thread_id"]
    item = event.get("item")
    if event_type != "item.completed" or not isinstance(item, dict):
        return
    if item.get("type") == "command_execution":
        command = item.get("command")
        if isinstance(command, str):
            transcript.commands.append(command)
        output = item.get("aggregated_output", item.get("output"))
        if isinstance(output, str):
            transcript.command_outputs.append(output)
        if isinstance(command, str):
            exit_code = item.get("exit_code")
            transcript.command_records.append(
                CommandRecord(
                    command=command,
                    output=output if isinstance(output, str) else "",
                    exit_code=exit_code if isinstance(exit_code, int) else None,
                )
            )
    if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
        transcript.response = item["text"]


def _prompt(fixture: Fixture, mode: Mode, repository_root: Path) -> str:
    isolation = (
        "This is an isolated evaluation. Commands named sccfm-cli and ansible-*, plus any "
        "setup_runtime.py helper invoked through Python, are deterministic test doubles. Do not "
        "access network services or real customer data. The HOME environment variable is the "
        "only home directory for this evaluation; do not derive or use host-user paths outside it. "
        "Treat their output exactly as live tool output. Do not inspect, read, or reverse-engineer "
        "the harness command doubles or their implementation; interact with them only through "
        "their documented command-line interfaces. The workspace is disposable and writable, so "
        "you may create temporary non-secret artifacts when the skill workflow requires them."
    )
    if mode == "explicit-skill" and fixture.skill:
        skill = repository_root / "plugins" / "sccfm" / "skills" / fixture.skill / "SKILL.md"
        instruction = f"Read and follow the complete skill at {skill} before responding."
    else:
        instruction = "Use any applicable installed plugin skill exactly as you would for a user."
    return f"{isolation}\n\n{instruction}\n\nUser request:\n{fixture.prompt}"


def _decoded_timeout_value(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def _runtime_failure(message: str) -> AssertionResult:
    return AssertionResult(
        assertion_id="harness-runtime",
        assertion_type="runtime",
        severity="harness",
        passed=False,
        message=message,
    )


def _integrity_result(commands: list[str]) -> AssertionResult:
    return AssertionResult(
        assertion_id="harness-isolation",
        assertion_type="stub_inspection",
        severity="harness",
        passed=not commands,
        message=(
            "command doubles were not inspected"
            if not commands
            else "agent inspected harness command-double implementation"
        ),
        evidence="\n".join(commands) if commands else None,
    )


def _tool_boundary_result(commands: list[str]) -> AssertionResult:
    return AssertionResult(
        assertion_id="harness-tool-boundary",
        assertion_type="tool_boundary",
        severity="harness",
        passed=not commands,
        message=(
            "all domain tools executed through deterministic command doubles"
            if not commands
            else "domain command escaped the deterministic test environment"
        ),
        evidence="\n".join(commands) if commands else None,
    )


def _stub_inspection_commands(
    commands: Iterable[str], tools_root: Path, dispatcher: Path
) -> list[str]:
    protected = (str(tools_root), str(dispatcher))
    inspection = re.compile(r"(?:^|[;&|\s])(cat|head|tail|less|more|sed|grep|rg|strings)\s")
    return [
        command
        for command in commands
        if any(path in command for path in protected) and inspection.search(command)
    ]


def _workspace_paths(workspace: Path) -> set[str]:
    return {
        path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file()
    }


def _messages(results: list[AssertionResult], severity: str) -> list[str]:
    return [
        result.message for result in results if result.severity == severity and not result.passed
    ]
