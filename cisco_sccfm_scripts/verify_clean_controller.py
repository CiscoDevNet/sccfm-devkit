# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Smoke-test the public wheel and collection on an isolated Ubuntu controller."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path

from cisco_sccfm_scripts.verify_ansible_collection import verify_collection_artifact
from cisco_sccfm_scripts.verify_python_artifacts import verify_python_wheel

_ANSIBLE_CORE = "ansible-core>=2.20,<2.22"
_TOKEN_ERROR = "api_token is required."
_EXPECTED_MODULES = 49
_EXPECTED_INVENTORY_PLUGINS = 1


class CleanControllerVerificationError(RuntimeError):
    """Raised when the clean-controller smoke test fails."""


@dataclass(frozen=True)
class _Controller:
    work: Path
    collections: Path
    binaries: Path
    environment: dict[str, str]


def _run(
    controller: _Controller,
    command: list[str | Path],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    rendered = [str(part) for part in command]
    result = subprocess.run(
        rendered,
        cwd=controller.work,
        env=controller.environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise CleanControllerVerificationError(
            f"{Path(rendered[0]).name} failed ({result.returncode}): "
            f"{result.stderr or result.stdout}"
        )
    return result


def _create_controller(workspace: Path) -> _Controller:
    work = workspace / "work"
    collections = workspace / "collections"
    venv_root = workspace / "venv"
    work.mkdir()
    venv.EnvBuilder(with_pip=True).create(venv_root)
    binaries = venv_root / "bin"

    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith(("ANSIBLE_", "SCCFM_")) or name in {
            "POETRY_ACTIVE",
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONUSERBASE",
            "VIRTUAL_ENV",
        }:
            environment.pop(name)
    isolated_dirs = {
        "HOME": "home",
        "XDG_CACHE_HOME": "xdg-cache",
        "XDG_CONFIG_HOME": "xdg-config",
        "XDG_DATA_HOME": "xdg-data",
        "XDG_STATE_HOME": "xdg-state",
        "ANSIBLE_LOCAL_TEMP": "ansible-tmp",
    }
    for variable, name in isolated_dirs.items():
        directory = workspace / name
        directory.mkdir()
        environment[variable] = str(directory)
    environment.update(
        {
            "ANSIBLE_COLLECTIONS_PATH": str(collections),
            "PATH": f"{binaries}{os.pathsep}{environment.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return _Controller(work, collections, binaries, environment)


def _discovered_plugins(raw: str, plugin_type: str) -> dict[str, str]:
    try:
        payload: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CleanControllerVerificationError(f"invalid {plugin_type} discovery JSON") from exc
    if not isinstance(payload, dict) or not payload:
        raise CleanControllerVerificationError(f"no cisco.sccfm {plugin_type} plugins discovered")
    if any(
        not isinstance(name, str)
        or not name.startswith("cisco.sccfm.")
        or not isinstance(description, str)
        for name, description in payload.items()
    ):
        raise CleanControllerVerificationError(f"unexpected {plugin_type} discovery result")
    return {str(name): str(payload[name]) for name in sorted(payload)}


def _documented_probe(controller: _Controller, modules: dict[str, str]) -> str:
    candidates = [
        name for name, description in modules.items() if description.casefold().startswith("list ")
    ]
    if not candidates:
        raise CleanControllerVerificationError("no readonly list module discovered")
    probe = candidates[0]
    raw = _run(controller, [controller.binaries / "ansible-doc", "-j", probe]).stdout
    payload: object = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {probe}:
        raise CleanControllerVerificationError("selected module documentation is missing")
    module = payload[probe]
    doc = module.get("doc") if isinstance(module, dict) else None
    options = doc.get("options") if isinstance(doc, dict) else None
    if not isinstance(options, dict) or any(
        isinstance(option, dict) and option.get("required") is True for option in options.values()
    ):
        raise CleanControllerVerificationError("offline probe has required business parameters")
    return probe


def _install_controller_and_collection(
    controller: _Controller,
    collection: Path,
) -> None:
    python = controller.binaries / "python"
    _run(controller, [python, "-I", "-m", "pip", "install", "--no-cache-dir", _ANSIBLE_CORE])
    _run(
        controller,
        [
            controller.binaries / "ansible-galaxy",
            "collection",
            "install",
            collection,
            "-p",
            controller.collections,
            "-f",
        ],
    )


def _verify_missing_devkit_dependency(
    controller: _Controller,
    expected_version: str,
) -> None:
    """Require modules to emit one actionable failure without the paired wheel."""
    probes = {
        "list_asa_not_on_version": 'version: "9.20(3)13"',
        "list_ftd_not_on_version": 'version: "7.4.1"',
    }
    requirement = f"cisco-sccfm-devkit=={expected_version}"
    forbidden = (
        "ApiException' is not defined",
        "Module result deserialization failed",
        "Extra data: line",
    )
    for module_name, argument in probes.items():
        playbook = controller.work / f"missing-{module_name}.yml"
        playbook.write_text(
            "---\n"
            "- hosts: localhost\n"
            "  connection: local\n"
            "  gather_facts: false\n"
            "  vars:\n"
            f"    ansible_python_interpreter: {controller.binaries / 'python'}\n"
            "  tasks:\n"
            "    - name: Verify missing paired runtime dependency\n"
            f"      cisco.sccfm.{module_name}:\n"
            f"        {argument}\n",
            encoding="utf-8",
        )
        result = _run(
            controller,
            [controller.binaries / "ansible-playbook", playbook],
            check=False,
        )
        rendered = f"{result.stdout}\n{result.stderr}"
        if (
            result.returncode == 0
            or requirement not in rendered
            or any(message in rendered for message in forbidden)
        ):
            raise CleanControllerVerificationError(
                f"{module_name} did not report the missing paired runtime cleanly"
            )


def _install_wheel(
    controller: _Controller,
    wheel: Path,
    expected_version: str,
) -> None:
    python = controller.binaries / "python"
    _run(controller, [python, "-I", "-m", "pip", "install", "--no-cache-dir", wheel])
    _run(controller, [python, "-I", "-m", "pip", "check"])
    import_check = """\
import importlib, importlib.metadata, importlib.util, sys
assert importlib.metadata.version("cisco-sccfm-devkit") == sys.argv[1]
for name in ("cisco_sccfm_cli", "cisco_sccfm_core", "scc_firewall_manager_sdk"):
    importlib.import_module(name)
assert importlib.util.find_spec("cisco_sccfm_scripts") is None
"""
    _run(controller, [python, "-I", "-c", import_check, expected_version])


def _discover(controller: _Controller) -> tuple[int, int, str]:
    ansible_doc = controller.binaries / "ansible-doc"
    modules = _discovered_plugins(
        _run(controller, [ansible_doc, "-j", "-l", "-t", "module", "cisco.sccfm"]).stdout,
        "module",
    )
    inventory = _discovered_plugins(
        _run(controller, [ansible_doc, "-j", "-l", "-t", "inventory", "cisco.sccfm"]).stdout,
        "inventory",
    )
    if len(modules) != _EXPECTED_MODULES or len(inventory) != _EXPECTED_INVENTORY_PLUGINS:
        raise CleanControllerVerificationError("expected 49 modules and 1 inventory plugin")
    probe = _documented_probe(controller, modules)
    return len(modules), len(inventory), probe


def _offline_checks(controller: _Controller, probe: str) -> None:
    result = _run(
        controller,
        [
            controller.binaries / "ansible",
            "localhost",
            "-i",
            "localhost,",
            "-c",
            "local",
            "-m",
            probe,
            "-e",
            f"ansible_python_interpreter={controller.binaries / 'python'}",
        ],
        check=False,
    )
    if result.returncode == 0 or _TOKEN_ERROR not in f"{result.stdout}\n{result.stderr}":
        raise CleanControllerVerificationError("module did not reach missing-token validation")
    playbook = controller.work / "syntax-check.yml"
    playbook.write_text(
        "---\n- hosts: localhost\n  gather_facts: false\n  tasks:\n" f"    - {probe}: {{}}\n",
        encoding="utf-8",
    )
    _run(controller, [controller.binaries / "ansible-playbook", "--syntax-check", playbook])


def verify_clean_controller(
    wheel: Path,
    collection: Path,
    expected_version: str,
) -> tuple[int, int, str]:
    """Verify matching artifacts using no project code inside the clean controller."""
    wheel_result = verify_python_wheel(wheel)
    if wheel_result.version != expected_version:
        raise CleanControllerVerificationError("wheel and collection versions do not match")
    verify_collection_artifact(collection, expected_version)
    wheel = wheel.resolve()
    collection = collection.resolve()
    with tempfile.TemporaryDirectory(prefix="sccfm-clean-controller-") as temporary:
        controller = _create_controller(Path(temporary))
        _install_controller_and_collection(controller, collection)
        _verify_missing_devkit_dependency(controller, expected_version)
        _install_wheel(controller, wheel, expected_version)
        module_count, inventory_count, probe = _discover(controller)
        _offline_checks(controller, probe)
    return module_count, inventory_count, probe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("collection", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    try:
        modules, inventory, probe = verify_clean_controller(
            args.wheel, args.collection, args.expected_version
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Clean-controller verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Clean controller verified: modules={modules} inventory={inventory} probe={probe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
