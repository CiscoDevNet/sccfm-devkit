# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest

from cisco_sccfm_scripts.verify_python_artifacts import (
    PythonArtifactVerificationError,
    verify_python_artifacts,
    verify_python_wheel,
)

_VERSION = "1.2.3"
_DIST_INFO = f"cisco_sccfm_devkit-{_VERSION}.dist-info"
_ENTRY_POINTS = b"[console_scripts]\nsccfm-cli=cisco_sccfm_cli.cli:cli\n"
_PYPROJECT = b"""\
[tool.poetry]
packages = [
    { include = "cisco_sccfm_cli" },
    { include = "cisco_sccfm_core" },
]

[tool.poetry.scripts]
sccfm-cli = "cisco_sccfm_cli.cli:cli"
"""


def _write_tar_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.mode = 0o644
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def _build_artifacts(
    tmp_path: Path,
    *,
    wheel_extra: Mapping[str, bytes] | None = None,
    sdist_extra: Mapping[str, bytes] | None = None,
    entry_points: bytes = _ENTRY_POINTS,
    pyproject: bytes = _PYPROJECT,
) -> tuple[Path, Path]:
    wheel = tmp_path / f"cisco_sccfm_devkit-{_VERSION}-py3-none-any.whl"
    wheel_files = {
        "cisco_sccfm_cli/__init__.py": b"",
        "cisco_sccfm_core/__init__.py": b"",
        f"{_DIST_INFO}/METADATA": b"Name: cisco-sccfm-devkit\nVersion: 1.2.3\n",
        f"{_DIST_INFO}/WHEEL": b"Wheel-Version: 1.0\n",
        f"{_DIST_INFO}/entry_points.txt": entry_points,
        f"{_DIST_INFO}/RECORD": b"",
        **(wheel_extra or {}),
    }
    with zipfile.ZipFile(wheel, mode="w") as archive:
        for name, content in wheel_files.items():
            archive.writestr(name, content)

    sdist = tmp_path / f"cisco_sccfm_devkit-{_VERSION}.tar.gz"
    prefix = f"cisco_sccfm_devkit-{_VERSION}"
    sdist_files = {
        "LICENSE": b"Apache-2.0\n",
        "LICENSES/Apache-2.0.txt": b"Apache-2.0\n",
        "PKG-INFO": b"Name: cisco-sccfm-devkit\nVersion: 1.2.3\n",
        "README.md": b"# Synthetic package\n",
        "cisco_sccfm_cli/__init__.py": b"",
        "cisco_sccfm_core/__init__.py": b"",
        "pyproject.toml": pyproject,
        **(sdist_extra or {}),
    }
    with tarfile.open(sdist, mode="w:gz") as archive:
        for name, content in sdist_files.items():
            _write_tar_file(archive, f"{prefix}/{name}", content)
    return wheel, sdist


def test_verifier_accepts_public_artifact_pair(tmp_path: Path) -> None:
    wheel, sdist = _build_artifacts(tmp_path)

    result = verify_python_artifacts(wheel, sdist)

    assert result.wheel_files == 6
    assert result.sdist_files == 7


def test_wheel_verifier_accepts_public_wheel_without_sdist(tmp_path: Path) -> None:
    wheel, _ = _build_artifacts(tmp_path)

    result = verify_python_wheel(wheel)

    assert result.version == _VERSION
    assert result.files == 6


@pytest.mark.parametrize(
    ("artifact", "member"),
    [
        ("wheel", "cisco_sccfm_scripts/devkit_cli.py"),
        ("sdist", "cisco_sccfm_scripts/devkit_cli.py"),
        ("wheel", "cisco_sccfm_scripts/bin/devkit"),
        ("sdist", "cisco_sccfm_scripts/bin/devkit"),
        ("wheel", "devtools/pyproject.toml"),
        ("sdist", "devtools/pyproject.toml"),
        ("wheel", "cisco_sccfm_cli/commands/tests/test_command.py"),
        ("wheel", "cisco_sccfm_cli/e2e/live_tenant.py"),
        ("wheel", "cisco_sccfm_core/__pycache__/service.pyc"),
        ("sdist", "cisco_sccfm_core/.env.production"),
        ("sdist", "cisco_sccfm_cli/private.pem"),
    ],
)
def test_verifier_rejects_non_public_members(tmp_path: Path, artifact: str, member: str) -> None:
    wheel_extra = {member: b"synthetic\n"} if artifact == "wheel" else None
    sdist_extra = {member: b"synthetic\n"} if artifact == "sdist" else None
    wheel, sdist = _build_artifacts(
        tmp_path,
        wheel_extra=wheel_extra,
        sdist_extra=sdist_extra,
    )

    with pytest.raises(PythonArtifactVerificationError):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_additional_wheel_entry_point(tmp_path: Path) -> None:
    entry_points = _ENTRY_POINTS + b"devkit=cisco_sccfm_scripts.devkit_cli:main\n"
    wheel, sdist = _build_artifacts(tmp_path, entry_points=entry_points)

    with pytest.raises(PythonArtifactVerificationError, match="exactly the sccfm-cli"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_additional_sdist_entry_point(tmp_path: Path) -> None:
    pyproject = _PYPROJECT + b'devkit = "cisco_sccfm_scripts.devkit_cli:main"\n'
    wheel, sdist = _build_artifacts(tmp_path, pyproject=pyproject)

    with pytest.raises(PythonArtifactVerificationError, match="exactly the sccfm-cli"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_additional_sdist_package_root(tmp_path: Path) -> None:
    pyproject = _PYPROJECT.replace(
        b'    { include = "cisco_sccfm_core" },\n',
        b'    { include = "cisco_sccfm_core" },\n' b'    { include = "cisco_sccfm_scripts" },\n',
    )
    wheel, sdist = _build_artifacts(tmp_path, pyproject=pyproject)

    with pytest.raises(PythonArtifactVerificationError, match="unexpected package roots"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_mismatched_versions(tmp_path: Path) -> None:
    wheel, sdist = _build_artifacts(tmp_path)
    renamed_sdist = sdist.with_name("cisco_sccfm_devkit-1.2.4.tar.gz")
    sdist.rename(renamed_sdist)

    with pytest.raises(PythonArtifactVerificationError, match="versions do not match"):
        verify_python_artifacts(wheel, renamed_sdist)
