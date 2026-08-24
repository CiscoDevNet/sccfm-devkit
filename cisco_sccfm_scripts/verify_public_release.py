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
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cisco_sccfm_scripts.verify_clean_controller import (
    _PROFILE_ERROR,
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
_MINIMUM_MODULES = 49
_MINIMUM_INVENTORY_PLUGINS = 1
_MINIMUM_LOOKUP_PLUGINS = 1
_PROFILE_REGION = "int"
_PROFILE_TOKEN = "sccfm-public-release-smoke-not-a-real-token"
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
    inventory_probe: str
    lookup_probe: str


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys instead of accepting ambiguous registry JSON."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PublicReleaseVerificationError("registry response contains a duplicate JSON key")
        result[key] = value
    return result


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
        return json.loads(raw, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PublicReleaseVerificationError("registry returned invalid JSON") from exc


def _registry_name(url: str) -> str:
    """Return the public registry represented by one fixed endpoint."""
    if url.startswith("https://pypi.org/"):
        return "PyPI"
    if url.startswith("https://galaxy.ansible.com/"):
        return "Ansible Galaxy"
    raise PublicReleaseVerificationError("unsupported public registry endpoint")


def _fetch_json(url: str, timeout: float = _REQUEST_TIMEOUT_SECONDS) -> object:
    """Fetch JSON from one fixed PyPI or Galaxy endpoint."""
    registry = _registry_name(url)
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
    except HTTPError as exc:
        raise PublicReleaseVerificationError(
            f"{registry} returned HTTP {exc.code} for {url}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise PublicReleaseVerificationError(f"could not query {registry} at {url}") from exc


def _nested_string(payload: object, *path: str) -> str | None:
    """Read a nested string from an untrusted JSON object."""
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, str) else None


def _log(message: str) -> None:
    """Emit one immediately visible smoke-test progress message."""
    print(f"[sccfm-smoke] {message}", flush=True)


def resolve_public_version(requested: str = "") -> str:
    """Resolve one stable version that is present in both public registries."""
    requested = requested.strip()
    if requested and _VERSION_PATTERN.fullmatch(requested) is None:
        raise PublicReleaseVerificationError("version must be a stable X.Y.Z value")

    if requested:
        _log(f"Checking requested release {requested} on PyPI and Ansible Galaxy")
        encoded = quote(requested, safe="")
        pypi = _fetch_json(_PYPI_VERSION_URL.format(version=encoded))
        galaxy = _fetch_json(_GALAXY_VERSION_URL.format(version=encoded))
        pypi_version = _nested_string(pypi, "info", "version")
        galaxy_version = _nested_string(galaxy, "version")
    else:
        _log("Resolving the latest stable release from PyPI and Ansible Galaxy")
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
    _log(f"Selected public release {pypi_version} from both registries")
    return pypi_version


def _install_public_artifacts(controller: _Controller, version: str) -> None:
    """Install an exact matching release from PyPI and Ansible Galaxy."""
    python = controller.binaries / "python"
    _log(f"Installing cisco-sccfm-devkit=={version} from public PyPI")
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
    _log(f"Installed and dependency-checked cisco-sccfm-devkit=={version} from PyPI")
    _log(f"Installing cisco.sccfm:=={version} from public Ansible Galaxy")
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
    _log(f"Installed cisco.sccfm:=={version} from Ansible Galaxy")


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
    _validate_cli_schema(schema, version)


def _validate_cli_schema(schema: object, version: str) -> None:
    """Require the public schema contract used by safe automation consumers."""
    commands = schema.get("commands") if isinstance(schema, dict) else None
    if not isinstance(schema, dict) or schema.get("version") != version:
        raise PublicReleaseVerificationError("CLI schema does not describe the installed release")
    if not isinstance(commands, list) or not commands:
        raise PublicReleaseVerificationError("CLI schema did not expose any commands")
    for command in commands:
        if not isinstance(command, dict):
            raise PublicReleaseVerificationError("CLI schema contains an invalid command")
        path = command.get("path")
        auth = command.get("auth")
        if (
            not isinstance(path, list)
            or not path
            or any(not isinstance(part, str) or not part for part in path)
            or not isinstance(command.get("command"), str)
            or not command["command"]
            or not isinstance(command.get("readonly"), bool)
            or not isinstance(auth, dict)
            or not isinstance(auth.get("requires_profile"), bool)
            or not isinstance(auth.get("requires_api_token"), bool)
            or not isinstance(command.get("options"), list)
            or not isinstance(command.get("constraints"), list)
        ):
            raise PublicReleaseVerificationError("CLI schema command metadata is incomplete")


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


def _validate_plugin_counts(
    modules: dict[str, str],
    inventory: dict[str, str],
    lookups: dict[str, str],
) -> None:
    """Require the public collection to retain its established plugin surfaces."""
    counts = (len(modules), len(inventory), len(lookups))
    minimums = (_MINIMUM_MODULES, _MINIMUM_INVENTORY_PLUGINS, _MINIMUM_LOOKUP_PLUGINS)
    if any(actual < minimum for actual, minimum in zip(counts, minimums, strict=True)):
        raise PublicReleaseVerificationError(
            "public collection exposes fewer plugins than expected: "
            f"modules={counts[0]} inventory={counts[1]} lookups={counts[2]}"
        )


def _plugin_documentation(
    controller: _Controller,
    plugin_type: str,
    name: str,
) -> dict[str, object]:
    """Load and validate one discovered plugin's ansible-doc payload."""
    raw = _run(
        controller,
        [controller.binaries / "ansible-doc", "-j", "-t", plugin_type, name],
    ).stdout
    try:
        payload: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PublicReleaseVerificationError(f"{plugin_type} documentation is invalid") from exc
    plugin = payload.get(name) if isinstance(payload, dict) else None
    doc = plugin.get("doc") if isinstance(plugin, dict) else None
    if not isinstance(doc, dict):
        raise PublicReleaseVerificationError(f"{plugin_type} documentation is missing")
    return doc


def _documented_probe(controller: _Controller, modules: dict[str, str]) -> str:
    """Select a documented readonly list module with no required business arguments."""
    for name, description in modules.items():
        if not description.casefold().startswith("list "):
            continue
        doc = _plugin_documentation(controller, "module", name)
        options = doc.get("options") if isinstance(doc, dict) else None
        if isinstance(options, dict) and not any(
            isinstance(option, dict) and option.get("required") is True
            for option in options.values()
        ):
            return name
    raise PublicReleaseVerificationError("no argument-free readonly list module was discovered")


def _expect_missing_profile(
    controller: _Controller,
    command: list[str | Path],
    surface: str,
    *,
    allow_zero: bool = False,
) -> None:
    """Require an offline runtime path to stop at profile validation."""
    result = _run(controller, command, check=False)
    rendered = f"{result.stdout}\n{result.stderr}"
    if (result.returncode == 0 and not allow_zero) or _PROFILE_ERROR not in rendered:
        raise PublicReleaseVerificationError(f"{surface} did not reach missing-profile validation")


def _inventory_runtime_probe(controller: _Controller, inventory: dict[str, str]) -> str:
    """Load a documented inventory plugin without contacting SCCFM."""
    for name in inventory:
        doc = _plugin_documentation(controller, "inventory", name)
        options = doc.get("options")
        plugin_option = options.get("plugin") if isinstance(options, dict) else None
        choices = plugin_option.get("choices") if isinstance(plugin_option, dict) else None
        if (
            isinstance(plugin_option, dict)
            and plugin_option.get("required") is True
            and isinstance(choices, list)
            and name in choices
        ):
            config = controller.work / "inventory.sccfm.yml"
            config.write_text(f"plugin: {json.dumps(name)}\n", encoding="utf-8")
            _log(f"Running offline missing-profile inventory probe: {name}")
            _expect_missing_profile(
                controller,
                [controller.binaries / "ansible-inventory", "-i", config, "--graph"],
                "inventory plugin",
                allow_zero=True,
            )
            return name
    raise PublicReleaseVerificationError("no safe inventory runtime probe was discovered")


def _lookup_runtime_probe(controller: _Controller, lookups: dict[str, str]) -> str:
    """Load a documented lookup plugin using an explicitly non-secret field."""
    for name in lookups:
        doc = _plugin_documentation(controller, "lookup", name)
        options = doc.get("options")
        if not isinstance(options, dict):
            continue
        safe_option = None
        for option_name, option in options.items():
            choices = option.get("choices") if isinstance(option, dict) else None
            if (
                isinstance(option_name, str)
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", option_name)
                and isinstance(choices, list)
                and "region" in choices
            ):
                safe_option = option_name
                break
        terms = options.get("_terms")
        if safe_option is None or not isinstance(terms, dict) or terms.get("required") is not True:
            continue
        expression = f"{{{{ lookup({json.dumps(name)}, 'default', {safe_option}='region') }}}}"
        playbook = controller.work / "lookup-probe.yml"
        playbook.write_text(
            "---\n"
            "- hosts: localhost\n"
            "  gather_facts: false\n"
            "  tasks:\n"
            "    - ansible.builtin.debug:\n"
            f"        msg: {json.dumps(expression)}\n",
            encoding="utf-8",
        )
        _log(f"Running offline missing-profile lookup probe: {name}")
        _expect_missing_profile(
            controller,
            [controller.binaries / "ansible-playbook", playbook],
            "lookup plugin",
        )
        return name
    raise PublicReleaseVerificationError("no safe lookup runtime probe was discovered")


def _verify_profile_handoff(controller: _Controller, lookup_name: str) -> None:
    """Configure one offline CLI profile and read its region through Ansible."""
    _log(
        f"Running positive CLI-to-Ansible profile handoff with {lookup_name} "
        f"and region {_PROFILE_REGION}"
    )
    configure_controller = replace(
        controller,
        environment={
            **controller.environment,
            "SCCFM_API_TOKEN": _PROFILE_TOKEN,
        },
    )
    _run(
        configure_controller,
        [
            controller.binaries / "sccfm-cli",
            "configure",
            "--region",
            _PROFILE_REGION,
        ],
    )

    expression = f"{{{{ lookup({json.dumps(lookup_name)}, 'default', field='region') }}}}"
    playbook = controller.work / "profile-handoff.yml"
    playbook.write_text(
        "---\n"
        "- hosts: localhost\n"
        "  gather_facts: false\n"
        "  tasks:\n"
        "    - name: Verify CLI to Ansible profile handoff\n"
        "      ansible.builtin.assert:\n"
        "        that:\n"
        f"          - configured_region == {json.dumps(_PROFILE_REGION)}\n"
        "      vars:\n"
        f"        configured_region: {json.dumps(expression)}\n",
        encoding="utf-8",
    )
    _run(controller, [controller.binaries / "ansible-playbook", playbook])


def verify_public_release(requested: str = "") -> PublicReleaseSummary:
    """Install and smoke-test one matching release from the public registries."""
    version = resolve_public_version(requested)
    with tempfile.TemporaryDirectory(prefix="sccfm-public-release-") as temporary:
        _log("Creating an isolated controller with a clean home and collection path")
        controller = _create_controller(Path(temporary))
        _install_public_artifacts(controller, version)
        _log("Verifying CLI imports, entry points, help output, and exported schema")
        _verify_cli(controller, version)
        _log(f"Verified installed PyPI package version {version}")
        _log("Verifying the installed Ansible collection version")
        _verify_collection_version(controller, version)
        _log(f"Verified installed Ansible Galaxy collection version {version}")
        _log("Discovering public module, inventory, and lookup plugin surfaces")
        modules, inventory, lookups = _discover_plugins(controller)
        _validate_plugin_counts(modules, inventory, lookups)
        _log(
            f"Discovered modules={len(modules)} inventory={len(inventory)} "
            f"lookups={len(lookups)}"
        )
        probe = _documented_probe(controller, modules)
        _log(f"Running offline missing-profile module and syntax probes: {probe}")
        _offline_checks(controller, probe)
        inventory_probe = _inventory_runtime_probe(controller, inventory)
        lookup_probe = _lookup_runtime_probe(controller, lookups)
        _verify_profile_handoff(controller, lookup_probe)
    return PublicReleaseSummary(
        version=version,
        module_count=len(modules),
        inventory_count=len(inventory),
        lookup_count=len(lookups),
        offline_probe=probe,
        inventory_probe=inventory_probe,
        lookup_probe=lookup_probe,
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
        f"module_probe={summary.offline_probe} inventory_probe={summary.inventory_probe} "
        f"lookup_probe={summary.lookup_probe}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
