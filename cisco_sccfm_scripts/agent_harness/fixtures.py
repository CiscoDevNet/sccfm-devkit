# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Fixture loading and static validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from .models import (
    AnsiblePlaybookState,
    AnsibleRuntimeLayout,
    Assertion,
    AssertionType,
    DeviceListState,
    Expectations,
    Fixture,
    Mode,
    ProfileConfigurationState,
    ProfileState,
    RuntimeState,
    Scenario,
    SchemaState,
    Severity,
    Tier,
)

VALID_MODES = {"explicit-skill", "installed-plugin"}
VALID_TIERS = {"required", "aspirational"}
VALID_SKILLS = {"sccfm-cli", "sccfm-ansible", "sccfm-setup", "sccfm-uninstall"}
VALID_SEVERITIES = {"critical", "gate", "quality"}
VALID_PROFILE_STATES = {"authenticated", "missing", "invalid"}
VALID_PROFILE_CONFIGURATION_STATES = {"absent", "present"}
VALID_SCHEMA_STATES = {"ok", "error", "malformed"}
VALID_DEVICE_LIST_STATES = {"ok", "error"}
VALID_ANSIBLE_PLAYBOOK_STATES = {"blocked", "readonly", "error"}
VALID_RUNTIME_STATES = {"absent", "installed"}
VALID_ANSIBLE_RUNTIME_LAYOUTS = {"path", "companion"}
VALID_ASSERTION_TYPES = {
    "operation_called",
    "operation_not_called",
    "response_pattern",
    "response_concepts",
    "response_commands_supported",
    "response_operation_confirmation",
    "blocked_command_confirmation",
    "secret_absent",
    "max_tool_calls",
    "max_operation_calls",
    "artifact_pattern_absent",
}


def load_fixtures(directory: Path) -> list[Fixture]:
    """Load and validate every JSON fixture in a directory."""

    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValueError(f"no fixture files found in {directory}")
    fixtures = [_load_fixture(path) for path in paths]
    identifiers = [fixture.fixture_id for fixture in fixtures]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("fixture ids must be unique")
    return fixtures


def _load_fixture(path: Path) -> Fixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: fixture must be a JSON object")
    _require_keys(raw, {"schema_version", "id", "tier", "skill", "prompt", "expect"}, path)
    if raw["schema_version"] != 2:
        raise ValueError(f"{path}: unsupported schema_version; expected 2")

    fixture_id = _nonempty_string(raw["id"], path, "id")
    tier_text = _nonempty_string(raw["tier"], path, "tier")
    if tier_text not in VALID_TIERS:
        raise ValueError(f"{path}: invalid tier {tier_text!r}")
    skill_value = raw["skill"]
    if skill_value is not None and skill_value not in VALID_SKILLS:
        raise ValueError(f"{path}: invalid skill {skill_value!r}")
    prompt = _nonempty_string(raw["prompt"], path, "prompt")

    raw_modes = raw.get("modes", sorted(VALID_MODES))
    if not isinstance(raw_modes, list) or not raw_modes:
        raise ValueError(f"{path}: modes must be a non-empty list")
    if any(mode not in VALID_MODES for mode in raw_modes):
        raise ValueError(f"{path}: invalid mode")

    return Fixture(
        fixture_id=fixture_id,
        tier=cast(Tier, tier_text),
        skill=cast(str | None, skill_value),
        prompt=prompt,
        expectations=Expectations(assertions=_load_assertions(raw["expect"], path)),
        source=path,
        scenario=_load_scenario(raw.get("scenario", {}), path),
        modes=cast(tuple[Mode, ...], tuple(raw_modes)),
    )


def _load_scenario(raw: object, path: Path) -> Scenario:
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: scenario must be an object")
    profile_state = raw.get("profile_state", "authenticated")
    if profile_state not in VALID_PROFILE_STATES:
        raise ValueError(f"{path}: invalid scenario.profile_state")
    profile_configuration_state = raw.get("profile_configuration_state", "absent")
    if profile_configuration_state not in VALID_PROFILE_CONFIGURATION_STATES:
        raise ValueError(f"{path}: invalid scenario.profile_configuration_state")
    region = _nonempty_string(raw.get("region", "us"), path, "scenario.region")
    devices = raw.get("devices", ["branch-fw-01", "branch-fw-02"])
    if not isinstance(devices, list) or not all(
        isinstance(device, str) and device for device in devices
    ):
        raise ValueError(f"{path}: scenario.devices must be a string list")
    schema_state = raw.get("schema_state", "ok")
    if schema_state not in VALID_SCHEMA_STATES:
        raise ValueError(f"{path}: invalid scenario.schema_state")
    device_list_state = raw.get("device_list_state", "ok")
    if device_list_state not in VALID_DEVICE_LIST_STATES:
        raise ValueError(f"{path}: invalid scenario.device_list_state")
    ansible_playbook_state = raw.get("ansible_playbook_state", "blocked")
    if ansible_playbook_state not in VALID_ANSIBLE_PLAYBOOK_STATES:
        raise ValueError(f"{path}: invalid scenario.ansible_playbook_state")
    runtime_state = raw.get("runtime_state", "absent")
    if runtime_state not in VALID_RUNTIME_STATES:
        raise ValueError(f"{path}: invalid scenario.runtime_state")
    ansible_runtime_layout = raw.get("ansible_runtime_layout", "path")
    if ansible_runtime_layout not in VALID_ANSIBLE_RUNTIME_LAYOUTS:
        raise ValueError(f"{path}: invalid scenario.ansible_runtime_layout")
    return Scenario(
        profile_state=cast(ProfileState, profile_state),
        profile_configuration_state=cast(ProfileConfigurationState, profile_configuration_state),
        region=region,
        devices=tuple(devices),
        schema_state=cast(SchemaState, schema_state),
        device_list_state=cast(DeviceListState, device_list_state),
        ansible_playbook_state=cast(AnsiblePlaybookState, ansible_playbook_state),
        runtime_state=cast(RuntimeState, runtime_state),
        ansible_runtime_layout=cast(AnsibleRuntimeLayout, ansible_runtime_layout),
    )


