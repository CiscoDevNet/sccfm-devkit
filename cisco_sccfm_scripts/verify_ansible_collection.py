# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed verification for built ``cisco.sccfm`` collection artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence, cast

import yaml

_MAX_MEMBERS = 2_000
_MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
_MAX_MEMBER_BYTES = 10 * 1024 * 1024
_MAX_TOTAL_BYTES = 50 * 1024 * 1024

_ALLOWED_TOP_LEVEL = frozenset(
    {
        "FILES.json",
        "LICENSE",
        "MANIFEST.json",
        "README.md",
        "__init__.py",
        "examples",
        "meta",
        "plugins",
        "requirements.txt",
    }
)
_REQUIRED_MEMBERS = frozenset(
    {
        "FILES.json",
        "LICENSE",
        "MANIFEST.json",
        "README.md",
        "examples/.vault_pass.example",
        "examples/group_vars/all/vault.yml.example",
        "meta/execution-environment.yml",
        "meta/runtime.yml",
        "plugins/inventory",
        "plugins/module_utils",
        "plugins/modules",
        "requirements.txt",
    }
)
_SAFE_CREDENTIAL_TEMPLATES = frozenset(
    {
        "examples/.vault_pass.example",
        "examples/group_vars/all/vault.yml.example",
    }
)
_ALLOWED_EXAMPLE_PATHS = frozenset(
    {
        "examples",
        "examples/.vault_pass.example",
        "examples/access_rules.yml",
        "examples/add_object_override.yml",
        "examples/asa_ha_check.yml",
        "examples/change_asa_boot_image.yml",
        "examples/change_asa_local_password.yml",
        "examples/configure_manager.yml",
        "examples/create_network_groups.yml",
        "examples/create_network_objects.yml",
        "examples/delete_network_groups.yml",
        "examples/delete_network_objects.yml",
        "examples/deploy_cdfmc_ftd.yml",
        "examples/execute_asa_cli.yml",
        "examples/execute_ftd_cli.yml",
        "examples/group_vars",
        "examples/group_vars/all",
        "examples/group_vars/all/vars.yml",
        "examples/group_vars/all/vault.yml.example",
        "examples/inventory.sccfm.yml",
        "examples/list_asa_boot_registry.yml",
        "examples/list_asa_compatible_versions.yml",
        "examples/list_asa_disk_files.yml",
        "examples/list_asa_local_users.yml",
        "examples/list_asa_not_on_version.yml",
        "examples/list_ftd_compatible_versions.yml",
        "examples/list_ftd_not_on_version.yml",
        "examples/list_network_groups.yml",
        "examples/list_network_objects.yml",
        "examples/manage_asa_shun.yml",
        "examples/manage_network_group_members.yml",
        "examples/network_objects.yml",
        "examples/onboard_asas.yml",
        "examples/onboard_cdfmc_ftd.yml",
        "examples/onboard_cdfmc_ftd_ztp.yml",
        "examples/show_devices.yml",
        "examples/trigger_asa_upgrade.yml",
        "examples/trigger_ftd_upgrade.yml",
        "examples/update_network_groups.yml",
        "examples/update_network_objects.yml",
    }
)
_FORBIDDEN_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".venv",
        "__pycache__",
    }
)
_FORBIDDEN_EXACT_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        ".vault_pass",
        "credentials",
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "secrets.yaml",
        "secrets.yml",
        "vault.yaml",
        "vault.yml",
    }
)
_FORBIDDEN_KEY_PREFIXES = (
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
)
_FORBIDDEN_SUFFIXES = (
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
)
_CONTENT_RULES: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "private key",
        re.compile(rb"-----BEGIN (?:[A-Z0-9]+ |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("AWS access key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    (
        "JWT-like token",
        re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
)


class ArtifactVerificationError(RuntimeError):
    """Raised when a collection artifact violates the release policy."""


@dataclass(frozen=True)
class ArtifactVerification:
    """Summary of a successfully verified artifact."""

    sha256: str
    file_count: int
    uncompressed_bytes: int


def _safe_member_name(raw_name: str) -> str:
    """Validate and return one canonical POSIX archive member path."""
    if not raw_name or "\x00" in raw_name or "\\" in raw_name or raw_name.startswith("/"):
        raise ArtifactVerificationError("artifact contains an invalid member path")
    raw_parts = raw_name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ArtifactVerificationError("artifact contains a non-canonical member path")
    canonical = PurePosixPath(raw_name).as_posix()
    if canonical != raw_name:
        raise ArtifactVerificationError("artifact contains a non-canonical member path")
    if len(canonical) > 500:
        raise ArtifactVerificationError("artifact contains an excessively long member path")
    return canonical


def _check_member_path(name: str) -> None:
    """Reject paths that do not belong in the public collection."""
    path = PurePosixPath(name)
    if path.parts[0] not in _ALLOWED_TOP_LEVEL:
        raise ArtifactVerificationError(f"unexpected top-level artifact path: {path.parts[0]}")

    lowered_parts = tuple(part.lower() for part in path.parts)
    if any(part in _FORBIDDEN_DIRECTORY_NAMES for part in lowered_parts[:-1]):
        raise ArtifactVerificationError(f"forbidden runtime directory in artifact: {name}")
    if path.parts[0] == "examples" and name not in _ALLOWED_EXAMPLE_PATHS:
        raise ArtifactVerificationError(f"unreviewed examples path in artifact: {name}")
    if name in _SAFE_CREDENTIAL_TEMPLATES:
        return

    basename = lowered_parts[-1]
    if basename in _FORBIDDEN_EXACT_NAMES:
        raise ArtifactVerificationError(f"forbidden credential path in artifact: {name}")
    if basename.startswith(".env") or basename.startswith(".vault_pass"):
        raise ArtifactVerificationError(f"forbidden credential backup in artifact: {name}")
    if basename.startswith("vault.yml.") or basename.startswith("vault.yaml."):
        raise ArtifactVerificationError(f"forbidden vault backup in artifact: {name}")
    if basename.startswith(_FORBIDDEN_KEY_PREFIXES):
        raise ArtifactVerificationError(f"forbidden private-key path in artifact: {name}")
    if basename.endswith(_FORBIDDEN_SUFFIXES) or basename.endswith("~"):
        raise ArtifactVerificationError(f"forbidden local-data path in artifact: {name}")


def _read_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    """Read a size-bounded regular member."""
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ArtifactVerificationError(f"could not read artifact member: {member.name}")
    data = extracted.read(_MAX_MEMBER_BYTES + 1)
    if len(data) > _MAX_MEMBER_BYTES:
        raise ArtifactVerificationError(f"artifact member exceeds size limit: {member.name}")
    return data


def _load_json_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo
) -> tuple[dict[str, Any], bytes]:
    """Load one required JSON object without exposing its contents in errors."""
    raw = _read_member(archive, member)
    try:
        parsed: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactVerificationError(f"invalid JSON in artifact member: {member.name}") from exc
    if not isinstance(parsed, dict):
        raise ArtifactVerificationError(f"expected a JSON object in artifact member: {member.name}")
    return cast(dict[str, Any], parsed), raw


