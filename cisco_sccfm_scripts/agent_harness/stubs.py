# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create deterministic command doubles for isolated agent runs."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

from .credentials import (
    CODEX_CREDENTIAL_VARIABLES,
    CREDENTIAL_NAMES_VARIABLE,
    CREDENTIAL_VARIABLES,
    SCRUB_VARIABLE,
    preserved_credential_names,
    provider_environment,
)
from .models import Agent, Scenario

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
PYTHON_NAME_PATTERN = re.compile(r"python3?(\.\d+)?")


def _python_wrapper_names() -> tuple[str, ...]:
    """Names of every Python interpreter reachable on the real PATH.

    Hardcoding a couple of interpreter names left later PATH entries able to
    resolve an agent's ``python3.11``/``python3.13``/etc call to the real,
    unstubbed interpreter instead of the deterministic double.
    """

    names = {"python", "python3", f"python3.{sys.version_info.minor}"}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for entry in entries:
            if PYTHON_NAME_PATTERN.fullmatch(entry) and os.access(Path(directory) / entry, os.X_OK):
                names.add(entry)
    return tuple(sorted(names))


def install_stubs(workspace: Path, dispatcher: Path, tools_root: Path | None = None) -> Path:
    """Install executable copies of the dispatcher and a fake setup helper."""

    binary_directory = (tools_root or workspace) / "bin"
    binary_directory.mkdir(parents=True)
    for name in STUB_NAMES:
        target = binary_directory / name
        # copy2 preserves SELinux xattrs from a Jenkins checkout. Those labels
        # can prevent a bind-mounted script from executing in the tool container
        # even after Docker privately relabels the mount, so copy content only.
        shutil.copyfile(dispatcher, target)
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
    for name in _python_wrapper_names():
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
    workspace: Path,
    binary_directory: Path,
    scenario: Scenario,
    agent: Agent = "codex",
) -> dict[str, str]:
    """Build an environment without customer credentials or the real user home.

    Claude authenticates the parent session from the environment for Bedrock,
    Vertex, Foundry, and API-key setups, so that agent keeps its provider
    variables and relies on ``CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`` to remove them
    from every Bash command, hook, and stdio MCP server it spawns. Codex has no
    equivalent scrub, so its environment stays fully credential free.
    """

    blocked_prefixes = ("SCCFM_", "AWS_", "ANSIBLE_", "ANTHROPIC_", "CDO_")
    blocked_names = {
        "CLAUDE_CODE_USE_BEDROCK",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        *CODEX_CREDENTIAL_VARIABLES,
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in blocked_names and not key.startswith(blocked_prefixes)
    }
    if agent == "claude":
        environment.update(provider_environment(dict(os.environ)))
        environment[SCRUB_VARIABLE] = "1"
        environment[CREDENTIAL_NAMES_VARIABLE] = " ".join(preserved_credential_names())
    elif agent == "bedrock":
        # Bedrock authentication remains in the parent Python process. Tool calls
        # run in a separate network-disabled container and receive only this
        # credential-name list so the doubles can prove no provider value leaked.
        environment[CREDENTIAL_NAMES_VARIABLE] = " ".join(CREDENTIAL_VARIABLES)
    else:
        environment[CREDENTIAL_NAMES_VARIABLE] = " ".join(CODEX_CREDENTIAL_VARIABLES)
    real_home = Path.home()
    home = workspace / "home"
    home.mkdir(exist_ok=True)
    path_override = f"export PATH={shlex.quote(str(binary_directory))}:$PATH\n"
    # zsh reads .zshenv on every invocation, so the disposable ZDOTDIR needs it
    # too; otherwise the host startup files would re-export scrubbed credentials.
    for profile_name in (".profile", ".zprofile", ".zshenv"):
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
