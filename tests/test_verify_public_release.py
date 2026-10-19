# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the public-registry release smoke harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

import cisco_sccfm_scripts.verify_public_release as verifier

_VERSION = "1.2.3"


class _JsonResponse:
    def __init__(self, url: str, payload: bytes) -> None:
        self._url = url
        self._payload = payload

    def geturl(self) -> str:
        return self._url

    def read(self, limit: int) -> bytes:
        return self._payload[:limit]


def _controller(tmp_path: Path) -> verifier._Controller:
    work = tmp_path / "work"
    work.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    collections = tmp_path / "collections"
    collections.mkdir()
    return verifier._Controller(work, collections, binaries, {})


def test_module_imports_without_site_packages() -> None:
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import cisco_sccfm_scripts.verify_public_release"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_registry_json_rejects_duplicate_keys() -> None:
    response = _JsonResponse(verifier._PYPI_LATEST_URL, b'{"version":"1","version":"2"}')

    with pytest.raises(verifier.PublicReleaseVerificationError, match="duplicate JSON key"):
        verifier._read_json(response, verifier._PYPI_LATEST_URL)


def test_registry_http_error_identifies_service_and_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = verifier._GALAXY_VERSION_URL.format(version=_VERSION)

    def fail(request: object, timeout: float) -> object:
        raise HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(verifier, "urlopen", fail)

    with pytest.raises(
        verifier.PublicReleaseVerificationError,
        match=r"Ansible Galaxy returned HTTP 404",
    ):
        verifier._fetch_json(url)


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


def test_plugin_count_floor_rejects_incomplete_collection() -> None:
    modules = {f"cisco.sccfm.module_{index}": "List item" for index in range(48)}

    with pytest.raises(verifier.PublicReleaseVerificationError, match="fewer plugins"):
        verifier._validate_plugin_counts(
            modules,
            {"cisco.sccfm.inventory": "Inventory"},
            {"cisco.sccfm.lookup": "Lookup"},
        )


def test_documented_probe_uses_first_argument_free_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    modules = {
        "cisco.sccfm.list_required": "List required items",
        "cisco.sccfm.list_safe": "List safe items",
    }
    documentation = {
        "cisco.sccfm.list_required": {"options": {"device": {"required": True}}},
        "cisco.sccfm.list_safe": {"options": {}},
    }
    monkeypatch.setattr(
        verifier,
        "_plugin_documentation",
        lambda selected, plugin_type, name: documentation[name],
    )

    assert verifier._documented_probe(controller, modules) == "cisco.sccfm.list_safe"


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
    assert 'lookup(\\"cisco.sccfm.profile\\"' in playbook
    assert "field='region'" in playbook
    assert "api_token" not in playbook
    assert commands == [
        [controller.binaries / "ansible-playbook", controller.work / "lookup-probe.yml"]
    ]


def test_profile_handoff_configures_offline_and_asserts_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    plugin = "cisco.sccfm.profile"
    calls: list[tuple[verifier._Controller, list[str | Path]]] = []

    def run(
        selected: verifier._Controller,
        command: list[str | Path],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((selected, command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(verifier, "_run", run)

    verifier._verify_profile_handoff(controller, plugin)

    configure_controller, configure_command = calls[0]
    assert configure_command == [
        controller.binaries / "sccfm-cli",
        "configure",
        "--region",
        "int",
    ]
    assert "SCCFM_API_TOKEN" not in controller.environment
    assert configure_controller.environment["SCCFM_API_TOKEN"] == verifier._PROFILE_TOKEN
    assert verifier._PROFILE_TOKEN not in " ".join(str(part) for part in configure_command)

    playbook = controller.work.joinpath("profile-handoff.yml")
    assert calls[1] == (
        controller,
        [controller.binaries / "ansible-playbook", playbook],
    )
    rendered = playbook.read_text(encoding="utf-8")
    assert 'lookup(\\"cisco.sccfm.profile\\"' in rendered
    assert 'configured_region == "int"' in rendered
    assert verifier._PROFILE_TOKEN not in rendered


def test_public_install_logs_both_registry_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _controller(tmp_path)
    monkeypatch.setattr(
        verifier,
        "_run",
        lambda selected, command: subprocess.CompletedProcess(command, 0, "", ""),
    )

    verifier._install_public_artifacts(controller, _VERSION)

    output = capsys.readouterr().out
    assert f"Installing cisco-sccfm-devkit=={_VERSION} from public PyPI" in output
    assert f"Installed cisco.sccfm:=={_VERSION} from Ansible Galaxy" in output


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
