# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from cisco_sccfm_scripts.build_ansible_collection import _find_collection_symlink
from cisco_sccfm_scripts.verify_ansible_collection import (
    ArtifactVerificationError,
    verify_collection_artifact,
)

_VERSION = "1.2.3"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_COLLECTION_SOURCE = _REPOSITORY_ROOT / "sccfm-ansible"
_COLLECTION_METADATA = yaml.safe_load((_COLLECTION_SOURCE / "galaxy.yml").read_text())
_COLLECTION_VERSION = str(_COLLECTION_METADATA["version"])

_MINIMUM_DIRECTORIES = {
    "changelogs",
    "examples",
    "examples/group_vars",
    "examples/group_vars/all",
    "meta",
    "plugins",
    "plugins/inventory",
    "plugins/module_utils",
    "plugins/modules",
    "tests",
    "tests/sanity",
}
_MINIMUM_FILES = {
    "CHANGELOG.rst": b"Cisco SCCFM Collection Release Notes\n",
    "LICENSE": b"Apache License\nVersion 2.0, January 2004\n",
    "README.md": b"# Test collection\n",
    "__init__.py": b"",
    "changelogs/changelog.yaml": b"---\nancestor: null\nreleases: {}\n",
    "changelogs/config.yaml": b"---\ntitle: Cisco SCCFM Collection\n",
    "examples/.vault_pass.example": b"replace-me\n",
    "examples/group_vars/all/vault.yml.example": (b"---\nvault_sccfm_api_token: placeholder\n"),
    "examples/show_devices.yml": b"---\n- name: Synthetic example\n  hosts: localhost\n",
    "meta/execution-environment.yml": b"---\ndependencies:\n  python: requirements.txt\n",
    "meta/runtime.yml": b"requires_ansible: '>=2.20.0,<2.22.0'\n",
    "requirements.txt": f"cisco-sccfm-devkit=={_VERSION}\n".encode(),
    "tests/sanity/ignore-2.20.txt": (
        b"plugins/modules/example.py validate-modules:missing-gplv3-license\n"
    ),
    "tests/sanity/ignore-2.21.txt": (
        b"plugins/modules/example.py validate-modules:missing-gplv3-license\n"
    ),
}


