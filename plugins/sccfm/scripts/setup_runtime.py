#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Plan, install, inspect, and remove the local SCCFM agent runtime."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

PACKAGE_NAME = "cisco-sccfm-devkit"
COLLECTION_NAME = "cisco.sccfm"
COLLECTION_NAMESPACE = "cisco"
COLLECTION_PACKAGE = "sccfm"
HOMEBREW_FORMULA = "ciscodevnet/tap/sccfm-cli"
HOMEBREW_UNINSTALL_ENVIRONMENT = {"HOMEBREW_NO_AUTOREMOVE": "1"}
ANSIBLE_CORE_SPEC = "ansible-core>=2.20,<2.22"
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
PACKAGE_NORMALIZATION_PATTERN = re.compile(r"[-_.]+")
INSTALL_STATE_SCHEMA_VERSION = 1
CLEANUP_PLAN_SCHEMA_VERSION = 3
CLEANUP_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PYTHON_INSTALLATION_SCRIPT = """
import importlib.metadata
import json
import sys

try:
    distribution = importlib.metadata.distribution("cisco-sccfm-devkit")
except importlib.metadata.PackageNotFoundError:
    raise SystemExit(3)

direct_url = {}
direct_url_text = distribution.read_text("direct_url.json")
if direct_url_text:
    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        direct_url = {}

dir_info = direct_url.get("dir_info", {}) if isinstance(direct_url, dict) else {}
print(json.dumps({
    "version": distribution.version,
    "location": str(distribution.locate_file("")),
    "environment": sys.prefix,
    "editable": bool(dir_info.get("editable")) if isinstance(dir_info, dict) else False,
    "source": direct_url.get("url") if isinstance(direct_url, dict) else None,
}))
"""


def command_path(name: str) -> str | None:
    return shutil.which(name)


def normalized_package_name(name: str) -> str:
    return PACKAGE_NORMALIZATION_PATTERN.sub("-", name).lower()


def run_capture(
    command: Sequence[str], *, environment: dict[str, str] | None = None, limit: int = 1000
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}

    output = (result.stdout or result.stderr).strip()
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output[:limit] if limit else output,
    }


def profile_metadata() -> dict[str, Any]:
    profile_path = profile_store_path()
    if not profile_path.exists():
        return {"configured": False, "path": str(profile_path)}

    metadata: dict[str, Any] = {"configured": True, "path": str(profile_path)}
    if sys.platform != "win32":
        metadata["mode"] = stat.filemode(profile_path.stat().st_mode)
        metadata["secure_permissions"] = stat.S_IMODE(profile_path.stat().st_mode) == 0o600
    return metadata


def profile_store_path() -> Path:
    return Path.home() / ".sccfm-cli" / "config.json"


def collection_install_base_path() -> Path:
    return (Path.home() / ".ansible" / "collections").resolve(strict=False)


def expected_collection_path() -> Path:
    return (
        collection_install_base_path()
        / "ansible_collections"
        / COLLECTION_NAMESPACE
        / COLLECTION_PACKAGE
    )


def install_state_path() -> Path:
    return Path.home() / ".sccfm-agent-plugin" / "runtime.json"


def load_install_state() -> dict[str, Any] | None:
    state_path = install_state_path()
    if not state_path.exists() and not state_path.is_symlink():
        return None
    if state_path.is_symlink() or not state_path.is_file():
        raise RuntimeError(f"runtime ownership state is not a regular file: {state_path}")
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"runtime ownership state is invalid: {state_path}: {error}") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != INSTALL_STATE_SCHEMA_VERSION
    ):
        raise RuntimeError(f"runtime ownership state has an unsupported format: {state_path}")
    collection_path = payload.get("collection_path")
    version = payload.get("version")
    if not isinstance(collection_path, str) or not isinstance(version, str):
        raise RuntimeError(f"runtime ownership state is incomplete: {state_path}")
    recorded_path = Path(collection_path).expanduser()
    if not recorded_path.is_absolute() or recorded_path != expected_collection_path():
        raise RuntimeError(
            f"runtime ownership state points outside the managed collection path: {recorded_path}"
        )
    if not VERSION_PATTERN.fullmatch(version):
        raise RuntimeError(f"runtime ownership state contains an invalid version: {version}")
    return payload


