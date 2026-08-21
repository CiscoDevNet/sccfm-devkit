# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Smoke-test matching SCCFM artifacts installed from public registries."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cisco_sccfm_scripts.verify_clean_controller import (
    _Controller,
    _create_controller,
    _discovered_plugins,
    _offline_checks,
    _run,
)

_ANSIBLE_CORE = "ansible-core>=2.20,<2.22"
_PYPI_LATEST_URL = "https://pypi.org/pypi/cisco-sccfm-devkit/json"
_PYPI_VERSION_URL = "https://pypi.org/pypi/cisco-sccfm-devkit/{version}/json"
_GALAXY_LATEST_URL = (
    "https://galaxy.ansible.com/api/v3/plugin/ansible/content/published/"
    "collections/index/cisco/sccfm/"
)
_GALAXY_VERSION_URL = f"{_GALAXY_LATEST_URL}versions/{{version}}/"
_MAX_RESPONSE_BYTES = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 30.0
_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class PublicReleaseVerificationError(RuntimeError):
    """Raised when public artifacts do not form a working matching release."""


@dataclass(frozen=True)
class PublicReleaseSummary:
    """Successful public-release smoke-test result."""

    version: str
    module_count: int
    inventory_count: int
    lookup_count: int
    offline_probe: str


def _read_json(response: Any, expected_url: str) -> object:
    """Read one bounded JSON response from an official registry endpoint."""
    if response.geturl() != expected_url:
        raise PublicReleaseVerificationError("registry redirected to an unexpected endpoint")
    try:
        raw: bytes = response.read(_MAX_RESPONSE_BYTES + 1)
    except OSError as exc:
        raise PublicReleaseVerificationError("could not read registry response") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise PublicReleaseVerificationError("registry response exceeds the size limit")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PublicReleaseVerificationError("registry returned invalid JSON") from exc


def _fetch_json(url: str, timeout: float = _REQUEST_TIMEOUT_SECONDS) -> object:
    """Fetch JSON from one fixed PyPI or Galaxy endpoint."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "cisco-sccfm-devkit-public-release-smoke",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return _read_json(response, url)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise PublicReleaseVerificationError("could not query public registry") from exc


def _nested_string(payload: object, *path: str) -> str | None:
    """Read a nested string from an untrusted JSON object."""
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, str) else None


def resolve_public_version(requested: str = "") -> str:
    """Resolve one stable version that is present in both public registries."""
    requested = requested.strip()
    if requested and _VERSION_PATTERN.fullmatch(requested) is None:
        raise PublicReleaseVerificationError("version must be a stable X.Y.Z value")

    if requested:
        encoded = quote(requested, safe="")
        pypi = _fetch_json(_PYPI_VERSION_URL.format(version=encoded))
        galaxy = _fetch_json(_GALAXY_VERSION_URL.format(version=encoded))
        pypi_version = _nested_string(pypi, "info", "version")
        galaxy_version = _nested_string(galaxy, "version")
    else:
        pypi = _fetch_json(_PYPI_LATEST_URL)
        galaxy = _fetch_json(_GALAXY_LATEST_URL)
        pypi_version = _nested_string(pypi, "info", "version")
        galaxy_version = _nested_string(galaxy, "highest_version", "version")

    if pypi_version is None or galaxy_version is None:
        raise PublicReleaseVerificationError("could not resolve versions from public registries")
    if pypi_version != galaxy_version:
        raise PublicReleaseVerificationError(
            f"public registry versions differ: PyPI={pypi_version}, Galaxy={galaxy_version}"
        )
    if requested and pypi_version != requested:
        raise PublicReleaseVerificationError(
            f"registries returned {pypi_version} instead of requested {requested}"
        )
    if _VERSION_PATTERN.fullmatch(pypi_version) is None:
        raise PublicReleaseVerificationError("public registries returned a non-stable version")
    return pypi_version


def _install_public_artifacts(controller: _Controller, version: str) -> None:
    """Install an exact matching release from PyPI and Ansible Galaxy."""
    python = controller.binaries / "python"
    _run(
        controller,
        [
            python,
            "-I",
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--index-url",
            "https://pypi.org/simple",
            _ANSIBLE_CORE,
            f"cisco-sccfm-devkit=={version}",
        ],
    )
    _run(controller, [python, "-I", "-m", "pip", "check"])
    _run(
        controller,
        [
            controller.binaries / "ansible-galaxy",
            "collection",
            "install",
            f"cisco.sccfm:=={version}",
            "--server",
            "https://galaxy.ansible.com",
            "--collections-path",
            controller.collections,
        ],
    )


def _verify_cli(controller: _Controller, version: str) -> None:
    """Verify imports, entry points, help, and the discovered CLI schema."""
    python = controller.binaries / "python"
    check = """\
