# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Create and verify the immutable artifact manifest for one release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MANIFEST_NAME = "release-manifest.json"
_PROJECT_NAME = "cisco-sccfm-devkit"
_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 64 * 1024
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ReleaseArtifactError(RuntimeError):
    """Raised when a release artifact bundle violates the immutable policy."""


@dataclass(frozen=True)
class ReleaseBundleVerification:
    """Summary of a successfully verified release bundle."""

    version: str
    artifact_count: int
    manifest_sha256: str


def _expected_artifacts(version: str) -> dict[str, str]:
    """Return the exact release filenames and their public artifact kinds."""
    return {
        f"cisco-sccfm-{version}.tar.gz": "ansible-collection",
        f"cisco_sccfm_devkit-{version}-py3-none-any.whl": "python-wheel",
        f"cisco_sccfm_devkit-{version}.tar.gz": "python-sdist",
    }


def _validate_identity(version: str, tag: str, source_commit: str) -> None:
    """Validate the source identity bound into the release manifest."""
    if _VERSION.fullmatch(version) is None:
        raise ReleaseArtifactError("release version is invalid")
    if tag != f"v{version}":
        raise ReleaseArtifactError("release tag does not match the version")
    if _COMMIT.fullmatch(source_commit) is None:
        raise ReleaseArtifactError("source commit must be a lowercase 40-character Git SHA")


def _file_digest(path: Path) -> tuple[int, str]:
    """Return the size and SHA-256 of one regular, non-symlink artifact."""
    if path.is_symlink() or not path.is_file():
        raise ReleaseArtifactError(f"release artifact must be a regular file: {path.name}")
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as artifact:
            while chunk := artifact.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise ReleaseArtifactError(f"could not read release artifact: {path.name}") from exc
    return size, digest.hexdigest()


def _manifest_payload(
    directory: Path,
    version: str,
    tag: str,
    source_commit: str,
) -> dict[str, Any]:
    """Build the canonical manifest payload for the three release artifacts."""
    artifacts = []
    for filename, kind in sorted(_expected_artifacts(version).items()):
        size, digest = _file_digest(directory / filename)
        artifacts.append(
            {
                "filename": filename,
                "kind": kind,
                "sha256": digest,
                "size": size,
            }
        )
    return {
        "schema_version": _SCHEMA_VERSION,
        "project": _PROJECT_NAME,
        "version": version,
        "tag": tag,
        "source_commit": source_commit,
        "artifacts": artifacts,
    }


def create_release_manifest(
    directory: Path,
    version: str,
    tag: str,
    source_commit: str,
) -> ReleaseBundleVerification:
    """Create the manifest once, then verify the complete bundle."""
    _validate_identity(version, tag, source_commit)
    if directory.is_symlink() or not directory.is_dir():
        raise ReleaseArtifactError("release bundle directory must be a regular directory")
    manifest = directory / _MANIFEST_NAME
    if manifest.exists() or manifest.is_symlink():
        raise ReleaseArtifactError("release manifest already exists")
    expected_before = set(_expected_artifacts(version))
    try:
        actual_before = {path.name for path in directory.iterdir()}
    except OSError as exc:
        raise ReleaseArtifactError("could not inspect release bundle directory") from exc
    if actual_before != expected_before:
        raise ReleaseArtifactError("release bundle must contain exactly the three artifacts")

    payload = _manifest_payload(directory, version, tag, source_commit)
    try:
        with manifest.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
    except FileExistsError as exc:
        raise ReleaseArtifactError("release manifest already exists") from exc
    except OSError as exc:
        raise ReleaseArtifactError("could not write release manifest") from exc

    return verify_release_bundle(directory, version, tag, source_commit)


