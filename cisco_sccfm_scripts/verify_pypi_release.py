# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Verify that PyPI serves the exact Python artifacts from a release bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cisco_sccfm_scripts.release_artifacts import (
    ReleaseArtifactError,
    verify_release_bundle,
)

_PYPI_PROJECT = "cisco-sccfm-devkit"
_PYPI_ENDPOINT = "https://pypi.org/pypi/cisco-sccfm-devkit/{version}/json"
_MAX_RESPONSE_BYTES = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 10.0
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PyPIReleaseError(RuntimeError):
    """Raised when a PyPI response cannot prove an exact artifact match."""


class PyPIReleaseNotPublishedError(PyPIReleaseError):
    """Raised when PyPI reports that the requested version does not exist."""


class PyPIReleaseStatus(Enum):
    """Publication state of the expected Python artifacts."""

    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True)
class PyPIReleaseVerification:
    """Summary of a complete or safely resumable PyPI release."""

    version: str
    file_count: int
    status: PyPIReleaseStatus


def _python_artifact_names(version: str) -> tuple[str, str]:
    """Return the exact wheel and sdist filenames for one release."""
    return (
        f"cisco_sccfm_devkit-{version}-py3-none-any.whl",
        f"cisco_sccfm_devkit-{version}.tar.gz",
    )


def _file_sha256(path: Path) -> str:
    """Hash one regular, non-symlink file without loading it into memory."""
    if path.is_symlink() or not path.is_file():
        raise PyPIReleaseError(f"local release artifact is not a regular file: {path.name}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as artifact:
            while chunk := artifact.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise PyPIReleaseError(f"could not read local release artifact: {path.name}") from exc
    return digest.hexdigest()


def _local_python_hashes(
    directory: Path,
    version: str,
    tag: str,
    source_commit: str,
) -> dict[str, str]:
    """Return hashes from an exact bundle that passes manifest verification."""
    try:
        verify_release_bundle(directory, version, tag, source_commit)
        hashes = {
            filename: _file_sha256(directory / filename)
            for filename in _python_artifact_names(version)
        }
        # Close the small check/hash race by requiring the complete manifest-bound bundle
        # to remain valid after hashing as well.
        verify_release_bundle(directory, version, tag, source_commit)
    except ReleaseArtifactError as exc:
        raise PyPIReleaseError(f"local release bundle is invalid: {exc}") from exc
    return hashes


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys instead of accepting ambiguous remote JSON."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PyPIReleaseError("PyPI response contains a duplicate JSON key")
        result[key] = value
    return result


def _read_response(response: Any, expected_url: str) -> object:
    """Read and decode one bounded response from the fixed PyPI endpoint."""
    if response.geturl() != expected_url:
        raise PyPIReleaseError("PyPI response was redirected to an unexpected endpoint")
    try:
        raw: bytes = response.read(_MAX_RESPONSE_BYTES + 1)
    except OSError as exc:
        raise PyPIReleaseError("could not read the PyPI response") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise PyPIReleaseError("PyPI response exceeds the size limit")
    try:
        return json.loads(raw, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PyPIReleaseError("PyPI response is not valid JSON") from exc


def _fetch_release(version: str, timeout: float) -> object:
    """Fetch one release document from the fixed official PyPI JSON endpoint."""
    url = _PYPI_ENDPOINT.format(version=quote(version, safe=""))
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "cisco-sccfm-devkit-release-verifier",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return _read_response(response, url)
    except HTTPError as exc:
        if exc.code == 404:
            raise PyPIReleaseNotPublishedError(
                f"{_PYPI_PROJECT} {version} is not published"
            ) from exc
        raise PyPIReleaseError("PyPI returned an unexpected HTTP error") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise PyPIReleaseError("could not query PyPI") from exc


def _remote_python_hashes(payload: object, version: str) -> dict[str, str]:
    """Extract a nonempty expected filename-to-SHA-256 mapping from PyPI."""
    if not isinstance(payload, dict):
        raise PyPIReleaseError("PyPI response must be a JSON object")
    info = payload.get("info")
    urls = payload.get("urls")
    if not isinstance(info, dict) or info.get("version") != version:
        raise PyPIReleaseError("PyPI response describes an unexpected version")
    if not isinstance(urls, list):
        raise PyPIReleaseError("PyPI response has an invalid files list")

    expected_names = set(_python_artifact_names(version))
    hashes: dict[str, str] = {}
    for item in urls:
        if not isinstance(item, dict):
            raise PyPIReleaseError("PyPI response contains an invalid file record")
        filename = item.get("filename")
        digests = item.get("digests")
        if not isinstance(filename, str) or not isinstance(digests, Mapping):
            raise PyPIReleaseError("PyPI response contains an invalid file record")
        sha256 = digests.get("sha256")
        if (
            filename not in expected_names
            or filename in hashes
            or not isinstance(sha256, str)
            or _SHA256.fullmatch(sha256) is None
        ):
            raise PyPIReleaseError("PyPI response contains an unexpected file record")
        hashes[filename] = sha256
    if not hashes:
        raise PyPIReleaseError("PyPI release does not contain an expected file")
    return hashes


def verify_pypi_release(
    directory: Path,
    version: str,
    tag: str,
    source_commit: str,
    *,
    timeout: float = _REQUEST_TIMEOUT_SECONDS,
) -> PyPIReleaseVerification:
    """Verify a complete release or a safe manifest-bound proper subset on PyPI."""
    local_hashes = _local_python_hashes(directory, version, tag, source_commit)
    remote_hashes = _remote_python_hashes(_fetch_release(version, timeout), version)
    if any(local_hashes[filename] != digest for filename, digest in remote_hashes.items()):
        raise PyPIReleaseError("PyPI file hashes do not match the verified release bundle")
    status = (
        PyPIReleaseStatus.COMPLETE if remote_hashes == local_hashes else PyPIReleaseStatus.PARTIAL
    )
    return PyPIReleaseVerification(
        version=version,
        file_count=len(remote_hashes),
        status=status,
    )


def _parser() -> argparse.ArgumentParser:
    """Build the PyPI verification CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Verify one published PyPI release for use by the release workflow."""
    args = _parser().parse_args(argv)
    try:
        result = verify_pypi_release(
            args.directory,
            args.version,
            args.tag,
            args.source_commit,
        )
    except PyPIReleaseNotPublishedError as exc:
        print(f"PyPI release not published: {exc}")
        return 2
    except PyPIReleaseError as exc:
        print(f"PyPI release verification failed: {exc}")
        return 1

    if result.status is PyPIReleaseStatus.PARTIAL:
        print(
            f"PyPI release partially published: version={result.version} files={result.file_count}"
        )
        return 3
    print(f"PyPI release verified: version={result.version} files={result.file_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