def write_install_state(collection_path: Path, version: str) -> None:
    if collection_path != expected_collection_path():
        raise RuntimeError(f"refusing to own an unexpected collection path: {collection_path}")
    state_path = install_state_path()
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        state_path.parent.chmod(0o700)
    temporary_path = state_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "schema_version": INSTALL_STATE_SCHEMA_VERSION,
                "collection_path": str(collection_path),
                "version": version,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        temporary_path.chmod(0o600)
    temporary_path.replace(state_path)


def remove_install_state() -> None:
    state_path = install_state_path()
    try:
        state_path.unlink()
    except FileNotFoundError:
        return
    try:
        state_path.parent.rmdir()
    except OSError:
        pass


def schema_metadata() -> dict[str, Any]:
    if command_path("sccfm-cli") is None:
        return {"ok": False, "error": "sccfm-cli is not on PATH"}

    result = run_capture(["sccfm-cli", "schema", "export", "--format", "json"], limit=0)
    if not result["ok"]:
        return result
    try:
        payload = json.loads(str(result["output"]))
    except json.JSONDecodeError as error:
        return {"ok": False, "error": f"schema output was not JSON: {error}"}
    return {
        "ok": True,
        "version": payload.get("version"),
        "command_count": len(payload.get("commands", [])),
    }


def collection_listing(environment: dict[str, str]) -> dict[str, Any]:
    if command_path("ansible-galaxy") is None:
        raise RuntimeError("ansible-galaxy is not on PATH")

    result = run_capture(
        ["ansible-galaxy", "collection", "list", COLLECTION_NAME, "--format", "json"],
        environment=environment,
        limit=0,
    )
    if not result["ok"]:
        raise RuntimeError(
            str(result.get("error") or result.get("output") or "collection list failed")
        )
    try:
        payload = json.loads(str(result["output"]))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"collection output was not JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError("collection output was not a JSON object")
    return payload


def validated_collection_path(collection_root: str) -> Path:
    root = Path(collection_root).expanduser()
    if not root.is_absolute():
        raise ValueError(f"collection root is not absolute: {collection_root}")
    if root.is_symlink():
        raise ValueError(f"collection root must not be a symlink: {collection_root}")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"collection root does not exist: {collection_root}") from error
    if resolved_root.name != "ansible_collections":
        raise ValueError(f"unexpected collection root: {resolved_root}")

    namespace_path = resolved_root / COLLECTION_NAMESPACE
    collection_path = namespace_path / COLLECTION_PACKAGE
    if namespace_path.is_symlink() or collection_path.is_symlink():
        raise ValueError(f"collection path must not contain symlinks: {collection_path}")
    if not collection_path.is_dir():
        raise ValueError(f"reported collection path is not a directory: {collection_path}")
    return collection_path


def collection_installations(payload: dict[str, Any]) -> list[dict[str, str]]:
    installations: list[dict[str, str]] = []
    for root, collections in payload.items():
        if not isinstance(root, str) or not isinstance(collections, dict):
            continue
        metadata = collections.get(COLLECTION_NAME)
        if not isinstance(metadata, dict):
            continue
        version = metadata.get("version")
        installations.append(
            {
                "path": str(validated_collection_path(root)),
                "version": version if isinstance(version, str) else "unknown",
            }
        )
    return installations


def collection_metadata(environment: dict[str, str]) -> dict[str, Any]:
    try:
        installations = collection_installations(collection_listing(environment))
        install_state = load_install_state()
    except (RuntimeError, ValueError) as error:
        return {"ok": False, "error": str(error)}

    if not installations:
        return {
            "ok": True,
            "installed": False,
            "installations": 0,
            "paths": [],
        }
    selected_installation = installations[0]
    managed = False
    if install_state is not None:
        managed_path = str(install_state["collection_path"])
        selected_installation = next(
            (
                installation
                for installation in installations
                if installation["path"] == managed_path
            ),
            {},
        )
        if not selected_installation:
            return {
                "ok": False,
                "error": (
                    "the recorded managed collection is not reported by ansible-galaxy: "
                    f"{managed_path}"
                ),
            }
        managed = True
    return {
        "ok": True,
        "installed": True,
        "version": selected_installation["version"],
        "managed": managed,
        "selected_path": selected_installation["path"],
        "installations": len(installations),
        "paths": [installation["path"] for installation in installations],
    }


