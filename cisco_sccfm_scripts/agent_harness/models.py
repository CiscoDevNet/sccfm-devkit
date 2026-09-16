# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Data models shared by the SCCFM agent harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Agent = Literal["codex", "claude", "bedrock"]
Mode = Literal["explicit-skill", "installed-plugin"]
Tier = Literal["required", "aspirational"]
Severity = Literal["critical", "gate", "quality", "harness"]
ProfileState = Literal["authenticated", "missing", "invalid"]
SchemaState = Literal["ok", "error", "malformed"]
DeviceListState = Literal["ok", "error"]
AnsiblePlaybookState = Literal["blocked", "readonly", "error"]
RuntimeState = Literal["absent", "installed"]
AnsibleRuntimeLayout = Literal["path", "companion"]
Outcome = Literal["pass", "agent-fail", "harness-invalid", "runtime-error"]
AssertionType = Literal[
    "operation_called",
    "operation_not_called",
    "response_pattern",
    "response_concepts",
    "response_operation_confirmation",
    "blocked_command_confirmation",
    "secret_absent",
    "max_tool_calls",
    "max_operation_calls",
    "artifact_pattern_absent",
]


@dataclass(frozen=True)
class Scenario:
    """Deterministic SCCFM state exposed by command doubles."""

    profile_state: ProfileState = "authenticated"
    region: str = "us"
    devices: tuple[str, ...] = ("branch-fw-01", "branch-fw-02")
    schema_state: SchemaState = "ok"
    device_list_state: DeviceListState = "ok"
    ansible_playbook_state: AnsiblePlaybookState = "blocked"
    runtime_state: RuntimeState = "absent"
    ansible_runtime_layout: AnsibleRuntimeLayout = "path"


@dataclass(frozen=True)
class Assertion:
    """One typed expectation over tool evidence or the final response."""

    assertion_id: str
    assertion_type: AssertionType
    severity: Severity
    operation: str | None = None
    argv_pattern: str | None = None
    pattern: str | None = None
    concepts: tuple[tuple[str, ...], ...] = ()
    value: str | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class Expectations:
    """Typed checks applied to one Codex transcript."""

    assertions: tuple[Assertion, ...] = ()


@dataclass(frozen=True)
class Fixture:
    """One user scenario and its expected behavior."""

    fixture_id: str
    tier: Tier
    skill: str | None
    prompt: str
    expectations: Expectations
    source: Path
    scenario: Scenario = Scenario()
    modes: tuple[Mode, ...] = ("explicit-skill", "installed-plugin")


@dataclass(frozen=True)
class CommandRecord:
    """One completed command execution reported by Codex."""

    command: str
    output: str
    exit_code: int | None


@dataclass(frozen=True)
class ToolEvent:
    """Normalized invocation inferred from a completed command record."""

    tool: str
    operation: str
    argv: tuple[str, ...]
    classification: str
    command: str
    output: str
    exit_code: int | None
    origin: str = "agent"


@dataclass(frozen=True)
class BlockedCommand:
    """One command rejected by an installed plugin hook."""

    command: str
    reason: str


@dataclass
class Transcript:
    """Relevant output extracted from a Codex JSONL run."""

    commands: list[str] = field(default_factory=list)
    command_outputs: list[str] = field(default_factory=list)
    command_records: list[CommandRecord] = field(default_factory=list)
    tool_events: list[ToolEvent] = field(default_factory=list)
    blocked_commands: list[BlockedCommand] = field(default_factory=list)
    workspace_artifacts: list[str] = field(default_factory=list)
    # Text of the files the agent generated, used for secret scanning only. A
    # generated file can hold the very secret the scan looks for, so this is
    # cleared once scoring finishes and never reaches a report.
    artifact_contents: list[str] = field(default_factory=list)
    response: str = ""
    runtime_stderr: str = ""
    thread_id: str | None = None
    parse_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AssertionResult:
    """Evidence-backed result for one typed assertion."""

    assertion_id: str
    assertion_type: str
    severity: Severity
    passed: bool
    message: str
    evidence: str | None = None


@dataclass
class SampleResult:
    """Result of one fixture sample."""

    fixture_id: str
    mode: Mode
    sample: int
    passed: bool
    safety_passed: bool
    functional_passed: bool
    quality_passed: bool
    failures: list[str]
    warnings: list[str]
    assertions: list[AssertionResult]
    transcript: Transcript
    exit_code: int
    stderr: str
    duration_seconds: float
    agent: Agent = "codex"
    tier: Tier | None = None
    skill: str | None = None
    prompt: str = ""
    scenario: Scenario | None = None
    harness_valid: bool = True
    outcome: Outcome = "pass"
    runtime_attempts: int = 1
    prior_runtime_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)
