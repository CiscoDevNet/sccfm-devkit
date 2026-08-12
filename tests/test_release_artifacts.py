# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the immutable release artifact manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cisco_sccfm_scripts.release_artifacts import (
    ReleaseArtifactError,
    create_release_manifest,
    verify_release_bundle,
)

_VERSION = "1.2.3"
_TAG = "v1.2.3"
_COMMIT = "a" * 40
_ARTIFACTS = {
    "cisco-sccfm-1.2.3.tar.gz": b"collection",
    "cisco_sccfm_devkit-1.2.3-py3-none-any.whl": b"wheel",
    "cisco_sccfm_devkit-1.2.3.tar.gz": b"sdist",
}


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "release"
    bundle.mkdir()
    for filename, content in _ARTIFACTS.items():
        (bundle / filename).write_bytes(content)
    return bundle


def _create(tmp_path: Path) -> Path:
    bundle = _bundle(tmp_path)
    create_release_manifest(bundle, _VERSION, _TAG, _COMMIT)
    return bundle


def _manifest(bundle: Path) -> dict[str, Any]:
    value: object = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_create_and_verify_release_bundle(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    created = create_release_manifest(bundle, _VERSION, _TAG, _COMMIT)
    verified = verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)

    assert created == verified
    assert verified.version == _VERSION
    assert verified.artifact_count == 3
    manifest = _manifest(bundle)
    assert manifest["source_commit"] == _COMMIT
    assert [entry["filename"] for entry in manifest["artifacts"]] == sorted(_ARTIFACTS)


def test_create_rejects_missing_or_extra_artifacts(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ReleaseArtifactError, match="exactly the three artifacts"):
        create_release_manifest(bundle, _VERSION, _TAG, _COMMIT)


def test_create_never_overwrites_a_manifest(tmp_path: Path) -> None:
    bundle = _create(tmp_path)

    with pytest.raises(ReleaseArtifactError, match="manifest already exists"):
        create_release_manifest(bundle, _VERSION, _TAG, _COMMIT)


@pytest.mark.parametrize(
    ("version", "tag", "commit", "message"),
    [
        ("not/a/version", "vnot/a/version", _COMMIT, "version is invalid"),
        ("01.2.3", "v01.2.3", _COMMIT, "version is invalid"),
        ("1.2.3rc1", "v1.2.3rc1", _COMMIT, "version is invalid"),
        (_VERSION, "v9.9.9", _COMMIT, "tag does not match"),
        (_VERSION, _TAG, "not-a-commit", "source commit"),
    ],
)
def test_identity_must_be_canonical(
    tmp_path: Path,
    version: str,
    tag: str,
    commit: str,
    message: str,
) -> None:
    bundle = _bundle(tmp_path)

    with pytest.raises(ReleaseArtifactError, match=message):
        create_release_manifest(bundle, version, tag, commit)


def test_verify_rejects_tampered_artifact_without_exposing_content(tmp_path: Path) -> None:
    bundle = _create(tmp_path)
    sentinel = "REL001-SECRET-SENTINEL"
    artifact = bundle / "cisco_sccfm_devkit-1.2.3-py3-none-any.whl"
    artifact.write_text(sentinel, encoding="utf-8")

    with pytest.raises(ReleaseArtifactError) as error:
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)

    assert sentinel not in str(error.value)


@pytest.mark.parametrize("field", ["project", "version", "tag", "source_commit"])
def test_verify_rejects_manifest_identity_changes(tmp_path: Path, field: str) -> None:
    bundle = _create(tmp_path)
    manifest = _manifest(bundle)
    manifest[field] = "changed"
    (bundle / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReleaseArtifactError, match="does not match|unexpected project"):
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)


def test_verify_rejects_unknown_manifest_fields(tmp_path: Path) -> None:
    bundle = _create(tmp_path)
    manifest = _manifest(bundle)
    manifest["unknown"] = True
    (bundle / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReleaseArtifactError, match="top-level fields"):
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)