def doctor_report() -> dict[str, Any]:
    python_candidates = {name: command_path(name) for name in ("python3.12", "python3", "python")}
    python_versions = {
        name: run_capture([path, "--version"])
        for name, path in python_candidates.items()
        if path is not None
    }
    commands = {
        name: command_path(name)
        for name in ("brew", "pipx", "sccfm-cli", "ansible-doc", "ansible-galaxy")
    }
    schema = schema_metadata()
    report: dict[str, Any] = {
        "python_candidates": python_candidates,
        "python_versions": python_versions,
        "commands": commands,
        "profile": profile_metadata(),
        "schema": schema,
    }
    try:
        homebrew_installation = homebrew_formula_installation()
    except RuntimeError as error:
        report["homebrew"] = {"ok": False, "error": str(error)}
    else:
        report["homebrew"] = {
            "ok": True,
            "installed": homebrew_installation is not None,
            "installation": homebrew_installation,
        }
    report["cli_version"] = schema.get("version") if schema.get("ok") else None
    with tempfile.TemporaryDirectory(prefix="sccfm-agent-doctor-") as temporary_directory:
        ansible_environment = os.environ.copy()
        ansible_environment["ANSIBLE_LOCAL_TEMP"] = temporary_directory
        report["collection"] = collection_metadata(ansible_environment)
        if commands["ansible-doc"]:
            report["ansible_discovery"] = run_capture(
                ["ansible-doc", "-j", "-l", "-t", "module", COLLECTION_NAME],
                environment=ansible_environment,
            )
    cli_version = report["cli_version"]
    collection_version = report["collection"].get("version")
    report["versions_match"] = bool(cli_version and cli_version == collection_version)
    report["operational"] = bool(
        schema.get("ok")
        and report["collection"].get("ok")
        and report["collection"].get("installed")
        and report.get("ansible_discovery", {}).get("ok")
        and report["versions_match"]
        and report["profile"].get("configured")
    )
    return report


def install_commands(
    version: str, python_command: str, collection_base: Path | None = None
) -> list[list[str]]:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("version must be a stable X.Y.Z release")
    return [
        [
            "pipx",
            "install",
            "--python",
            python_command,
            "--force",
            f"{PACKAGE_NAME}=={version}",
        ],
        [
            "pipx",
            "inject",
            "--include-apps",
            "--force",
            PACKAGE_NAME,
            ANSIBLE_CORE_SPEC,
        ],
        [
            "ansible-galaxy",
            "collection",
            "install",
            f"{COLLECTION_NAME}:=={version}",
            "--force",
            "--collections-path",
            str(collection_base or collection_install_base_path()),
        ],
    ]


def print_plan(version: str, python_command: str) -> None:
    homebrew_installation = homebrew_formula_installation()
    if homebrew_installation is not None:
        installed_versions = ", ".join(homebrew_installation["versions"])
        raise SystemExit(
            f"Homebrew already manages {HOMEBREW_FORMULA} {installed_versions}; "
            "refusing to plan a duplicate pipx installation"
        )
    for command in install_commands(version, python_command):
        print(shlex.join(command))


def install(version: str, python_command: str, confirmed: bool) -> None:
    if not confirmed:
        raise SystemExit("Refusing to install without --yes after user confirmation")
    if command_path("pipx") is None:
        raise SystemExit("pipx is required; install pipx before continuing")
    if command_path(python_command) is None:
        raise SystemExit(f"Python runtime is not on PATH: {python_command}")
    homebrew_installation = homebrew_formula_installation()
    if homebrew_installation is not None:
        installed_versions = ", ".join(homebrew_installation["versions"])
        raise SystemExit(
            f"Homebrew already manages {HOMEBREW_FORMULA} {installed_versions}; "
            "remove it through a reviewed cleanup before installing with pipx"
        )
    target_path = expected_collection_path()
    install_state = load_install_state()
    if target_path.exists() or target_path.is_symlink():
        if target_path.is_symlink() or not target_path.is_dir():
            raise SystemExit(f"Managed collection target is unsafe: {target_path}")
        if install_state is None:
            raise SystemExit(
                "Refusing to overwrite an existing collection that is not owned by this helper: "
                f"{target_path}"
            )
    elif install_state is not None:
        raise SystemExit(
            "Runtime ownership state exists but its collection is missing; "
            f"remove or repair {install_state_path()} before reinstalling"
        )
    for command in install_commands(version, python_command):
        print(f"Running: {shlex.join(command)}")
        subprocess.run(command, check=True)
    installed_path = validated_collection_path(
        str(collection_install_base_path() / "ansible_collections")
    )
    if installed_path != target_path:
        raise RuntimeError(
            f"collection was installed outside the expected managed path: {installed_path}"
        )
    write_install_state(installed_path, version)


