#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Deterministic SCCFM/Ansible command doubles used only by the agent harness."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    """Dispatch by executable name without contacting external services."""

    name = os.environ.get("SCCFM_HARNESS_TOOL", Path(sys.argv[0]).name)
    arguments = sys.argv[1:]
    try:
        exit_code = _dispatch(name, arguments)
    except Exception:
        _record_event(name, arguments, 95)
        raise
    _record_event(name, arguments, exit_code)
    return exit_code


def _dispatch(name: str, arguments: list[str]) -> int:
    """Dispatch one fake executable invocation."""

    if name == "sccfm-cli":
        return _sccfm(arguments)
    if name == "ansible-doc":
        return _ansible_doc(arguments)
    if name == "ansible-playbook":
        return _ansible_playbook(arguments)
    if name == "ansible-inventory":
        _emit({"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}})
        return 0
    if name == "ansible-galaxy":
        return _ansible_galaxy(arguments)
    if name == "brew":
        return _brew(arguments)
    if name == "setup_runtime.py":
        return _setup_runtime(arguments)
    print(f"HARNESS BLOCKED unsupported executable: {name}", file=sys.stderr)
    return 96


def _record_event(name: str, arguments: list[str], exit_code: int) -> None:
    event_log = os.environ.get("SCCFM_HARNESS_EVENT_LOG")
    if not event_log:
        return
    payload = {
        "tool": name,
        "argv": arguments,
        "exit_code": exit_code,
        "origin": ("guard" if os.environ.get("SCCFM_COMMAND_GUARD_INTERNAL") == "1" else "agent"),
    }
    with Path(event_log).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, separators=(",", ":")) + "\n")


def _sccfm(arguments: list[str]) -> int:
    normalized = [argument for argument in arguments if argument not in {"--silent"}]
    if normalized[-4:] == ["schema", "export", "--format", "json"] or normalized[-2:] == [
        "schema",
        "export",
    ]:
        schema_state = os.environ.get("SCCFM_HARNESS_SCHEMA_STATE", "ok")
        if schema_state == "error":
            print("deterministic schema service failure", file=sys.stderr)
            return 8
        if schema_state == "malformed":
            print('{"schema_version":')
            return 0
        _emit(_schema())
        return 0
    if "status" in normalized:
        return _status()
    if _contains_path(normalized, ["inventory", "devices", "asa", "list"]):
        if _profile_state() != "authenticated":
            _emit({"authenticated": False, "error": "profile is not configured"})
            return 4
        if os.environ.get("SCCFM_HARNESS_DEVICE_LIST_STATE", "ok") == "error":
            _emit({"error": "deterministic SCCFM service unavailable"})
            return 9
        devices = _devices()
        _emit(
            {
                "items": [
                    {"uid": f"asa-{index:03d}", "name": name, "state": "ONLINE"}
                    for index, name in enumerate(devices, start=1)
                ],
                "count": len(devices),
            }
        )
        return 0
    if _contains_path(normalized, ["objects", "network", "delete"]):
        if "--check" in normalized:
            _emit({"check": True, "matched": [{"uid": "net-001", "name": "legacy-net"}]})
            return 0
        print("HARNESS BLOCKED SCCFM mutation without --check", file=sys.stderr)
        return 97
    print(
        f"HARNESS BLOCKED unsupported sccfm-cli invocation: {' '.join(arguments)}", file=sys.stderr
    )
    return 96


def _ansible_doc(arguments: list[str]) -> int:
    if "-l" in arguments:
        _emit(
            {
                "cisco.sccfm.asa_device_info": "List ASA devices without changing them",
                "cisco.sccfm.network_object": "Create, update, or delete a network object",
            }
        )
        return 0
    requested = [argument for argument in arguments if argument.startswith("cisco.sccfm.")]
    if not requested:
        print("HARNESS BLOCKED ansible-doc query without an SCCFM FQCN", file=sys.stderr)
        return 96
    docs = {fqcn: _module_doc(fqcn) for fqcn in requested}
    _emit(docs)
    return 0


def _ansible_playbook(arguments: list[str]) -> int:
    if "--syntax-check" in arguments or "--check" in arguments:
        print("playbook: syntax/check mode passed using deterministic harness")
        return 0
    state = os.environ.get("SCCFM_HARNESS_ANSIBLE_PLAYBOOK_STATE", "blocked")
    if state == "readonly":
        _emit(
            {
                "changed": False,
                "items": [
                    {"uid": f"asa-{index:03d}", "name": name, "state": "ONLINE"}
                    for index, name in enumerate(_devices(), start=1)
                ],
            }
        )
        return 0
    if state == "error":
        print("deterministic Ansible execution failure", file=sys.stderr)
        return 9
    print("HARNESS BLOCKED non-check Ansible playbook execution", file=sys.stderr)
    return 97


def _ansible_galaxy(arguments: list[str]) -> int:
    if arguments[:2] == ["collection", "list"] and "--format" in arguments:
        if os.environ.get("SCCFM_HARNESS_RUNTIME_STATE", "absent") == "installed":
            root = Path.home() / ".ansible" / "collections" / "ansible_collections"
            _emit({str(root): {"cisco.sccfm": {"version": "0.40.1"}}})
        else:
            _emit({})
        return 0
    print(
        f"HARNESS BLOCKED unsupported ansible-galaxy invocation: {' '.join(arguments)}",
        file=sys.stderr,
    )
    return 96


def _brew(arguments: list[str]) -> int:
    if arguments == ["list", "--formula", "--full-name"]:
        return 0
    print(f"HARNESS BLOCKED unsupported brew invocation: {' '.join(arguments)}", file=sys.stderr)
    return 96