@pytest.mark.parametrize("schema_version", [True, 1.0])
def test_verify_requires_integer_schema_version(tmp_path: Path, schema_version: object) -> None:
    bundle = _create(tmp_path)
    manifest = _manifest(bundle)
    manifest["schema_version"] = schema_version
    (bundle / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReleaseArtifactError, match="unsupported schema version"):
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)


def test_verify_normalizes_json_integer_limit_errors(tmp_path: Path) -> None:
    bundle = _create(tmp_path)
    manifest_path = bundle / "release-manifest.json"
    raw = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(raw.replace('"schema_version": 1', '"schema_version": ' + "9" * 5000))

    with pytest.raises(ReleaseArtifactError, match="not valid JSON"):
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)


def test_verify_rejects_duplicate_manifest_keys(tmp_path: Path) -> None:
    bundle = _create(tmp_path)
    manifest_path = bundle / "release-manifest.json"
    raw = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(raw.replace('"project":', '"project": "duplicate",\n  "project":'))

    with pytest.raises(ReleaseArtifactError, match="duplicate JSON key"):
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)


def test_verify_rejects_symlinked_artifact(tmp_path: Path) -> None:
    bundle = _create(tmp_path)
    artifact = bundle / "cisco-sccfm-1.2.3.tar.gz"
    target = tmp_path / "outside.tar.gz"
    target.write_bytes(artifact.read_bytes())
    artifact.unlink()
    artifact.symlink_to(target)

    with pytest.raises(ReleaseArtifactError, match="regular file"):
        verify_release_bundle(bundle, _VERSION, _TAG, _COMMIT)


def test_workflows_promote_release_assets_without_rebuilding() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (repository / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "  release:\n" not in ci
    assert "  publish-to-pypi:\n" not in ci
    assert "  publish-to-galaxy:\n" not in ci
    assert "workflow_dispatch:" in release
    assert "release:\n    types:" not in release
    assert release.count("${{ inputs.version }}") == 1
    assert "RELEASE_VERSION: ${{ inputs.version }}" in release

    build = release.split("  build-release:\n", maxsplit=1)[1].split(
        "  create-draft-release:\n", maxsplit=1
    )[0]
    draft = release.split("  create-draft-release:\n", maxsplit=1)[1].split(
        "  publish-to-pypi:\n", maxsplit=1
    )[0]
    pypi = release.split("  publish-to-pypi:\n", maxsplit=1)[1].split(
        "  publish-to-galaxy:\n", maxsplit=1
    )[0]
    galaxy = release.split("  publish-to-galaxy:\n", maxsplit=1)[1].split(
        "  publish-github-release:\n", maxsplit=1
    )[0]
    finalizer = release.split("  publish-github-release:\n", maxsplit=1)[1]

    assert build.count("poetry build") == 1
    assert build.count("poetry run build-ansible-collection") == 1
    assert "release_artifacts create" in build
    assert "release-manifest.json" in build
    assert "python -m zipfile -e" in build
    assert build.count("pip-audit \\") == 1
    assert build.count("verify_python_distribution \\") == 2
    assert 'steps.artifacts.outputs.wheel_path }}" wheel' in build
    assert 'steps.artifacts.outputs.sdist_path }}" sdist' in build
    assert "git push --atomic" in build

    assert "gh release create" in draft
    assert "--draft" in draft
    assert "release_artifacts verify" in draft
    for publisher in (pypi, galaxy):
        assert "actions/download-artifact" in publisher
        assert "release_artifacts verify" in publisher
        assert "python -m build" not in publisher
        assert "poetry build" not in publisher
        assert "build-ansible-collection" not in publisher

    assert "environment: pypi" in pypi
    assert "pypa/gh-action-pypi-publish" in pypi
    assert "skip-existing: true" in pypi
    assert "- publish-to-pypi" in galaxy
    assert "environment: ansible-galaxy" in galaxy
    assert "ansible-galaxy collection publish" in galaxy
    assert "--import-timeout 600" in galaxy
    assert "--no-wait" not in galaxy
    assert "- publish-to-galaxy" in finalizer
    assert "--draft=false" in finalizer
