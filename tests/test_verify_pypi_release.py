# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for exact PyPI release verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import cisco_sccfm_scripts.verify_pypi_release as verifier
from cisco_sccfm_scripts.release_artifacts import create_release_manifest
from cisco_sccfm_scripts.verify_pypi_release import (
    PyPIReleaseError,
    PyPIReleaseNotPublishedError,
    PyPIReleaseStatus,
    PyPIReleaseVerification,
    verify_pypi_release,
)

_VERSION = "1.2.3"
_TAG = "v1.2.3"
_COMMIT = "a" * 40
_WHEEL = "cisco_sccfm_devkit-1.2.3-py3-none-any.whl"
_SDIST = "cisco_sccfm_devkit-1.2.3.tar.gz"
_ARTIFACTS = {
    "cisco-sccfm-1.2.3.tar.gz": b"collection",
    _WHEEL: b"wheel",
    _SDIST: b"sdist",
}


class _Response:
    """Small context-managed urllib response for deterministic tests."""

    def __init__(self, payload: bytes, url: str) -> None:
        self._payload = payload
        self._url = url
        self.read_limit: int | None = None

    def __enter__(self) -> _Response:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, limit: int) -> bytes:
        self.read_limit = limit
        return self._payload[:limit]


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "release"
    bundle.mkdir()
    for filename, content in _ARTIFACTS.items():
        (bundle / filename).write_bytes(content)
    create_release_manifest(bundle, _VERSION, _TAG, _COMMIT)
    return bundle


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _payload(
    *,
    wheel_hash: str | None = None,
    sdist_hash: str | None = None,
    files: list[dict[str, Any]] | None = None,
) -> bytes:
    urls = files
    if urls is None:
        urls = [
            {
                "filename": _WHEEL,
                "digests": {"sha256": wheel_hash or _sha256(_ARTIFACTS[_WHEEL])},
            },
            {
                "filename": _SDIST,
                "digests": {"sha256": sdist_hash or _sha256(_ARTIFACTS[_SDIST])},
            },
        ]
    return json.dumps({"info": {"version": _VERSION}, "urls": urls}).encode()


def _install_response(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> tuple[_Response, list[tuple[str, float]]]:
    calls: list[tuple[str, float]] = []
    response = _Response(
        payload,
        "https://pypi.org/pypi/cisco-sccfm-devkit/1.2.3/json",
    )

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        calls.append((request.full_url, timeout))
        return response

    monkeypatch.setattr(verifier, "urlopen", fake_urlopen)
    return response, calls


def test_matching_release_uses_fixed_bounded_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    response, calls = _install_response(monkeypatch, _payload())

    result = verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)

    assert result == PyPIReleaseVerification(
        version=_VERSION,
        file_count=2,
        status=PyPIReleaseStatus.COMPLETE,
    )
    assert calls == [
        ("https://pypi.org/pypi/cisco-sccfm-devkit/1.2.3/json", 10.0),
    ]
    assert response.read_limit == 1024 * 1024 + 1


def test_http_404_means_not_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)

    def not_found(request: Request, timeout: float) -> _Response:
        raise HTTPError(request.full_url, 404, "sentinel", None, None)

    monkeypatch.setattr(verifier, "urlopen", not_found)

    with pytest.raises(PyPIReleaseNotPublishedError, match="not published"):
        verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)


def test_hash_mismatch_does_not_expose_remote_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    sentinel = "REMOTE-SECRET-SENTINEL"
    payload = json.loads(_payload(wheel_hash="b" * 64))
    payload["info"]["untrusted"] = sentinel
    _install_response(monkeypatch, json.dumps(payload).encode())

    with pytest.raises(PyPIReleaseError) as error:
        verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)

    assert sentinel not in str(error.value)


@pytest.mark.parametrize("filename", [_WHEEL, _SDIST])
def test_matching_nonempty_subset_is_safely_resumable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    bundle = _bundle(tmp_path)
    files = [{"filename": filename, "digests": {"sha256": _sha256(_ARTIFACTS[filename])}}]
    _install_response(monkeypatch, _payload(files=files))

    result = verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)

    assert result == PyPIReleaseVerification(
        version=_VERSION,
        file_count=1,
        status=PyPIReleaseStatus.PARTIAL,
        missing_filenames=(_SDIST if filename == _WHEEL else _WHEEL,),
    )


@pytest.mark.parametrize(
    "files",
    [
        [],
        [
            {"filename": _WHEEL, "digests": {"sha256": _sha256(_ARTIFACTS[_WHEEL])}},
            {"filename": _SDIST, "digests": {"sha256": _sha256(_ARTIFACTS[_SDIST])}},
            {"filename": "unexpected.zip", "digests": {"sha256": "c" * 64}},
        ],
        [
            {"filename": _WHEEL, "digests": {"sha256": _sha256(_ARTIFACTS[_WHEEL])}},
            {"filename": _WHEEL, "digests": {"sha256": _sha256(_ARTIFACTS[_WHEEL])}},
        ],
    ],
    ids=["empty", "extra", "duplicate"],
)
def test_partial_release_rejects_unsafe_file_sets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: list[dict[str, Any]],
) -> None:
    bundle = _bundle(tmp_path)
    _install_response(monkeypatch, _payload(files=files))

    with pytest.raises(PyPIReleaseError, match="expected file|unexpected file"):
        verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)


def test_partial_release_rejects_a_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    files = [{"filename": _WHEEL, "digests": {"sha256": "b" * 64}}]
    _install_response(monkeypatch, _payload(files=files))

    with pytest.raises(PyPIReleaseError, match="hashes do not match"):
        verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        json.dumps({"info": {"version": _VERSION}, "urls": {}}).encode(),
        json.dumps({"info": {"version": "9.9.9"}, "urls": []}).encode(),
    ],
    ids=["invalid-json", "invalid-files", "wrong-version"],
)
def test_malformed_response_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    bundle = _bundle(tmp_path)
    _install_response(monkeypatch, payload)

    with pytest.raises(PyPIReleaseError):
        verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)


def test_network_error_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)

    def fail(request: Request, timeout: float) -> _Response:
        raise URLError("REMOTE-SECRET-SENTINEL")

    monkeypatch.setattr(verifier, "urlopen", fail)

    with pytest.raises(PyPIReleaseError) as error:
        verify_pypi_release(bundle, _VERSION, _TAG, _COMMIT)

    assert str(error.value) == "could not query PyPI"


@pytest.mark.parametrize(
    ("outcome", "exit_code", "message"),
    [
        (
            PyPIReleaseVerification(_VERSION, 2, PyPIReleaseStatus.COMPLETE),
            0,
            "PyPI release verified",
        ),
        (
            PyPIReleaseVerification(
                _VERSION,
                1,
                PyPIReleaseStatus.PARTIAL,
                (_SDIST,),
            ),
            3,
            "partially published",
        ),
        (PyPIReleaseNotPublishedError("not published"), 2, "not published"),
        (PyPIReleaseError("verification failed"), 1, "verification failed"),
    ],
)
def test_cli_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: PyPIReleaseVerification | Exception,
    exit_code: int,
    message: str,
) -> None:
    bundle = tmp_path / "release"

    def fake_verify(
        directory: Path,
        version: str,
        tag: str,
        source_commit: str,
    ) -> PyPIReleaseVerification:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(verifier, "verify_pypi_release", fake_verify)

    result = verifier.main(
        [
            str(bundle),
            "--version",
            _VERSION,
            "--tag",
            _TAG,
            "--source-commit",
            _COMMIT,
        ]
    )

    assert result == exit_code
    assert message in capsys.readouterr().out
