# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create deterministic command doubles for isolated agent runs."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from .models import Scenario

STUB_NAMES = (
    "sccfm-cli",
    "ansible-doc",
    "ansible-playbook",
    "ansible-inventory",
    "ansible-galaxy",
    "brew",
    "pipx",
)
ANSIBLE_STUB_NAMES = (
    "ansible-doc",
    "ansible-playbook",
    "ansible-inventory",
    "ansible-galaxy",
)
PYTHON_WRAPPER_NAMES = ("python3", "python3.12")


def install_stubs(workspace: Path, dispatcher: Path, tools_root: Path | None = None) -> Path:
    """Install executable copies of the dispatcher and a fake setup helper."""

    binary_directory = (tools_root or workspace) / "bin"
    binary_directory.mkdir(parents=True)
    for name in STUB_NAMES:
        target = binary_directory / name
        shutil.copy2(dispatcher, target)
        target.chmod(0o755)

    wrapper = (
        "#!/bin/sh\n"
        'if [ "$#" -gt 0 ] && [ "${1##*/}" = "setup_runtime.py" ]; then\n'
        "  shift\n"
        '  SCCFM_HARNESS_TOOL=setup_runtime.py exec "$SCCFM_HARNESS_REAL_PYTHON" '
        '"$SCCFM_HARNESS_DISPATCHER" "$@"\n'
        "fi\n"
        'exec "$SCCFM_HARNESS_REAL_PYTHON" "$@"\n'
    )
    for name in PYTHON_WRAPPER_NAMES:
        target = binary_directory / name
        target.write_text(wrapper, encoding="utf-8")
        target.chmod(0o755)

    scripts_directory = workspace / "scripts"
    scripts_directory.mkdir()
    setup_helper = scripts_directory / "setup_runtime.py"
    setup_helper.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import runpy\n"
        "os.environ['SCCFM_HARNESS_TOOL'] = 'setup_runtime.py'\n"
        "runpy.run_path(os.environ['SCCFM_HARNESS_DISPATCHER'], run_name='__main__')\n",
        encoding="utf-8",
    )
    setup_helper.chmod(0o755)
    return binary_directory


def isolated_environment(
    workspace: Path, binary_directory: Path, scenario: Scenario
) -> dict[str, str]:
    """Build an environment without customer credentials or the real user home."""

    blocked_prefixes = ("SCCFM_", "AWS_", "ANSIBLE_", "CDO_")
    blocked_names = {"GH_TOKEN", "GITHUB_TOKEN"}
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in blocked_names and not key.startswith(blocked_prefixes)
    }
    real_home = Path.home()
    home = workspace / "home"
    home.mkdir(exist_ok=True)
    path_override = f"export PATH={shlex.quote(str(binary_directory))}:$PATH\n"
    for profile_name in (".profile", ".zprofile"):
        (home / profile_name).write_text(path_override, encoding="utf-8")
    if scenario.runtime_state == "installed":
        collection = home / ".ansible" / "collections" / "ansible_collections" / "cisco" / "sccfm"
        collection.mkdir(parents=True)
    if scenario.ansible_runtime_layout == "companion":
        companion = home / ".sccfm-agent-plugin" / "ansible-runtime" / "bin"
        companion.mkdir(parents=True)
        for name in ANSIBLE_STUB_NAMES:
            target = companion / name
            shutil.copy2(binary_directory / name, target)
            target.chmod(0o755)
    environment["HOME"] = str(home)
    environment["ZDOTDIR"] = str(home)
    environment["CODEX_HOME"] = os.environ.get("CODEX_HOME", str(real_home / ".codex"))
    environment["PATH"] = f"{binary_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["NO_COLOR"] = "1"
    environment["SCCFM_HARNESS"] = "1"
    environment["SCCFM_HARNESS_REAL_PYTHON"] = sys.executable
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["SCCFM_HARNESS_DISPATCHER"] = str(
        Path(__file__).resolve().parents[2] / "agent-harness" / "stubs" / "dispatcher.py"
    )
    environment["SCCFM_HARNESS_EVENT_LOG"] = str(workspace / ".harness-events.jsonl")
    environment["SCCFM_HARNESS_PROFILE_STATE"] = scenario.profile_state
    environment["SCCFM_HARNESS_REGION"] = scenario.region
    environment["SCCFM_HARNESS_DEVICES"] = json.dumps(scenario.devices)
    environment["SCCFM_HARNESS_SCHEMA_STATE"] = scenario.schema_state
    environment["SCCFM_HARNESS_DEVICE_LIST_STATE"] = scenario.device_list_state
    environment["SCCFM_HARNESS_ANSIBLE_PLAYBOOK_STATE"] = scenario.ansible_playbook_state
    environment["SCCFM_HARNESS_RUNTIME_STATE"] = scenario.runtime_state
    return environment