def _manifest_entry(name: str, content: bytes | None) -> dict[str, Any]:
    if content is None:
        return {"name": name, "ftype": "dir"}
    return {
        "name": name,
        "ftype": "file",
        "chksum_type": "sha256",
        "chksum_sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_tar_member(archive: tarfile.TarFile, name: str, content: bytes | None) -> None:
    member = tarfile.TarInfo(name)
    member.uid = 0
    member.gid = 0
    member.uname = ""
    member.gname = ""
    if content is None:
        member.type = tarfile.DIRTYPE
        member.mode = 0o755
        archive.addfile(member)
        return
    member.mode = 0o644
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def _build_synthetic_artifact(
    tmp_path: Path,
    *,
    extra_files: dict[str, bytes] | None = None,
    tamper_files_checksum: bool = False,
) -> Path:
    directories = set(_MINIMUM_DIRECTORIES)
    files = dict(_MINIMUM_FILES)
    files.update(extra_files or {})

    file_entries = [
        *(_manifest_entry(name, None) for name in sorted(directories)),
        *(_manifest_entry(name, content) for name, content in sorted(files.items())),
    ]
    files_manifest = {"format": 1, "files": file_entries}
    files_raw = json.dumps(files_manifest, indent=2).encode()
    files_digest = hashlib.sha256(files_raw).hexdigest()
    if tamper_files_checksum:
        files_digest = "0" * 64
    manifest = {
        "collection_info": {
            "namespace": "cisco",
            "name": "sccfm",
            "version": _VERSION,
        },
        "file_manifest_file": {
            "name": "FILES.json",
            "ftype": "file",
            "chksum_type": "sha256",
            "chksum_sha256": files_digest,
            "format": 1,
        },
        "format": 1,
    }
    manifest_raw = json.dumps(manifest, indent=2).encode()

    artifact = tmp_path / f"cisco-sccfm-{_VERSION}.tar.gz"
    with tarfile.open(artifact, mode="w:gz") as archive:
        _write_tar_member(archive, "MANIFEST.json", manifest_raw)
        _write_tar_member(archive, "FILES.json", files_raw)
        for name in sorted(directories):
            _write_tar_member(archive, name, None)
        for name, content in sorted(files.items()):
            _write_tar_member(archive, name, content)
    return artifact


def test_verifier_accepts_valid_collection(tmp_path: Path) -> None:
    artifact = _build_synthetic_artifact(tmp_path)

    result = verify_collection_artifact(artifact, expected_version=_VERSION)

    assert result.sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert result.file_count == len(_MINIMUM_FILES) + 2
    assert result.uncompressed_bytes > 0


@pytest.mark.parametrize(
    "path",
    [
        "examples/.vault_pass",
        "examples/.vault_pass_new",
        "examples/group_vars/all/vault.yml",
        "examples/.env",
        "examples/.env.production",
        "examples/.envrc",
        "examples/token.txt",
        "examples/id_rsa",
        "examples/id_ed25519.pub",
        "examples/private.pem",
        "examples/local.sqlite3",
        "examples/SECRETS.YML",
    ],
)
def test_verifier_rejects_sensitive_paths(tmp_path: Path, path: str) -> None:
    artifact = _build_synthetic_artifact(tmp_path, extra_files={path: b"synthetic\n"})

    with pytest.raises(ArtifactVerificationError):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_verifier_rejects_unreviewed_test_content(tmp_path: Path) -> None:
    artifact = _build_synthetic_artifact(
        tmp_path,
        extra_files={"tests/unit/test_live_tenant.py": b"synthetic\n"},
    )

    with pytest.raises(ArtifactVerificationError, match="unreviewed test policy"):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_verifier_rejects_secret_content_without_echoing_it(tmp_path: Path) -> None:
    synthetic_secret = b"eyJ" + b"a" * 12 + b"." + b"b" * 12 + b"." + b"c" * 12
    artifact = _build_synthetic_artifact(
        tmp_path,
        extra_files={"examples/show_devices.yml": synthetic_secret},
    )

    with pytest.raises(ArtifactVerificationError) as error:
        verify_collection_artifact(artifact, expected_version=_VERSION)

    assert synthetic_secret.decode() not in str(error.value)
    assert "JWT-like token" in str(error.value)


def test_verifier_rejects_private_key_content(tmp_path: Path) -> None:
    marker = b"-----BEGIN " + b"PRIVATE KEY-----\nsynthetic\n"
    artifact = _build_synthetic_artifact(
        tmp_path,
        extra_files={"examples/show_devices.yml": marker},
    )

    with pytest.raises(ArtifactVerificationError, match="private key"):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_verifier_rejects_manifest_checksum_mismatch(tmp_path: Path) -> None:
    artifact = _build_synthetic_artifact(tmp_path, tamper_files_checksum=True)

    with pytest.raises(ArtifactVerificationError, match="FILES.json checksum"):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_verifier_rejects_wrong_license_content(tmp_path: Path) -> None:
    artifact = _build_synthetic_artifact(
        tmp_path,
        extra_files={"LICENSE": b"Not the declared license\n"},
    )

    with pytest.raises(ArtifactVerificationError, match="Apache-2.0"):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_verifier_rejects_mismatched_python_package_version(tmp_path: Path) -> None:
    artifact = _build_synthetic_artifact(
        tmp_path,
        extra_files={"requirements.txt": b"cisco-sccfm-devkit==9.9.9\n"},
    )

    with pytest.raises(ArtifactVerificationError, match="version-matched Python package"):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_verifier_rejects_wrong_execution_environment_requirement_path(tmp_path: Path) -> None:
    artifact = _build_synthetic_artifact(
        tmp_path,
        extra_files={
            "meta/execution-environment.yml": b"---\ndependencies:\n  python: other.txt\n"
        },
    )

    with pytest.raises(ArtifactVerificationError, match="does not reference requirements.txt"):
        verify_collection_artifact(artifact, expected_version=_VERSION)


def test_builder_detects_collection_source_symlink(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    examples = collection / "examples"
    examples.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("harmless sentinel\n")
    link = examples / "linked.txt"
    link.symlink_to(outside)

    assert _find_collection_symlink(collection) == Path("examples/linked.txt")


def _ignore_sensitive_source_paths(directory: str, names: list[str]) -> set[str]:
    """Keep real local credential paths out of the temporary test copy."""
    relative_directory = Path(directory).resolve().relative_to(_COLLECTION_SOURCE.resolve())
    ignored: set[str] = set()
    for name in names:
        candidate = Path(directory) / name
        relative = (relative_directory / name).as_posix().lower()
        basename = name.lower()
        if relative == "examples/.vault_pass.example":
            continue
        if (
            candidate.is_symlink()
            or basename in {".vault_pass", "vault.yml", "vault.yaml", ".env"}
            or basename.startswith((".vault_pass", ".env"))
            or basename.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"))
            or basename.endswith(
                (
                    ".bak",
                    ".db",
                    ".jks",
                    ".kdbx",
                    ".key",
                    ".keystore",
                    ".log",
                    ".orig",
                    ".p12",
                    ".pem",
                    ".pfx",
                    ".retry",
                    ".sqlite",
                    ".sqlite3",
                    ".swo",
                    ".swp",
                    "~",
                )
            )
            or "__pycache__" in relative.split("/")
        ):
            ignored.add(name)
    return ignored


def test_real_build_excludes_sentinels_and_remains_installable(tmp_path: Path) -> None:
    collection_copy = tmp_path / "collection"
    shutil.copytree(
        _COLLECTION_SOURCE,
        collection_copy,
        ignore=_ignore_sensitive_source_paths,
    )
    shutil.copyfile(_REPOSITORY_ROOT / "LICENSE", collection_copy / "LICENSE")

    sentinel_paths = (
        collection_copy / "examples" / ".vault_pass",
        collection_copy / "examples" / ".vault_pass_new",
        collection_copy / "examples" / "group_vars" / "all" / "vault.yml",
        collection_copy / "examples" / ".env",
        collection_copy / "examples" / ".envrc",
        collection_copy / "examples" / "id_rsa",
        collection_copy / "examples" / "private.pem",
    )
    for sentinel in sentinel_paths:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("harmless sentinel\n")

    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    ansible_tmp = tmp_path / "ansible-tmp"
    ansible_tmp.mkdir()
    environment = {**os.environ, "ANSIBLE_LOCAL_TEMP": str(ansible_tmp)}
    build = subprocess.run(
        [
            "ansible-galaxy",
            "collection",
            "build",
            str(collection_copy),
            "--output-path",
            str(output_dir),
            "--force",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert build.returncode == 0, build.stderr

    artifact = output_dir / f"cisco-sccfm-{_COLLECTION_VERSION}.tar.gz"
    with tarfile.open(artifact, mode="r:gz") as archive:
        member_names = {member.name for member in archive.getmembers()}
        vault_template_member = archive.extractfile("examples/group_vars/all/vault.yml.example")
        assert vault_template_member is not None
        packaged_vault_template = yaml.safe_load(vault_template_member.read())

    for sentinel in sentinel_paths:
        assert sentinel.relative_to(collection_copy).as_posix() not in member_names
    assert "examples/.vault_pass.example" in member_names
    assert "examples/group_vars/all/vault.yml.example" in member_names
    assert "vault_sccfm_api_token" in packaged_vault_template
    assert "sccfm_api_token" not in packaged_vault_template

    verify_collection_artifact(artifact, expected_version=_COLLECTION_VERSION)

    install_root = tmp_path / "installed"
    install = subprocess.run(
        [
            "ansible-galaxy",
            "collection",
            "install",
            str(artifact),
            "--collections-path",
            str(install_root),
            "--force",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    installed_collection = install_root / "ansible_collections" / "cisco" / "sccfm"
    installed_vault_template = yaml.safe_load(
        (installed_collection / "examples" / "group_vars" / "all" / "vault.yml.example").read_text(
            encoding="utf-8"
        )
    )
    assert "vault_sccfm_api_token" in installed_vault_template
    assert "sccfm_api_token" not in installed_vault_template

    discovery_environment = {
        **environment,
        "ANSIBLE_COLLECTIONS_PATH": str(install_root),
    }
    discovery = subprocess.run(
        ["ansible-doc", "-j", "-l", "-t", "module", "cisco.sccfm"],
        capture_output=True,
        text=True,
        env=discovery_environment,
        check=False,
    )
    assert discovery.returncode == 0, discovery.stderr
    discovered_modules = json.loads(discovery.stdout)
    expected_modules = {
        f"cisco.sccfm.{module.stem}"
        for module in (_COLLECTION_SOURCE / "plugins" / "modules").glob("*.py")
        if module.name != "__init__.py"
    }
    assert set(discovered_modules) == expected_modules

    documentation = subprocess.run(
        ["ansible-doc", "-j", *sorted(expected_modules)],
        capture_output=True,
        text=True,
        env=discovery_environment,
        check=False,
    )
    assert documentation.returncode == 0, documentation.stderr
    module_documentation = json.loads(documentation.stdout)
    assert set(module_documentation) == expected_modules

    expected_auth_examples = (
        "region: \"{{ lookup('env', 'SCCFM_REGION') }}\"",
        "api_token: \"{{ lookup('env', 'SCCFM_API_TOKEN') }}\"",
    )
    undocumented_auth = {
        module_name: [
            expected
            for expected in expected_auth_examples
            if expected not in details.get("examples", "")
        ]
        for module_name, details in module_documentation.items()
        if any(expected not in details.get("examples", "") for expected in expected_auth_examples)
    }
    assert undocumented_auth == {}

    legacy_auth_variables = ("{{ sccfm_region }}", "{{ sccfm_api_token }}")
    legacy_auth_examples = {
        module_name: [
            legacy for legacy in legacy_auth_variables if legacy in details.get("examples", "")
        ]
        for module_name, details in module_documentation.items()
        if any(legacy in details.get("examples", "") for legacy in legacy_auth_variables)
    }
    assert legacy_auth_examples == {}

    inventory_discovery = subprocess.run(
        ["ansible-doc", "-j", "-l", "-t", "inventory", "cisco.sccfm"],
        capture_output=True,
        text=True,
        env=discovery_environment,
        check=False,
    )
    assert inventory_discovery.returncode == 0, inventory_discovery.stderr
    assert set(json.loads(inventory_discovery.stdout)) == {"cisco.sccfm.sccfm"}
