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
_DESCRIPTION = b"# Synthetic package\n\nSee [documentation](https://example.com/docs).\n"
_LICENSE = (Path(__file__).resolve().parents[1] / "LICENSE").read_bytes()
_METADATA_HEADERS = (
    b"Name: cisco-sccfm-devkit\n"
    b"Version: 1.2.3\n"
    b"License-Expression: Apache-2.0\n"
    b"License-File: LICENSE\n"
    b"License-File: LICENSES/Apache-2.0.txt\n"
    b"Description-Content-Type: text/markdown\n\n"
)
_REQUIRED_PROJECT_DOCUMENTS = {
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "INSTALL.md",
    "SECURITY.md",
}
_PYPROJECT = b"""\
[project]

[project.scripts]
sccfm-cli = "cisco_sccfm_cli.cli:cli"

[tool.poetry]
packages = [
    { include = "cisco_sccfm_cli" },
    { include = "cisco_sccfm_core" },
]
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
    wheel_description: bytes = _DESCRIPTION,
    sdist_description: bytes = _DESCRIPTION,
    omitted_sdist_files: frozenset[str] = frozenset(),
) -> tuple[Path, Path]:
    wheel = tmp_path / f"cisco_sccfm_devkit-{_VERSION}-py3-none-any.whl"
    wheel_files = {
        "cisco_sccfm_cli/__init__.py": b"",
        "cisco_sccfm_core/__init__.py": b"",
        f"{_DIST_INFO}/METADATA": _METADATA_HEADERS + wheel_description,
        f"{_DIST_INFO}/WHEEL": b"Wheel-Version: 1.0\n",
        f"{_DIST_INFO}/entry_points.txt": entry_points,
        f"{_DIST_INFO}/licenses/LICENSE": _LICENSE,
        f"{_DIST_INFO}/licenses/LICENSES/Apache-2.0.txt": _LICENSE,
        f"{_DIST_INFO}/RECORD": b"",
        **(wheel_extra or {}),
    }
    with zipfile.ZipFile(wheel, mode="w") as archive:
        for name, content in wheel_files.items():
            archive.writestr(name, content)

    sdist = tmp_path / f"cisco_sccfm_devkit-{_VERSION}.tar.gz"
    prefix = f"cisco_sccfm_devkit-{_VERSION}"
    sdist_files = {
        "LICENSE": _LICENSE,
        "LICENSES/Apache-2.0.txt": _LICENSE,
        "CHANGELOG.md": b"# Changelog\n",
        "CONTRIBUTING.md": b"# Contributing\n",
        "INSTALL.md": b"# Installation\n",
        "PKG-INFO": _METADATA_HEADERS + sdist_description,
        "README.md": sdist_description,
        "SECURITY.md": b"# Security\n",
        "cisco_sccfm_cli/__init__.py": b"",
        "cisco_sccfm_core/__init__.py": b"",
        "pyproject.toml": pyproject,
        **(sdist_extra or {}),
    }
    with tarfile.open(sdist, mode="w:gz") as archive:
        for name, content in sdist_files.items():
            if name in omitted_sdist_files:
                continue
            _write_tar_file(archive, f"{prefix}/{name}", content)
    return wheel, sdist


def test_verifier_accepts_public_artifact_pair(tmp_path: Path) -> None:
    wheel, sdist = _build_artifacts(tmp_path)

    result = verify_python_artifacts(wheel, sdist)

    assert result.wheel_files == 8
    assert result.sdist_files == 11


def test_wheel_verifier_accepts_public_wheel_without_sdist(tmp_path: Path) -> None:
    wheel, _ = _build_artifacts(tmp_path)

    result = verify_python_wheel(wheel)

    assert result.version == _VERSION
    assert result.files == 8


@pytest.mark.parametrize(
    ("artifact", "member"),
    [
        ("wheel", "cisco_sccfm_scripts/interactive_cli.py"),
        ("sdist", "cisco_sccfm_scripts/interactive_cli.py"),
        ("wheel", "cisco_sccfm_scripts/bin/sccfm-cli-interactive"),
        ("sdist", "cisco_sccfm_scripts/bin/sccfm-cli-interactive"),
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
    entry_points = (
        _ENTRY_POINTS + b"sccfm-cli-interactive=cisco_sccfm_scripts.interactive_cli:main\n"
    )
    wheel, sdist = _build_artifacts(tmp_path, entry_points=entry_points)

    with pytest.raises(PythonArtifactVerificationError, match="exactly the sccfm-cli"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_additional_sdist_entry_point(tmp_path: Path) -> None:
    pyproject = _PYPROJECT.replace(
        b'sccfm-cli = "cisco_sccfm_cli.cli:cli"\n',
        b'sccfm-cli = "cisco_sccfm_cli.cli:cli"\n'
        b'sccfm-cli-interactive = "cisco_sccfm_scripts.interactive_cli:main"\n',
    )
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


@pytest.mark.parametrize("document", sorted(_REQUIRED_PROJECT_DOCUMENTS))
def test_verifier_rejects_missing_sdist_document(tmp_path: Path, document: str) -> None:
    wheel, sdist = _build_artifacts(
        tmp_path,
        omitted_sdist_files=frozenset({document}),
    )

    with pytest.raises(PythonArtifactVerificationError, match="required project documents"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_relative_link_in_wheel_description(tmp_path: Path) -> None:
    wheel, sdist = _build_artifacts(
        tmp_path,
        wheel_description=b"See [documentation](docs/README.md).\n",
    )

    with pytest.raises(PythonArtifactVerificationError, match="relative Markdown link"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_relative_link_in_sdist_description(tmp_path: Path) -> None:
    wheel, sdist = _build_artifacts(
        tmp_path,
        sdist_description=b"See [license](LICENSE).\n",
    )

    with pytest.raises(PythonArtifactVerificationError, match="relative Markdown link"):
        verify_python_artifacts(wheel, sdist)


@pytest.mark.parametrize("artifact", ["wheel", "sdist"])
def test_verifier_rejects_incomplete_license_text(tmp_path: Path, artifact: str) -> None:
    wheel_license = f"{_DIST_INFO}/licenses/LICENSE"
    wheel_extra = {wheel_license: b"not the license\n"} if artifact == "wheel" else None
    sdist_extra = {"LICENSE": b"not the license\n"} if artifact == "sdist" else None
    wheel, sdist = _build_artifacts(
        tmp_path,
        wheel_extra=wheel_extra,
        sdist_extra=sdist_extra,
    )

    with pytest.raises(PythonArtifactVerificationError, match="Apache-2.0 text"):
        verify_python_artifacts(wheel, sdist)


def test_verifier_rejects_incorrect_license_expression(tmp_path: Path) -> None:
    metadata = (_METADATA_HEADERS + _DESCRIPTION).replace(
        b"License-Expression: Apache-2.0", b"License-Expression: MIT"
    )
    wheel, sdist = _build_artifacts(
        tmp_path,
        wheel_extra={f"{_DIST_INFO}/METADATA": metadata},
    )

    with pytest.raises(PythonArtifactVerificationError, match="license expression"):
        verify_python_artifacts(wheel, sdist)


@pytest.mark.parametrize("artifact", ["wheel", "sdist"])
def test_verifier_rejects_duplicate_license_file_header(tmp_path: Path, artifact: str) -> None:
    metadata = (_METADATA_HEADERS + _DESCRIPTION).replace(
        b"License-File: LICENSE\n",
        b"License-File: LICENSE\nLicense-File: LICENSE\n",
    )
    wheel_extra = {f"{_DIST_INFO}/METADATA": metadata} if artifact == "wheel" else None
    sdist_extra = {"PKG-INFO": metadata} if artifact == "sdist" else None
    wheel, sdist = _build_artifacts(
        tmp_path,
        wheel_extra=wheel_extra,
        sdist_extra=sdist_extra,
    )

    with pytest.raises(PythonArtifactVerificationError, match="license files"):
        verify_python_artifacts(wheel, sdist)