def discover_collection_paths() -> list[Path]:
    with tempfile.TemporaryDirectory(prefix="sccfm-agent-uninstall-") as temporary_directory:
        ansible_environment = os.environ.copy()
        ansible_environment["ANSIBLE_LOCAL_TEMP"] = temporary_directory
        return [
            Path(installation["path"])
            for installation in collection_installations(collection_listing(ansible_environment))
        ]


def partition_collection_paths(collection_paths: Sequence[Path]) -> tuple[list[Path], list[Path]]:
    install_state = load_install_state()
    if install_state is None:
        return [], list(collection_paths)
    managed_path = Path(str(install_state["collection_path"]))
    if managed_path not in collection_paths:
        raise RuntimeError(
            "the recorded managed collection is not reported by ansible-galaxy: " f"{managed_path}"
        )
    return [managed_path], [path for path in collection_paths if path != managed_path]


def pipx_package_environment() -> Path | None:
    actual_home = Path.home()
    configured_pipx_home = os.environ.get("PIPX_HOME")
    if configured_pipx_home:
        pipx_home = Path(configured_pipx_home).expanduser()
        if not pipx_home.is_dir():
            return None
    else:
        pipx_home_candidates = (
            actual_home / ".local" / "share" / "pipx",
            actual_home / ".local" / "pipx",
            actual_home / ".pipx",
            actual_home / "Library" / "Application Support" / "pipx",
        )
        discovered_pipx_home = next(
            (candidate for candidate in pipx_home_candidates if candidate.is_dir()),
            None,
        )
        if discovered_pipx_home is None:
            return None
        pipx_home = discovered_pipx_home
    environments_path = pipx_home / "venvs"
    if environments_path.is_symlink():
        raise RuntimeError(f"pipx environments path must not be a symlink: {environments_path}")
    if not environments_path.is_dir():
        return None
    expected_name = normalized_package_name(PACKAGE_NAME)
    for environment_path in environments_path.iterdir():
        if environment_path.is_symlink() or not environment_path.is_dir():
            continue
        metadata_path = environment_path / "pipx_metadata.json"
        if metadata_path.is_symlink() or not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise RuntimeError(f"pipx metadata is invalid: {metadata_path}: {error}") from error
        main_package = metadata.get("main_package", {}) if isinstance(metadata, dict) else {}
        package = main_package.get("package") if isinstance(main_package, dict) else None
        if isinstance(package, str) and normalized_package_name(package) == expected_name:
            return environment_path.resolve(strict=False)
    return None


def pipx_package_installed() -> bool:
    return pipx_package_environment() is not None


def homebrew_formula_installation() -> dict[str, Any] | None:
    brew = command_path("brew")
    if brew is None:
        return None
    installed_formulae = run_capture([brew, "list", "--formula", "--full-name"], limit=0)
    if not installed_formulae["ok"]:
        detail = (
            installed_formulae.get("error")
            or installed_formulae.get("output")
            or "formula discovery failed"
        )
        raise RuntimeError(f"cannot inspect Homebrew formulae: {detail}")
    if HOMEBREW_FORMULA not in str(installed_formulae["output"]).splitlines():
        return None
    version_result = run_capture(
        [brew, "list", "--formula", "--versions", HOMEBREW_FORMULA],
        limit=0,
    )
    if not version_result["ok"]:
        detail = version_result.get("error") or version_result.get("output") or "version failed"
        raise RuntimeError(f"cannot inspect Homebrew formula version: {detail}")
    fields = str(version_result["output"]).split()
    versions = fields[1:] if fields and fields[0] == "sccfm-cli" else []
    if not versions:
        raise RuntimeError(
            f"Homebrew reports {HOMEBREW_FORMULA} but did not return an installed version"
        )
    return {
        "formula": HOMEBREW_FORMULA,
        "versions": versions,
        "command": [brew, "uninstall", HOMEBREW_FORMULA],
        "environment": HOMEBREW_UNINSTALL_ENVIRONMENT,
    }