def _load_yaml_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> dict[str, Any]:
    """Load one required YAML mapping without exposing its contents in errors."""
    raw = _read_member(archive, member)
    try:
        parsed: object = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ArtifactVerificationError(f"invalid YAML in artifact member: {member.name}") from exc
    if not isinstance(parsed, dict):
        raise ArtifactVerificationError(
            f"expected a YAML mapping in artifact member: {member.name}"
        )
    return cast(dict[str, Any], parsed)


def _manifest_entries(files_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a validated, duplicate-free FILES.json entry map."""
    raw_entries = files_manifest.get("files")
    if not isinstance(raw_entries, list):
        raise ArtifactVerificationError("FILES.json has no valid files list")

    entries: dict[str, dict[str, Any]] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ArtifactVerificationError("FILES.json contains an invalid entry")
        entry = cast(dict[str, Any], raw_entry)
        name = entry.get("name")
        if not isinstance(name, str):
            raise ArtifactVerificationError("FILES.json contains an entry without a valid name")
        if name == ".":
            if entry.get("ftype") != "dir":
                raise ArtifactVerificationError("FILES.json root entry is not a directory")
            continue
        name = _safe_member_name(name)
        if name in entries:
            raise ArtifactVerificationError(f"FILES.json contains a duplicate path: {name}")
        entries[name] = entry
    return entries


def _verify_manifests(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    expected_version: str,
) -> None:
    """Verify Ansible metadata, member declarations, and file hashes."""
    manifest, _ = _load_json_member(archive, members["MANIFEST.json"])
    files_manifest, files_raw = _load_json_member(archive, members["FILES.json"])

    collection_info = manifest.get("collection_info")
    if not isinstance(collection_info, dict):
        raise ArtifactVerificationError("MANIFEST.json has no valid collection_info")
    expected_metadata = {"namespace": "cisco", "name": "sccfm", "version": expected_version}
    for key, expected in expected_metadata.items():
        if collection_info.get(key) != expected:
            raise ArtifactVerificationError(f"MANIFEST.json has unexpected {key}")

    file_manifest_file = manifest.get("file_manifest_file")
    if not isinstance(file_manifest_file, dict):
        raise ArtifactVerificationError("MANIFEST.json has no valid file_manifest_file")
    if file_manifest_file.get("name") != "FILES.json":
        raise ArtifactVerificationError("MANIFEST.json references an unexpected file manifest")
    if file_manifest_file.get("chksum_type") != "sha256":
        raise ArtifactVerificationError("MANIFEST.json uses an unexpected checksum type")
    if file_manifest_file.get("chksum_sha256") != hashlib.sha256(files_raw).hexdigest():
        raise ArtifactVerificationError("FILES.json checksum does not match MANIFEST.json")

    entries = _manifest_entries(files_manifest)
    actual_names = set(members) - {"MANIFEST.json", "FILES.json"}
    if set(entries) != actual_names:
        raise ArtifactVerificationError("artifact members do not exactly match FILES.json")

    for name, entry in entries.items():
        member = members[name]
        file_type = entry.get("ftype")
        if member.isdir():
            if file_type != "dir":
                raise ArtifactVerificationError(f"FILES.json type mismatch for: {name}")
            continue
        if file_type != "file" or entry.get("chksum_type") != "sha256":
            raise ArtifactVerificationError(f"FILES.json file metadata is invalid for: {name}")
        actual_hash = hashlib.sha256(_read_member(archive, member)).hexdigest()
        if entry.get("chksum_sha256") != actual_hash:
            raise ArtifactVerificationError(f"artifact member checksum mismatch: {name}")


def _scan_member_content(name: str, data: bytes) -> None:
    """Apply redacted high-confidence secret tripwires to one file."""
    if data.lstrip().startswith(b"$ANSIBLE_VAULT;"):
        raise ArtifactVerificationError(f"encrypted vault payload found in artifact: {name}")
    for label, pattern in _CONTENT_RULES:
        if pattern.search(data):
            raise ArtifactVerificationError(f"{label} material found in artifact: {name}")


def _verify_license_content(archive: tarfile.TarFile, member: tarfile.TarInfo) -> None:
    """Require the declared Apache-2.0 license text in the exact artifact."""
    content = _read_member(archive, member)
    if b"Apache License" not in content or b"Version 2.0" not in content:
        raise ArtifactVerificationError("artifact LICENSE does not contain Apache-2.0 text")


def _verify_python_dependency_contract(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    expected_version: str,
) -> None:
    """Require Ansible Builder metadata and the lockstep Python package pin."""
    try:
        requirements = _read_member(archive, members["requirements.txt"]).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactVerificationError(
            "invalid UTF-8 in artifact member: requirements.txt"
        ) from exc
    requirement_lines = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    expected_requirement = f"cisco-sccfm-devkit=={expected_version}"
    if requirement_lines != [expected_requirement]:
        raise ArtifactVerificationError(
            "requirements.txt does not contain only the version-matched Python package"
        )

    execution_environment = _load_yaml_member(archive, members["meta/execution-environment.yml"])
    if execution_environment != {"dependencies": {"python": "requirements.txt"}}:
        raise ArtifactVerificationError(
            "meta/execution-environment.yml does not reference requirements.txt"
        )


def verify_collection_artifact(artifact: Path, expected_version: str) -> ArtifactVerification:
    """Verify structure, manifests, paths, content, and digest for one tarball."""
    expected_name = f"cisco-sccfm-{expected_version}.tar.gz"
    if artifact.name != expected_name:
        raise ArtifactVerificationError(f"unexpected artifact filename: {artifact.name}")
    if artifact.is_symlink() or not artifact.is_file():
        raise ArtifactVerificationError("collection artifact must be a regular file")
    if artifact.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise ArtifactVerificationError("collection artifact exceeds compressed-size limit")

    try:
        with tarfile.open(artifact, mode="r:gz") as archive:
            raw_members = archive.getmembers()
            if len(raw_members) > _MAX_MEMBERS:
                raise ArtifactVerificationError("artifact exceeds member-count limit")

            members: dict[str, tarfile.TarInfo] = {}
            total_bytes = 0
            for member in raw_members:
                name = _safe_member_name(member.name)
                if name in members:
                    raise ArtifactVerificationError(f"artifact contains a duplicate path: {name}")
                if not (member.isfile() or member.isdir()):
                    raise ArtifactVerificationError(f"unsupported archive member type: {name}")
                if member.mode & 0o7000 or member.mode & 0o022:
                    raise ArtifactVerificationError(f"unsafe archive mode for: {name}")
                if member.size < 0 or member.size > _MAX_MEMBER_BYTES:
                    raise ArtifactVerificationError(f"artifact member exceeds size limit: {name}")
                total_bytes += member.size
                if total_bytes > _MAX_TOTAL_BYTES:
                    raise ArtifactVerificationError("artifact exceeds uncompressed-size limit")
                _check_member_path(name)
                members[name] = member

            missing = _REQUIRED_MEMBERS - set(members)
            if missing:
                raise ArtifactVerificationError(
                    f"artifact is missing required path: {sorted(missing)[0]}"
                )

            _verify_manifests(archive, members, expected_version)
            _verify_license_content(archive, members["LICENSE"])
            _verify_python_dependency_contract(archive, members, expected_version)
            for name, member in members.items():
                if member.isfile():
                    _scan_member_content(name, _read_member(archive, member))
    except (tarfile.TarError, OSError) as exc:
        raise ArtifactVerificationError(
            "collection artifact is not a readable tar.gz file"
        ) from exc

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    file_count = sum(member.isfile() for member in raw_members)
    return ArtifactVerification(
        sha256=digest,
        file_count=file_count,
        uncompressed_bytes=total_bytes,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line wrapper for CI and release automation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args(argv)

    try:
        result = verify_collection_artifact(args.artifact, args.expected_version)
    except ArtifactVerificationError as exc:
        print(f"Collection artifact rejected: {exc}")
        return 1

    print(
        "Collection artifact verified: "
        f"files={result.file_count} bytes={result.uncompressed_bytes} sha256={result.sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
