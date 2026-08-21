# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the public-registry release smoke harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import cisco_sccfm_scripts.verify_public_release as verifier

_VERSION = "1.2.3"


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


def test_main_writes_machine_readable_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "reports" / "summary.json"
    summary = verifier.PublicReleaseSummary(_VERSION, 49, 1, 1, "cisco.sccfm.list_devices")
    monkeypatch.setattr(verifier, "verify_public_release", lambda requested: summary)

    assert verifier.main(["--version", _VERSION, "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8")) == {
        "inventory_count": 1,
        "lookup_count": 1,
        "module_count": 49,
        "offline_probe": "cisco.sccfm.list_devices",
        "version": _VERSION,
    }