def _load_assertions(raw: object, path: Path) -> tuple[Assertion, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: expect must be a non-empty assertion list")
    assertions = tuple(_load_assertion(item, path, index) for index, item in enumerate(raw))
    identifiers = [assertion.assertion_id for assertion in assertions]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{path}: assertion ids must be unique")
    return assertions


def _load_assertion(raw: object, path: Path, index: int) -> Assertion:
    prefix = f"expect[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: {prefix} must be an object")
    assertion_id = _nonempty_string(raw.get("id"), path, f"{prefix}.id")
    assertion_type = _nonempty_string(raw.get("type"), path, f"{prefix}.type")
    severity = _nonempty_string(raw.get("severity"), path, f"{prefix}.severity")
    if assertion_type not in VALID_ASSERTION_TYPES:
        raise ValueError(f"{path}: invalid {prefix}.type {assertion_type!r}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"{path}: invalid {prefix}.severity {severity!r}")

    operation = _optional_string(raw.get("operation"), path, f"{prefix}.operation")
    argv_pattern = _optional_regex(raw.get("argv_pattern"), path, f"{prefix}.argv_pattern")
    pattern = _optional_regex(raw.get("pattern"), path, f"{prefix}.pattern")
    value = _optional_string(raw.get("value"), path, f"{prefix}.value")
    maximum = raw.get("maximum")
    concepts = _load_concepts(raw.get("concepts", []), path, prefix)

    if (
        assertion_type
        in {
            "operation_called",
            "operation_not_called",
            "max_operation_calls",
            "response_operation_confirmation",
            "blocked_command_confirmation",
        }
        and operation is None
    ):
        raise ValueError(f"{path}: {prefix}.operation is required")
    if assertion_type == "response_pattern" and pattern is None:
        raise ValueError(f"{path}: {prefix}.pattern is required")
    if assertion_type == "artifact_pattern_absent" and pattern is None:
        raise ValueError(f"{path}: {prefix}.pattern is required")
    if assertion_type == "response_concepts" and not concepts:
        raise ValueError(f"{path}: {prefix}.concepts is required")
    if assertion_type == "secret_absent" and value is None:
        raise ValueError(f"{path}: {prefix}.value is required")
    if assertion_type in {"max_tool_calls", "max_operation_calls"} and (
        not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0
    ):
        raise ValueError(f"{path}: {prefix}.maximum must be a non-negative integer")

    return Assertion(
        assertion_id=assertion_id,
        assertion_type=cast(AssertionType, assertion_type),
        severity=cast(Severity, severity),
        operation=operation,
        argv_pattern=argv_pattern,
        pattern=pattern,
        concepts=concepts,
        value=value,
        maximum=cast(int | None, maximum),
    )


def _load_concepts(raw: object, path: Path, prefix: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{path}: {prefix}.concepts must be a list")
    result = []
    for group_index, group in enumerate(raw):
        if (
            not isinstance(group, list)
            or not group
            or not all(isinstance(value, str) and value for value in group)
        ):
            raise ValueError(
                f"{path}: {prefix}.concepts[{group_index}] must be a non-empty string list"
            )
        for value in group:
            _compile_regex(value, path, f"{prefix}.concepts[{group_index}]")
        result.append(tuple(group))
    return tuple(result)


def _optional_regex(value: object, path: Path, field_name: str) -> str | None:
    result = _optional_string(value, path, field_name)
    if result is not None:
        _compile_regex(result, path, field_name)
    return result


def _compile_regex(value: str, path: Path, field_name: str) -> None:
    try:
        re.compile(value)
    except re.error as error:
        raise ValueError(f"{path}: invalid regex in {field_name}: {error}") from error


def _require_keys(raw: dict[str, Any], expected: set[str], path: Path) -> None:
    missing = expected - raw.keys()
    if missing:
        raise ValueError(f"{path}: missing keys: {', '.join(sorted(missing))}")


def _optional_string(value: object, path: Path, field_name: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, path, field_name)


def _nonempty_string(value: object, path: Path, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: {field_name} must be a non-empty string")
    return value
