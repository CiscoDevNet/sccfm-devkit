# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the immutable release artifact manifest."""

from __future__ import annotations

import json
import re
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


def _workflow_job(source: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n.*?(?=^  [a-z0-9-]+:\n|\Z)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"workflow job {name!r} is missing"
    return match.group(0)


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


def test_workflows_separate_automatic_preparation_from_manual_deployment() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (repository / ".github/workflows/release.yml").read_text(encoding="utf-8")

    prepare = _workflow_job(ci, "prepare-release")
    draft = _workflow_job(ci, "create-draft-release")
    validation = _workflow_job(release, "validate-release")
    pypi = _workflow_job(release, "publish-to-pypi")
    galaxy = _workflow_job(release, "publish-to-galaxy")
    finalizer = _workflow_job(release, "publish-github-release")

    assert "needs: lint-and-test" in prepare
    assert "github.event_name == 'push'" in prepare
    assert "github.event_name == 'pull_request'" in prepare
    assert "github.ref == 'refs/heads/main'" in prepare
    assert "production-release" in ci
    assert "cancel-in-progress: false" in ci
    assert "  publish-to-pypi:\n" not in ci
    assert "  publish-to-galaxy:\n" not in ci
    assert "pypa/gh-action-pypi-publish" not in ci
    assert "ansible-galaxy collection publish" not in ci
    assert "secrets.PYPI_API_TOKEN" not in ci
    assert "secrets.GALAXY_API_KEY" not in ci
    assert "secrets.SCCFM_CI_DEPLOY_KEY" in prepare
    assert "contents: read" in prepare
    assert "contents: write" not in prepare

    assert prepare.count("poetry build") == 1
    assert prepare.count("poetry run build-ansible-collection") == 1
    assert "release_artifacts create" in prepare
    assert 'git tag -a "${{ steps.version.outputs.tag }}"' in prepare
    assert "release-manifest-sha256:" in prepare
    assert "release-manifest.json" in prepare
    assert "python -m zipfile -e" in prepare
    assert prepare.count("pip-audit \\") == 1
    assert prepare.count("verify_python_distribution \\") == 2
    assert 'steps.artifacts.outputs.wheel_path }}" wheel' in prepare
    assert 'steps.artifacts.outputs.sdist_path }}" sdist' in prepare
    assert 'local smoke_interactive="${smoke_root}/venv/bin/sccfm-cli-interactive"' in prepare
    assert '"sccfm-cli-interactive": "cisco_sccfm_cli.interactive:main"' in prepare
    assert '"${smoke_interactive}" --help >/dev/null' in prepare
    assert "git push --atomic" in prepare
    assert "actions/upload-artifact" in prepare

    assert "needs: prepare-release" in draft
    assert "actions/download-artifact" in draft
    assert "gh release create" in draft
    assert "--verify-tag" in draft
    assert "--draft" in draft
    assert "release_artifacts verify" in draft

    assert "workflow_dispatch:" in release
    assert "release:\n    types:" not in release
    assert release.count("${{ inputs.version }}") == 1
    assert "REQUESTED_RELEASE: ${{ inputs.version }}" in validation
    assert "production-release" in release
    assert "cancel-in-progress: false" in release
    assert 'test "${GITHUB_REPOSITORY}" = "CiscoDevNet/sccfm-devkit"' in validation
    assert 'test "${GITHUB_REF}" = "refs/heads/main"' in validation
    assert "must identify an existing stable GitHub release" in validation
    assert 'git rev-parse "refs/tags/${RELEASE_TAG}^{commit}"' in validation
    assert "release-manifest-sha256:" in validation
    assert "release_artifacts verify" in validation

    prohibited_deploy_commands = (
        "poetry build",
        "python -m build",
        "build-ansible-collection",
        "cz bump",
        "git commit ",
        "git tag ",
        "git push ",
        "actions/upload-artifact",
        "actions/download-artifact",
        "SCCFM_CI_DEPLOY_KEY",
    )
    for command in prohibited_deploy_commands:
        assert command not in release

    for job in (validation, pypi, galaxy, finalizer):
        assert 'gh release download "${RELEASE_TAG}"' in job
        assert "release_artifacts verify" in job

    assert "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33" in pypi
    assert "pypa/gh-action-pypi-publish@release/v1" not in pypi
    assert "secrets.PYPI_API_TOKEN" in pypi
    assert '"${INSTALL_ROOT}/venv/bin/sccfm-cli-interactive" --help >/dev/null' in pypi
    assert "skip-existing:" not in pypi
    assert 'MISSING_FILES="${PYPI_VERIFICATION##* missing=}"' in pypi
    assert 'test "$(find dist -mindepth 1 -maxdepth 1 -type f' in pypi
    assert '2)\n              cp "${WHEEL_PATH}" "${SDIST_PATH}" dist/' in pypi
    assert "3)\n              MISSING_FILES=" in pypi
    assert (
        'cp "${WHEEL_PATH}" "${SDIST_PATH}" dist/'
        not in pypi.split("3)\n              MISSING_FILES=", maxsplit=1)[1]
    )

    assert "- publish-to-pypi" in galaxy
    assert "secrets.GALAXY_API_KEY" in galaxy
    assert "ansible-galaxy collection publish" in galaxy
    assert "--import-timeout 600" in galaxy
    assert "--no-wait" not in galaxy
    assert "- publish-to-galaxy" in finalizer
    assert "--draft=false" in finalizer
    assert "--latest=false" in finalizer
    assert "DEP002_EXCEPTION_EXPIRES" not in ci
    assert "DEP002_EXCEPTION_EXPIRES" not in release
    assert "exceptions expired" not in ci
    assert "exceptions expired" not in release
    assert ci.count("--ignore-vuln PYSEC-2026-") == 6
    assert "--ignore-vuln PYSEC-2026-" not in release
    assert "\n    environment:" not in release
    assert "\n    environment:" not in ci


def test_ci_refreshes_metadata_after_inferred_files_only_bump() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    synchronization = ci.split("      - name: Infer and synchronize release version\n", maxsplit=1)[
        1
    ].split("      - name: Build release artifacts once\n", maxsplit=1)[0]

    inference = synchronization.index("poetry run cz bump --get-next")
    bump = synchronization.index("poetry run cz bump --yes --changelog --files-only")
    reinstall = synchronization.index("poetry install --only-root --no-interaction")
    metadata_check = synchronization.index('test "${INSTALLED_VERSION}" = "${RELEASE_VERSION}"')

    assert inference < bump < reinstall < metadata_check
    assert 'version("cisco-sccfm-devkit")' in synchronization


def test_ci_release_changed_path_validation_reads_tracked_and_untracked_paths() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    commit_step = ci.split("      - name: Commit verified source\n", maxsplit=1)[1].split(
        "      - name: Create and verify release manifest\n", maxsplit=1
    )[0]

    validation = re.compile(
        r"while IFS= read -r changed_path; do.*?done < <\(\s*\{\s*"
        r"git diff --name-only\s*git ls-files --others --exclude-standard\s*"
        r"\} \| sort -u\s*\)",
        re.DOTALL,
    )
    assert validation.search(commit_step) is not None
    assert re.search(r"\} \| sort -u \| while", commit_step) is None
    paired_runtime = "sccfm-ansible/plugins/module_utils/dependencies.py"
    assert paired_runtime in commit_step
    assert re.search(rf"git add .*?{re.escape(paired_runtime)}", commit_step, re.DOTALL)


def test_draft_release_and_registry_retries_are_manifest_bound() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (repository / ".github/workflows/release.yml").read_text(encoding="utf-8")
    draft = _workflow_job(ci, "create-draft-release")
    prepare = _workflow_job(ci, "prepare-release")
    pypi = _workflow_job(release, "publish-to-pypi")
    galaxy = _workflow_job(release, "publish-to-galaxy")

    assert "actions: read" in prepare
    assert '[[ "${GITHUB_RUN_ATTEMPT}" -gt 1' in prepare
    assert 'test "$(git rev-parse "${RECOVERY_SOURCE}^")" = "${GITHUB_SHA}"' in prepare
    assert "actions/runs/${GITHUB_RUN_ID}/artifacts" in prepare
    assert 'gh run download "${GITHUB_RUN_ID}"' in prepare
    assert "release_artifacts verify" in prepare
    assert "RECOVERY_TAG_MESSAGE" in prepare
    assert "release-manifest-sha256:" in prepare
    assert "expected one unexpired manifest-bound bundle" in prepare
    assert "steps.source.outputs.source_commit || steps.version.outputs.source_commit" in prepare
    assert "steps.source.outputs.bundle_name || steps.version.outputs.bundle_name" in prepare

    assert "gh release view" in draft
    assert 'cmp -s "${local_asset}" "${existing_root}/${asset_name}"' in draft
    assert "gh release upload" in draft
    assert draft.count('gh release download "${RELEASE_TAG}"') == 2
    assert draft.count("release_artifacts verify") == 2

    assert "verify_pypi_release" in pypi
    assert 'case "${PYPI_STATUS}" in' in pypi
    assert re.search(r"\n\s+0\)\n\s+echo \"publish=false\"", pypi) is not None
    assert re.search(r"\n\s+2\)\n.*?echo \"publish=true\"", pypi, re.DOTALL) is not None
    assert re.search(r"\n\s+3\)\n.*?echo \"publish=true\"", pypi, re.DOTALL) is not None

    assert 'case "${HTTP_STATUS}" in' in galaxy
    assert "200)" in galaxy
    assert "jq -er '.artifact.sha256'" in galaxy
    assert 'echo "publish=false"' in galaxy
    assert '404) echo "publish=true"' in galaxy


def test_ci_release_push_reconciles_an_accepted_remote_update() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    push = ci.split("      - name: Push release commit and tag atomically\n", maxsplit=1)[1].split(
        "\n  create-draft-release:\n", maxsplit=1
    )[0]

    assert 'PUSH_REMOTE="git@github.com:${GITHUB_REPOSITORY}.git"' in push
    assert 'git push --atomic "${PUSH_REMOTE}"' in push
    assert "refs/heads/main:refs/remotes/origin/main" in push
    assert '[[ "$(git rev-parse "refs/tags/${RELEASE_TAG}^{commit}")"' in push
    assert "git merge-base --is-ancestor \\" in push
    assert '"${SOURCE_COMMIT}" refs/remotes/origin/main' in push
    assert "the atomic remote update was verified" in push


def test_release_workflows_limit_deploy_key_to_push_steps() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (repository / ".github/workflows/release.yml").read_text(encoding="utf-8")
    generated_docs = (repository / ".github/workflows/generated-docs.yml").read_text(
        encoding="utf-8"
    )
    prepare = _workflow_job(ci, "prepare-release")

    for workflow in (ci, release, generated_docs):
        assert workflow.count("uses: actions/checkout@v7") == workflow.count(
            "persist-credentials: false"
        )

    prepare_before_push, prepare_push = prepare.split(
        "      - name: Push release commit and tag atomically\n", maxsplit=1
    )
    assert "persist-credentials: false" in prepare_before_push
    assert "ssh-key:" not in prepare_before_push
    assert "SCCFM_CI_DEPLOY_KEY" not in prepare_before_push
    assert prepare_push.count("secrets.SCCFM_CI_DEPLOY_KEY") == 1
    assert 'chmod 600 "${DEPLOY_KEY_PATH}"' in prepare_push
    assert "trap cleanup_ssh EXIT" in prepare_push
    assert "unset SCCFM_CI_DEPLOY_KEY" in prepare_push
    assert "https://api.github.com/meta" in prepare_push
    assert "StrictHostKeyChecking=yes" in prepare_push

    docs_before_push, docs_push = generated_docs.split(
        "      - name: Push generated docs\n", maxsplit=1
    )
    assert "persist-credentials: false" in docs_before_push
    assert "permissions:\n  contents: read" in docs_before_push
    assert "ssh-key:" not in docs_before_push
    assert "SCCFM_CI_DEPLOY_KEY" not in docs_before_push
    assert docs_push.count("secrets.SCCFM_CI_DEPLOY_KEY") == 1
    assert 'chmod 600 "${DEPLOY_KEY_PATH}"' in docs_push
    assert "trap cleanup_ssh EXIT" in docs_push
    assert "unset SCCFM_CI_DEPLOY_KEY" in docs_push
    assert "StrictHostKeyChecking=yes" in docs_push


def test_ci_runs_pinned_workflow_lints_and_a_no_push_release_rehearsal() -> None:
    repository = Path(__file__).resolve().parents[1]
    ci = (repository / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    prepare = _workflow_job(ci, "prepare-release")
    draft = _workflow_job(ci, "create-draft-release")

    assert "shellcheck-py==0.11.0.1" in ci
    assert "github.com/rhysd/actionlint/cmd/actionlint@v1.7.12" in ci
    assert "SHELLCHECK_OPTS: --severity=warning" in ci
    assert '-shellcheck "$(command -v shellcheck)"' in ci
    assert "go install github.com/zricethezav/gitleaks/v8@v8.30.1" in prepare
    assert "go install github.com/gitleaks/gitleaks/v8@v8.30.1" not in prepare

    assert "github.event_name == 'pull_request'" in prepare
    assert 'git commit --allow-empty -m "fix: rehearse release preparation"' in prepare
    assert "poetry run cz bump --get-next" in prepare
    assert "poetry run cz bump --yes --changelog --files-only" in prepare
    assert "prepare_ansible_release" in prepare
    assert "poetry run generate-cli-docs" in prepare
    assert "poetry run generate-cli-man-docs" in prepare
    assert "poetry run generate-ansible-docs" in prepare
    assert "poetry run build-ansible-collection" in prepare
    assert "poetry build" in prepare
    assert "verify_python_artifacts" in prepare
    assert "verify_ansible_collection" in prepare
    assert 'git commit -m "bump: version ${RELEASE_VERSION}"' in prepare
    assert "release_artifacts create" in prepare
    assert 'git tag -a "${{ steps.version.outputs.tag }}"' in prepare
    assert "Complete credential-free release rehearsal" in prepare
    assert "without uploading or pushing" in prepare

    preserve = prepare.split("      - name: Preserve exact release bundle\n", maxsplit=1)[1]
    preserve = preserve.split("      - name: Push release commit", maxsplit=1)[0]
    push = prepare.split("      - name: Push release commit and tag atomically\n", maxsplit=1)[1]
    push = push.split("      - name: Complete credential-free", maxsplit=1)[0]
    assert "github.event_name == 'push'" in preserve
    assert "github.event_name == 'push'" in push
    assert "github.event_name == 'push'" in draft