def environment_python_paths(environment_path: Path) -> list[Path]:
    if os.name == "nt":
        return [environment_path / "Scripts" / "python.exe"]
    return [
        environment_path / "bin" / "python",
        environment_path / "bin" / "python3",
        environment_path / "bin" / "python3.12",
    ]


def resolved_command_path(name: str) -> Path | None:
    executable = command_path(name)
    if executable is None:
        return None
    path = Path(executable).expanduser()
    pyenv = command_path("pyenv")
    if path.parent.name == "shims" and pyenv is not None:
        result = run_capture([pyenv, "which", name], limit=0)
        if result["ok"]:
            resolved = Path(str(result["output"])).expanduser()
            if resolved.is_absolute() and resolved.is_file():
                return resolved
    if not path.is_absolute() or not path.is_file():
        return None
    return path


def candidate_python_paths(*, include_cli_candidate: bool) -> list[Path]:
    candidates: list[Path] = []

    def add_candidate(path: Path | None) -> None:
        if path is None or not path.is_absolute() or not path.is_file():
            return
        if path not in candidates:
            candidates.append(path)

    for name in ("python3.12", "python3", "python"):
        add_candidate(resolved_command_path(name))

    pyenv = command_path("pyenv")
    if pyenv is not None:
        result = run_capture([pyenv, "prefix", "--all"], limit=0)
        if result["ok"]:
            for prefix in str(result["output"]).splitlines():
                prefix_path = Path(prefix.strip()).expanduser()
                if not prefix_path.is_absolute():
                    continue
                for python_path in environment_python_paths(prefix_path):
                    add_candidate(python_path)

    virtual_environment = os.environ.get("VIRTUAL_ENV")
    environment_paths = [Path.cwd() / ".venv"]
    if virtual_environment:
        environment_paths.append(Path(virtual_environment).expanduser())
    if include_cli_candidate:
        cli_path = resolved_command_path("sccfm-cli")
        if cli_path is not None and cli_path.parent.name in {"bin", "Scripts"}:
            environment_paths.append(cli_path.parent.parent)
    for environment_path in environment_paths:
        if not environment_path.is_absolute():
            environment_path = environment_path.resolve(strict=False)
        for python_path in environment_python_paths(environment_path):
            add_candidate(python_path)
    return candidates


def inspect_python_installation(interpreter: Path) -> dict[str, Any] | None:
    result = run_capture([str(interpreter), "-c", PYTHON_INSTALLATION_SCRIPT], limit=0)
    if result.get("exit_code") == 3:
        return None
    if not result["ok"]:
        detail = result.get("error") or result.get("output") or "inspection failed"
        raise RuntimeError(f"cannot inspect Python environment {interpreter}: {detail}")
    try:
        payload = json.loads(str(result["output"]))
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Python environment inspection was not JSON for {interpreter}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Python environment inspection was invalid for {interpreter}")
    version = payload.get("version")
    location = payload.get("location")
    environment = payload.get("environment")
    if not all(isinstance(value, str) for value in (version, location, environment)):
        raise RuntimeError(f"Python environment inspection was incomplete for {interpreter}")
    source = payload.get("source")
    return {
        "interpreter": str(interpreter),
        "version": version,
        "location": location,
        "environment": environment,
        "editable": payload.get("editable") is True,
        "source": source if isinstance(source, str) else None,
        "command": [
            str(interpreter),
            "-m",
            "pip",
            "uninstall",
            "--yes",
            PACKAGE_NAME,
        ],
    }


def discover_python_installations(*, include_cli_candidate: bool) -> list[dict[str, Any]]:
    installations: dict[str, dict[str, Any]] = {}
    for interpreter in candidate_python_paths(include_cli_candidate=include_cli_candidate):
        installation = inspect_python_installation(interpreter)
        if installation is None:
            continue
        location = str(installation["location"])
        installations.setdefault(location, installation)
    return [installations[key] for key in sorted(installations)]


def collection_identity_matches(collection_path: Path) -> bool:
    manifest_path = collection_path / "MANIFEST.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return False
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    collection_info = payload.get("collection_info", {}) if isinstance(payload, dict) else {}
    return bool(
        isinstance(collection_info, dict)
        and collection_info.get("namespace") == COLLECTION_NAMESPACE
        and collection_info.get("name") == COLLECTION_PACKAGE
    )