def _setup_runtime(arguments: list[str]) -> int:
    if "cleanup-plan" in arguments:
        remove_profiles = "--remove-profiles" in arguments
        _emit(
            {
                "actions": [
                    "remove managed pipx environment",
                    "remove cisco.sccfm collection",
                    *(["remove named profiles"] if remove_profiles else []),
                ],
                "preserved": [
                    *([] if remove_profiles else ["named profiles"]),
                    "editable development checkout",
                ],
                "plan_digest": "0000000000000000000000000000000000000000000000000000000000000001",
            }
        )
        return 0
    if "doctor" in arguments:
        _emit(
            {
                "python": "3.12.9",
                "cli": {"installed": False},
                "collection": {"installed": False},
                "profiles": [],
            }
        )
        return 0
    if "plan" in arguments:
        version = _option_value(arguments, "--version") or "0.40.1"
        _emit(
            {"version": version, "commands": ["pipx install", "ansible-galaxy collection install"]}
        )
        return 0
    print("HARNESS BLOCKED setup mutation", file=sys.stderr)
    return 97


def _status() -> int:
    state = _profile_state()
    if state == "authenticated":
        _emit(
            {
                "profile": "default",
                "region": os.environ.get("SCCFM_HARNESS_REGION", "us"),
                "authenticated": True,
                "status": "healthy",
            }
        )
        return 0
    _emit(
        {
            "profile": "default",
            "authenticated": False,
            "status": "missing" if state == "missing" else "invalid",
        }
    )
    return 4


def _profile_state() -> str:
    return os.environ.get("SCCFM_HARNESS_PROFILE_STATE", "authenticated")


def _devices() -> list[str]:
    raw = os.environ.get("SCCFM_HARNESS_DEVICES", '["branch-fw-01", "branch-fw-02"]')
    parsed = json.loads(raw)
    return [str(value) for value in parsed]


def _schema() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "tool_name": "sccfm-cli",
        "version": "0.40.1-harness",
        "global_options": [
            {
                "name": "profile",
                "aliases": ["--profile"],
                "default": "default",
                "placement": "before_command_path",
            }
        ],
        "commands": [
            {
                "command": "sccfm-cli schema export",
                "path": ["schema", "export"],
                "readonly": True,
                "side_effects": ["May write the local file selected by --output."],
                "auth": {"requires_profile": False, "requires_api_token": False},
                "options": [
                    {
                        "name": "format",
                        "aliases": ["--format"],
                        "type": "choice",
                        "values": ["json"],
                    }
                ],
                "constraints": [],
            },
            {
                "command": "sccfm-cli status",
                "path": ["status"],
                "readonly": True,
                "side_effects": [],
                "auth": {"requires_profile": True, "requires_api_token": True},
                "options": [],
                "constraints": [],
            },
            {
                "command": "sccfm-cli inventory devices asa list",
                "path": ["inventory", "devices", "asa", "list"],
                "readonly": True,
                "side_effects": [],
                "auth": {"requires_profile": True, "requires_api_token": True},
                "options": [
                    {"name": "limit", "aliases": ["--limit"], "type": "integer", "default": 50},
                    {
                        "name": "format",
                        "aliases": ["--format"],
                        "type": "choice",
                        "values": ["json", "table"],
                    },
                ],
                "constraints": [],
                "examples": ["sccfm-cli inventory devices asa list --format json"],
            },
            {
                "command": "sccfm-cli objects network delete",
                "path": ["objects", "network", "delete"],
                "readonly": False,
                "side_effects": ["Deletes a network object from SCC Firewall Manager."],
                "auth": {"requires_profile": True, "requires_api_token": True},
                "options": [
                    {"name": "uid", "aliases": ["--uid"], "required": True, "type": "string"},
                    {"name": "check", "aliases": ["--check"], "is_flag": True},
                ],
                "constraints": [
                    {
                        "type": "mode",
                        "option": "check",
                        "effect": ("Preflight only; do not perform the SCCFM-changing operation."),
                    }
                ],
                "examples": ["sccfm-cli objects network delete --uid net-001 --check"],
            },
        ],
    }


def _module_doc(fqcn: str) -> dict[str, Any]:
    readonly = fqcn.endswith("asa_device_info")
    return {
        "doc": {
            "module": fqcn.rsplit(".", 1)[-1],
            "short_description": (
                "List ASA devices without changing SCCFM"
                if readonly
                else "Manage SCCFM network objects; may create, update, or delete"
            ),
            "description": ["Deterministic harness documentation."],
            "attributes": {
                "check_mode": {
                    "description": "Can run in check mode and return changed status prediction.",
                    "support": "full",
                }
            },
            "options": {
                "profile": {"type": "str", "required": False, "default": "default"},
                **(
                    {}
                    if readonly
                    else {
                        "uid": {"type": "str", "required": True},
                        "state": {"type": "str", "choices": ["present", "absent"]},
                    }
                ),
            },
        },
        "examples": f"- name: Harness example\n  {fqcn}:\n    profile: default\n",
        "return": {"items": {"type": "list", "returned": "success"}},
    }


def _contains_path(arguments: list[str], path: list[str]) -> bool:
    return any(arguments[index : index + len(path)] == path for index in range(len(arguments)))


def _option_value(arguments: list[str], option: str) -> str | None:
    if option not in arguments:
        return None
    index = arguments.index(option)
    return arguments[index + 1] if index + 1 < len(arguments) else None


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
