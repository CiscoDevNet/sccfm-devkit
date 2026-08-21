# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the public-registry release smoke harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import cisco_sccfm_scripts.verify_public_release as verifier

_VERSION = "1.2.3"


def _controller(tmp_path: Path) -> verifier._Controller:
    work = tmp_path / "work"
    work.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    collections = tmp_path / "collections"
    collections.mkdir()
    return verifier._Controller(work, collections, binaries, {})


def test_resolve_latest_requires_matching_registry_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: dict[str, object] = {
        verifier._PYPI_LATEST_URL: {"info": {"version": _VERSION}},
        verifier._GALAXY_LATEST_URL: {"highest_version": {"version": _VERSION}},
    }
    monkeypatch.setattr(verifier, "_fetch_json", responses.__getitem__)

    assert verifier.resolve_public_version() == _VERSION


def test_resolve_exact_version_uses_versioned_registry_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fetch(url: str) -> object:
        calls.append(url)
        if "pypi.org" in url:
            return {"info": {"version": _VERSION}}
        return {"version": _VERSION}

    monkeypatch.setattr(verifier, "_fetch_json", fetch)

    assert verifier.resolve_public_version(_VERSION) == _VERSION
    assert calls == [
        verifier._PYPI_VERSION_URL.format(version=_VERSION),
        verifier._GALAXY_VERSION_URL.format(version=_VERSION),
    ]


def test_resolve_rejects_invalid_version_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_fetch(url: str) -> object:
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr(verifier, "_fetch_json", unexpected_fetch)

    with pytest.raises(verifier.PublicReleaseVerificationError, match="stable X.Y.Z"):
        verifier.resolve_public_version("v1.2.3")


def test_resolve_rejects_registry_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    responses: dict[str, object] = {
        verifier._PYPI_LATEST_URL: {"info": {"version": _VERSION}},
        verifier._GALAXY_LATEST_URL: {"highest_version": {"version": "1.2.2"}},
    }
    monkeypatch.setattr(verifier, "_fetch_json", responses.__getitem__)

    with pytest.raises(verifier.PublicReleaseVerificationError, match="versions differ"):
        verifier.resolve_public_version()


def test_cli_schema_requires_safety_and_auth_metadata() -> None:
    schema = {
        "version": _VERSION,
        "commands": [
            {
                "path": ["status"],
                "command": "sccfm-cli status",
                "readonly": True,
                "auth": {"requires_profile": True, "requires_api_token": True},
                "options": [],
                "constraints": [],
            }
        ],
    }

    verifier._validate_cli_schema(schema, _VERSION)
    del schema["commands"][0]["readonly"]
    with pytest.raises(verifier.PublicReleaseVerificationError, match="metadata is incomplete"):
        verifier._validate_cli_schema(schema, _VERSION)


def test_inventory_probe_loads_documented_plugin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    plugin = "cisco.sccfm.dynamic"
    monkeypatch.setattr(
        verifier,
        "_plugin_documentation",
        lambda selected, plugin_type, name: {
            "options": {"plugin": {"required": True, "choices": [plugin]}}
        },
    )
    commands: list[list[str | Path]] = []
    monkeypatch.setattr(
        verifier,
        "_expect_missing_profile",
        lambda selected, command, surface, allow_zero: commands.append(command),
    )

    assert verifier._inventory_runtime_probe(controller, {plugin: "Load inventory"}) == plugin
    assert controller.work.joinpath("inventory.sccfm.yml").read_text() == (
        'plugin: "cisco.sccfm.dynamic"\n'
    )
    assert commands == [
        [
            controller.binaries / "ansible-inventory",
            "-i",
            controller.work / "inventory.sccfm.yml",
            "--graph",
        ]
    ]


def test_lookup_probe_requests_only_documented_region_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    plugin = "cisco.sccfm.profile"
    monkeypatch.setattr(
        verifier,
        "_plugin_documentation",
        lambda selected, plugin_type, name: {
            "options": {
                "_terms": {"required": True},
                "field": {"choices": ["region", "api_token"]},
            }
        },
    )
    commands: list[list[str | Path]] = []
    monkeypatch.setattr(
        verifier,
        "_expect_missing_profile",
        lambda selected, command, surface: commands.append(command),
    )

    assert verifier._lookup_runtime_probe(controller, {plugin: "Read profile"}) == plugin
    playbook = controller.work.joinpath("lookup-probe.yml").read_text(encoding="utf-8")
    assert "field='region'" in playbook
    assert "api_token" not in playbook
    assert commands == [
        [controller.binaries / "ansible-playbook", controller.work / "lookup-probe.yml"]
    ]


def test_missing_profile_probe_rejects_other_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    monkeypatch.setattr(
        verifier,
        "_run",
        lambda selected, command, check: subprocess.CompletedProcess(command, 2, "", "other"),
    )

    with pytest.raises(verifier.PublicReleaseVerificationError, match="lookup plugin"):
        verifier._expect_missing_profile(controller, ["ansible-playbook"], "lookup plugin")


def test_missing_profile_probe_accepts_inventory_warning_with_zero_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    monkeypatch.setattr(
        verifier,
        "_run",
        lambda selected, command, check: subprocess.CompletedProcess(
            command,
            0,
            "",
            "SCCFM profile 'default' not found",
        ),
    )

    verifier._expect_missing_profile(
        controller,
        ["ansible-inventory"],
        "inventory plugin",
        allow_zero=True,
    )


def test_main_writes_machine_readable_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "reports" / "summary.json"
    summary = verifier.PublicReleaseSummary(
        _VERSION,
        49,
        1,
        1,
        "cisco.sccfm.list_devices",
        "cisco.sccfm.sccfm",
        "cisco.sccfm.profile",
    )
    monkeypatch.setattr(verifier, "verify_public_release", lambda requested: summary)

    assert verifier.main(["--version", _VERSION, "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8")) == {
        "inventory_count": 1,
        "inventory_probe": "cisco.sccfm.sccfm",
        "lookup_count": 1,
        "lookup_probe": "cisco.sccfm.profile",
        "module_count": 49,
        "offline_probe": "cisco.sccfm.list_devices",
        "version": _VERSION,
    }