def discover_cleanup_collection_paths() -> list[Path]:
    if command_path("ansible-galaxy") is not None:
        return discover_collection_paths()
    collection_path = expected_collection_path()
    if not collection_path.exists() and not collection_path.is_symlink():
        return []
    if collection_path.is_symlink() or not collection_path.is_dir():
        raise RuntimeError(f"standard collection path is unsafe: {collection_path}")
    if not collection_identity_matches(collection_path):
        raise RuntimeError(
            "cannot positively identify the collection without ansible-galaxy: "
            f"{collection_path}"
        )
    return [collection_path]


def partition_cleanup_collection_paths(
    collection_paths: Sequence[Path],
) -> tuple[list[Path], list[Path]]:
    install_state = load_install_state()
    managed_path = Path(str(install_state["collection_path"])) if install_state else None
    if managed_path is not None and managed_path not in collection_paths:
        if managed_path.exists() or managed_path.is_symlink():
            raise RuntimeError(
                "the recorded managed collection is not reported by ansible-galaxy: "
                f"{managed_path}"
            )
    removable: list[Path] = []
    preserved: list[Path] = []
    for path in collection_paths:
        if path == expected_collection_path() or path == managed_path:
            removable.append(path)
        else:
            preserved.append(path)
    return removable, preserved