import importlib, importlib.metadata, importlib.util, sys
assert importlib.metadata.version("cisco-sccfm-devkit") == sys.argv[1]
for name in ("cisco_sccfm_cli", "cisco_sccfm_core", "scc_firewall_manager_sdk"):
    importlib.import_module(name)
assert importlib.util.find_spec("cisco_sccfm_scripts") is None
scripts = {
    entry.name
    for entry in importlib.metadata.distribution("cisco-sccfm-devkit").entry_points
    if entry.group == "console_scripts"
}
assert {"sccfm-cli", "sccfm-cli-interactive"}.issubset(scripts)
"""
    _run(controller, [python, "-I", "-c", check, version])
    _run(controller, [controller.binaries / "sccfm-cli", "--help"])
    _run(controller, [controller.binaries / "sccfm-cli-interactive", "--help"])
    schema_raw = _run(
        controller,
        [controller.binaries / "sccfm-cli", "schema", "export", "--format", "json"],
    ).stdout
    try:
        schema: object = json.loads(schema_raw)
    except json.JSONDecodeError as exc:
        raise PublicReleaseVerificationError("CLI schema is not valid JSON") from exc
    commands = schema.get("commands") if isinstance(schema, dict) else None
    if (
        not isinstance(schema, dict)
        or schema.get("version") != version
        or not isinstance(commands, list)
        or not commands
    ):
        raise PublicReleaseVerificationError("CLI schema does not describe the installed release")


def _verify_collection_version(controller: _Controller, version: str) -> None:
    """Verify that Galaxy installed the exact requested collection version."""
    manifest = controller.collections / "ansible_collections/cisco/sccfm/MANIFEST.json"
    try:
        payload: object = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicReleaseVerificationError("installed collection manifest is invalid") from exc
    installed = _nested_string(payload, "collection_info", "version")
    if installed != version:
        raise PublicReleaseVerificationError(
            f"installed collection version {installed} does not match {version}"
        )


def _discover_plugins(
    controller: _Controller,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Discover every supported cisco.sccfm plugin surface through ansible-doc."""
    ansible_doc = controller.binaries / "ansible-doc"
    discovered = []
    for plugin_type in ("module", "inventory", "lookup"):
        raw = _run(
            controller,
            [ansible_doc, "-j", "-l", "-t", plugin_type, "cisco.sccfm"],
        ).stdout
        discovered.append(_discovered_plugins(raw, plugin_type))
    return discovered[0], discovered[1], discovered[2]


def _documented_probe(controller: _Controller, modules: dict[str, str]) -> str:
    """Select a documented readonly list module with no required business arguments."""
    ansible_doc = controller.binaries / "ansible-doc"
    for name, description in modules.items():
        if not description.casefold().startswith("list "):
            continue
        raw = _run(controller, [ansible_doc, "-j", name]).stdout
        try:
            payload: object = json.loads(raw)
        except json.JSONDecodeError:
            continue
        module = payload.get(name) if isinstance(payload, dict) else None
        doc = module.get("doc") if isinstance(module, dict) else None
        options = doc.get("options") if isinstance(doc, dict) else None
        if isinstance(options, dict) and not any(
            isinstance(option, dict) and option.get("required") is True
            for option in options.values()
        ):
            return name
    raise PublicReleaseVerificationError("no argument-free readonly list module was discovered")


def verify_public_release(requested: str = "") -> PublicReleaseSummary:
    """Install and smoke-test one matching release from the public registries."""
    version = resolve_public_version(requested)
    with tempfile.TemporaryDirectory(prefix="sccfm-public-release-") as temporary:
        controller = _create_controller(Path(temporary))
        _install_public_artifacts(controller, version)
        _verify_cli(controller, version)
        _verify_collection_version(controller, version)
        modules, inventory, lookups = _discover_plugins(controller)
        probe = _documented_probe(controller, modules)
        _offline_checks(controller, probe)
    return PublicReleaseSummary(
        version=version,
        module_count=len(modules),
        inventory_count=len(inventory),
        lookup_count=len(lookups),
        offline_probe=probe,
    )


def _parser() -> argparse.ArgumentParser:
    """Build the public-release smoke-test parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default="",
        help="Exact stable X.Y.Z release; omit to use the latest matching public version.",
    )
    parser.add_argument("--report", type=Path, help="Optional JSON summary output path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the public-release smoke test."""
    args = _parser().parse_args(argv)
    try:
        summary = verify_public_release(args.version)
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Public release verification failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Public release verified: version={summary.version} modules={summary.module_count} "
        f"inventory={summary.inventory_count} lookups={summary.lookup_count} "
        f"probe={summary.offline_probe}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