def _load_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    """Load a small JSON manifest object without accepting links or special files."""
    if path.is_symlink() or not path.is_file():
        raise ReleaseArtifactError("release manifest must be a regular file")
    try:
        if path.stat().st_size > _MAX_MANIFEST_BYTES:
            raise ReleaseArtifactError("release manifest exceeds the size limit")
        raw = path.read_bytes()
        parsed: object = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (OSError, ValueError) as exc:
        raise ReleaseArtifactError("release manifest is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ReleaseArtifactError("release manifest must be a JSON object")
    return dict(parsed), raw


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON object keys at every manifest nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseArtifactError("release manifest contains a duplicate JSON key")
        result[key] = value
    return result


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    """Require one manifest object to expose no missing or unknown fields."""
    if set(value) != expected:
        raise ReleaseArtifactError(f"release manifest has invalid {label} fields")


def _manifest_artifacts(raw: object, version: str) -> dict[str, dict[str, Any]]:
    """Return validated, duplicate-free artifact records keyed by filename."""
    if not isinstance(raw, list) or len(raw) != 3:
        raise ReleaseArtifactError("release manifest must describe exactly three artifacts")
    expected = _expected_artifacts(version)
    records: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ReleaseArtifactError("release manifest contains an invalid artifact record")
        record = dict(item)
        _require_exact_keys(record, {"filename", "kind", "sha256", "size"}, "artifact")
        filename = record.get("filename")
        kind = record.get("kind")
        digest = record.get("sha256")
        size = record.get("size")
        if not isinstance(filename, str) or filename in records or filename not in expected:
            raise ReleaseArtifactError("release manifest contains an unexpected artifact filename")
        if kind != expected[filename]:
            raise ReleaseArtifactError("release manifest contains an unexpected artifact kind")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ReleaseArtifactError("release manifest contains an invalid SHA-256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ReleaseArtifactError("release manifest contains an invalid artifact size")
        records[filename] = record
    if set(records) != set(expected):
        raise ReleaseArtifactError("release manifest does not describe the expected artifacts")
    return records


def verify_release_bundle(
    directory: Path,
    expected_version: str,
    expected_tag: str,
    expected_source_commit: str,
) -> ReleaseBundleVerification:
    """Verify identity, filenames, sizes, and hashes for an exact release bundle."""
    _validate_identity(expected_version, expected_tag, expected_source_commit)
    if directory.is_symlink() or not directory.is_dir():
        raise ReleaseArtifactError("release bundle directory must be a regular directory")

    expected_names = set(_expected_artifacts(expected_version)) | {_MANIFEST_NAME}
    try:
        actual_names = {path.name for path in directory.iterdir()}
    except OSError as exc:
        raise ReleaseArtifactError("could not inspect release bundle directory") from exc
    if actual_names != expected_names:
        raise ReleaseArtifactError("release bundle contains missing or unexpected files")

    manifest, raw_manifest = _load_manifest(directory / _MANIFEST_NAME)
    _require_exact_keys(
        manifest,
        {"schema_version", "project", "version", "tag", "source_commit", "artifacts"},
        "top-level",
    )
    schema_version = manifest.get("schema_version")
    if type(schema_version) is not int or schema_version != _SCHEMA_VERSION:
        raise ReleaseArtifactError("release manifest uses an unsupported schema version")
    if manifest.get("project") != _PROJECT_NAME:
        raise ReleaseArtifactError("release manifest names an unexpected project")
    if manifest.get("version") != expected_version:
        raise ReleaseArtifactError("release manifest version does not match")
    if manifest.get("tag") != expected_tag:
        raise ReleaseArtifactError("release manifest tag does not match")
    if manifest.get("source_commit") != expected_source_commit:
        raise ReleaseArtifactError("release manifest source commit does not match")

    records = _manifest_artifacts(manifest.get("artifacts"), expected_version)
    for filename, record in records.items():
        size, digest = _file_digest(directory / filename)
        if size != record["size"]:
            raise ReleaseArtifactError(f"release artifact size does not match: {filename}")
        if digest != record["sha256"]:
            raise ReleaseArtifactError(f"release artifact SHA-256 does not match: {filename}")

    return ReleaseBundleVerification(
        version=expected_version,
        artifact_count=len(records),
        manifest_sha256=hashlib.sha256(raw_manifest).hexdigest(),
    )


def _parser() -> argparse.ArgumentParser:
    """Build the release manifest CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "verify"):
        subparser = commands.add_parser(command)
        subparser.add_argument("directory", type=Path)
        subparser.add_argument("--version", required=True)
        subparser.add_argument("--tag", required=True)
        subparser.add_argument("--source-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Create or verify an exact release bundle from CI."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            result = create_release_manifest(
                args.directory,
                args.version,
                args.tag,
                args.source_commit,
            )
        else:
            result = verify_release_bundle(
                args.directory,
                args.version,
                args.tag,
                args.source_commit,
            )
    except ReleaseArtifactError as exc:
        print(f"Release artifact bundle rejected: {exc}")
        return 1

    print(
        "Release artifact bundle verified: "
        f"version={result.version} artifacts={result.artifact_count} "
        f"manifest_sha256={result.manifest_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