def cleanup_plan_digest(plan: dict[str, Any]) -> str:
    digest_payload = {key: value for key, value in plan.items() if key != "plan_digest"}
    encoded = json.dumps(digest_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cleanup_plan(remove_profiles: bool, include_editable: bool) -> dict[str, Any]:
    collection_paths, preserved_collection_paths = partition_cleanup_collection_paths(
        discover_cleanup_collection_paths()
    )
    managed_environment = pipx_package_environment()
    managed_environment_installed = managed_environment is not None
    pipx_executable = command_path("pipx")
    if managed_environment_installed and pipx_executable is None:
        raise RuntimeError(
            "the SCCFM pipx environment exists but pipx is unavailable; "
            "install pipx before cleanup"
        )
    pipx_command: list[str] | None = None
    if managed_environment_installed:
        assert pipx_executable is not None
        pipx_command = [pipx_executable, "uninstall", PACKAGE_NAME]
    homebrew_installation = homebrew_formula_installation()
    python_installations = discover_python_installations(
        include_cli_candidate=not managed_environment_installed and homebrew_installation is None
    )
    if managed_environment is not None:
        python_installations = [
            installation
            for installation in python_installations
            if Path(str(installation["environment"])).resolve(strict=False) != managed_environment
        ]
    removable_python = [
        installation
        for installation in python_installations
        if include_editable or not installation["editable"]
    ]
    preserved_python = [
        installation
        for installation in python_installations
        if installation["editable"] and not include_editable
    ]
    plan: dict[str, Any] = {
        "schema_version": CLEANUP_PLAN_SCHEMA_VERSION,
        "options": {
            "include_editable": include_editable,
            "remove_profiles": remove_profiles,
        },
        "collection_paths": [str(path) for path in collection_paths],
        "preserved_collection_paths": [str(path) for path in preserved_collection_paths],
        "install_state": {
            "action": "delete" if install_state_path().exists() else "absent",
            "path": str(install_state_path()),
            "exists": install_state_path().exists(),
        },
        "homebrew_installation": homebrew_installation,
        "pipx_command": pipx_command,
        "python_installations": removable_python,
        "preserved_python_installations": preserved_python,
        "profile": {
            "action": "delete" if remove_profiles else "preserve",
            "path": str(profile_store_path()),
            "exists": profile_store_path().exists(),
        },
    }
    plan["plan_digest"] = cleanup_plan_digest(plan)
    return plan


def print_cleanup_plan(remove_profiles: bool, include_editable: bool, as_json: bool) -> None:
    plan = cleanup_plan(remove_profiles, include_editable)
    if as_json:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return
    for path in plan["collection_paths"]:
        print(f"Remove Ansible collection: {path}")
    for path in plan["preserved_collection_paths"]:
        print(f"Preserve Ansible collection outside the standard managed path: {path}")
    if plan["pipx_command"]:
        print(f"Run: {shlex.join(plan['pipx_command'])}")
    homebrew_installation = plan["homebrew_installation"]
    if homebrew_installation:
        versions = ", ".join(homebrew_installation["versions"])
        environment = " ".join(
            f"{name}={value}" for name, value in homebrew_installation["environment"].items()
        )
        print(
            f"Remove Homebrew formula {homebrew_installation['formula']} {versions}: "
            f"{environment} {shlex.join(homebrew_installation['command'])}"
        )
    for installation in plan["python_installations"]:
        print(
            f"Remove Python package {installation['version']} from "
            f"{installation['environment']}: {shlex.join(installation['command'])}"
        )
    for installation in plan["preserved_python_installations"]:
        print(
            f"Preserve editable Python package {installation['version']} from "
            f"{installation['source'] or installation['environment']}"
        )
    profile = plan["profile"]
    print(f"{str(profile['action']).capitalize()} profile store: {profile['path']}")
    print(f"Plan digest: {plan['plan_digest']}")


def validate_collection_before_removal(collection_path: Path) -> None:
    if collection_path != expected_collection_path():
        raise RuntimeError(
            f"refusing to remove collection outside the standard path: {collection_path}"
        )
    validated = validated_collection_path(str(collection_path.parents[1]))
    if validated != collection_path:
        raise RuntimeError(f"collection path changed after planning: {collection_path}")


def cleanup(
    remove_profiles: bool,
    include_editable: bool,
    plan_digest: str,
    confirmed: bool,
) -> None:
    if not confirmed:
        raise SystemExit("Refusing to clean up without --yes after user confirmation")
    if not CLEANUP_DIGEST_PATTERN.fullmatch(plan_digest):
        raise SystemExit("Cleanup requires the 64-character digest from the reviewed plan")
    plan = cleanup_plan(remove_profiles, include_editable)
    current_digest = str(plan["plan_digest"])
    if not hmac.compare_digest(plan_digest, current_digest):
        raise RuntimeError(
            "cleanup targets changed after review; generate and confirm a new cleanup plan"
        )
    for collection_path in plan["collection_paths"]:
        path = Path(collection_path)
        validate_collection_before_removal(path)
        print(f"Removing Ansible collection: {path}")
        shutil.rmtree(path)
    if plan["install_state"]["action"] == "delete":
        remove_install_state()
    pipx_command = plan["pipx_command"]
    if pipx_command:
        print(f"Running: {shlex.join(pipx_command)}")
        subprocess.run(pipx_command, check=True)
    homebrew_installation = plan["homebrew_installation"]
    if homebrew_installation:
        homebrew_command = homebrew_installation["command"]
        homebrew_environment = os.environ.copy()
        homebrew_environment.update(homebrew_installation["environment"])
        print("Running without Homebrew dependency autoremove: " f"{shlex.join(homebrew_command)}")
        subprocess.run(homebrew_command, check=True, env=homebrew_environment)
    for installation in plan["python_installations"]:
        command = installation["command"]
        print(f"Running: {shlex.join(command)}")
        subprocess.run(command, check=True)
    if remove_profiles:
        print(f"Removing profile store: {profile_store_path()}")
        remove_profile_store()
    else:
        print(f"Preserving profile store: {profile_store_path()}")


def uninstall_plan(remove_profiles: bool) -> dict[str, Any]:
    collection_paths, preserved_collection_paths = partition_collection_paths(
        discover_collection_paths()
    )
    pipx_path = command_path("pipx")
    cli_path = command_path("sccfm-cli")
    if pipx_path is None and cli_path is not None:
        raise RuntimeError(
            "sccfm-cli is installed but pipx is unavailable; refusing to guess how it was installed"
        )
    managed_environment_installed = pipx_package_installed() if pipx_path is not None else False
    if cli_path is not None and not managed_environment_installed:
        raise RuntimeError(
            "sccfm-cli is not owned by the managed pipx environment; refusing to remove it"
        )
    return {
        "collection_paths": [str(path) for path in collection_paths],
        "preserved_collection_paths": [str(path) for path in preserved_collection_paths],
        "install_state": {
            "action": "delete" if collection_paths else "absent",
            "path": str(install_state_path()),
            "exists": install_state_path().exists(),
        },
        "pipx_command": (
            ["pipx", "uninstall", PACKAGE_NAME] if managed_environment_installed else None
        ),
        "profile": {
            "action": "delete" if remove_profiles else "preserve",
            "path": str(profile_store_path()),
            "exists": profile_store_path().exists(),
        },
    }


def print_uninstall_plan(remove_profiles: bool, as_json: bool) -> None:
    plan = uninstall_plan(remove_profiles)
    if as_json:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return

    collection_paths = plan["collection_paths"]
    if collection_paths:
        for path in collection_paths:
            print(f"Remove Ansible collection: {path}")
    else:
        print(f"No helper-managed Ansible collection is installed: {COLLECTION_NAME}")
    for path in plan["preserved_collection_paths"]:
        print(f"Preserve unmanaged Ansible collection: {path}")
    install_state = plan["install_state"]
    if install_state["action"] == "delete":
        print(f"Remove runtime ownership state: {install_state['path']}")
    pipx_command = plan["pipx_command"]
    if pipx_command:
        print(f"Run: {shlex.join(pipx_command)}")
    else:
        print(f"pipx environment is not installed: {PACKAGE_NAME}")
    profile = plan["profile"]
    print(f"{str(profile['action']).capitalize()} profile store: {profile['path']}")


def remove_profile_store() -> None:
    profile_path = profile_store_path()
    if not profile_path.exists() and not profile_path.is_symlink():
        return
    if profile_path.is_dir() and not profile_path.is_symlink():
        raise RuntimeError(f"profile store is unexpectedly a directory: {profile_path}")
    profile_path.unlink()
    try:
        profile_path.parent.rmdir()
    except OSError:
        pass


def uninstall(remove_profiles: bool, confirmed: bool) -> None:
    if not confirmed:
        raise SystemExit("Refusing to uninstall without --yes after user confirmation")
    plan = uninstall_plan(remove_profiles)
    for collection_path in plan["collection_paths"]:
        path = Path(collection_path)
        print(f"Removing Ansible collection: {path}")
        shutil.rmtree(path)
    if plan["collection_paths"]:
        remove_install_state()
    pipx_command = plan["pipx_command"]
    if pipx_command:
        print(f"Running: {shlex.join(pipx_command)}")
        subprocess.run(pipx_command, check=True)
    if remove_profiles:
        print(f"Removing profile store: {profile_store_path()}")
        remove_profile_store()
    else:
        print(f"Preserving profile store: {profile_store_path()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--version", required=True)
    plan_parser.add_argument("--python", default="python3.12")

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--version", required=True)
    install_parser.add_argument("--python", default="python3.12")
    install_parser.add_argument("--yes", action="store_true")

    uninstall_plan_parser = subparsers.add_parser("uninstall-plan")
    uninstall_plan_parser.add_argument("--remove-profiles", action="store_true")
    uninstall_plan_parser.add_argument("--json", action="store_true")

    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("--remove-profiles", action="store_true")
    uninstall_parser.add_argument("--yes", action="store_true")

    cleanup_plan_parser = subparsers.add_parser("cleanup-plan")
    cleanup_plan_parser.add_argument("--remove-profiles", action="store_true")
    cleanup_plan_parser.add_argument("--include-editable", action="store_true")
    cleanup_plan_parser.add_argument("--json", action="store_true")

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--remove-profiles", action="store_true")
    cleanup_parser.add_argument("--include-editable", action="store_true")
    cleanup_parser.add_argument("--plan-digest", required=True)
    cleanup_parser.add_argument("--yes", action="store_true")

    arguments = parser.parse_args()
    if arguments.action == "doctor":
        report = doctor_report()
        if arguments.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
    elif arguments.action == "plan":
        print_plan(arguments.version, arguments.python)
    elif arguments.action == "install":
        install(arguments.version, arguments.python, arguments.yes)
    elif arguments.action == "uninstall-plan":
        try:
            print_uninstall_plan(arguments.remove_profiles, arguments.json)
        except RuntimeError as error:
            raise SystemExit(f"Cannot safely plan uninstall: {error}") from error
    elif arguments.action == "uninstall":
        try:
            uninstall(arguments.remove_profiles, arguments.yes)
        except RuntimeError as error:
            raise SystemExit(f"Cannot safely uninstall: {error}") from error
    elif arguments.action == "cleanup-plan":
        try:
            print_cleanup_plan(
                arguments.remove_profiles,
                arguments.include_editable,
                arguments.json,
            )
        except RuntimeError as error:
            raise SystemExit(f"Cannot safely plan cleanup: {error}") from error
    elif arguments.action == "cleanup":
        try:
            cleanup(
                arguments.remove_profiles,
                arguments.include_editable,
                arguments.plan_digest,
                arguments.yes,
            )
        except RuntimeError as error:
            raise SystemExit(f"Cannot safely clean up: {error}") from error


if __name__ == "__main__":
    main()
