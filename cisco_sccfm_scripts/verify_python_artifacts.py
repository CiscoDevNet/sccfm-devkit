# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Verify the public member and entry-point policy for Python artifacts."""

from __future__ import annotations

import argparse
import configparser
import io
import stat
import tarfile
import tomllib
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

_DISTRIBUTION_STEM = "cisco_sccfm_devkit"
_PACKAGE_ROOTS = frozenset({"cisco_sccfm_cli", "cisco_sccfm_core"})
_SDIST_METADATA_ROOTS = frozenset(
    {
        "LICENSE",
        "LICENSES",
        "PKG-INFO",
        "README.md",
        "pyproject.toml",
    }
)
_EXPECTED_SCRIPTS = {"sccfm-cli": "cisco_sccfm_cli.cli:cli"}
_FORBIDDEN_DIRECTORY_NAMES = frozenset(
    {
        ".cache",
        ".eggs",
        ".git",
        ".mypy_cache",
        ".poetry_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "cisco_sccfm_scripts",
        "devtools",
        "e2e",
        "test",
        "tests",
    }
)
_FORBIDDEN_EXACT_NAMES = frozenset(
    {
        ".coverage",
        ".ds_store",
        ".env",
        ".netrc",
        ".vault_pass",
        "cachedir.tag",
        "coverage.xml",
        "credentials",
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
        "vault.json",
        "vault.yaml",
        "vault.yml",
    }
)
_FORBIDDEN_KEY_PREFIXES = ("id_dsa", "id_ecdsa", "id_ed25519", "id_rsa")
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
    ".pyc",
    ".pyo",
    ".retry",
    ".sqlite",
    ".sqlite3",
    ".swo",
    ".swp",
)


class PythonArtifactVerificationError(RuntimeError):
    """Raised when a wheel or sdist violates the public artifact policy."""


class _EntryPointParser(configparser.ConfigParser):
    """Config parser that preserves case-sensitive entry-point names."""

    def optionxform(self, optionstr: str) -> str:
        """Return an entry-point name unchanged."""
        return optionstr


@dataclass(frozen=True)
class PythonArtifactVerification:
    """Counts from a successfully verified wheel and sdist."""

    wheel_files: int
    sdist_files: int


def _wheel_version(path: Path) -> str:
    """Return the version encoded in the expected pure-Python wheel filename."""
    parts = path.name.removesuffix(".whl").split("-")
    if path.suffix != ".whl" or len(parts) != 5:
        raise PythonArtifactVerificationError(f"unexpected wheel filename: {path.name}")
    distribution, version, python_tag, abi_tag, platform_tag = parts
    if (
        distribution != _DISTRIBUTION_STEM
        or not version
        or python_tag != "py3"
        or abi_tag != "none"
        or platform_tag != "any"
    ):
        raise PythonArtifactVerificationError(f"unexpected wheel filename: {path.name}")
    return version


def _sdist_version(path: Path) -> str:
    """Return the version encoded in the expected sdist filename."""
    prefix = f"{_DISTRIBUTION_STEM}-"
    suffix = ".tar.gz"
    if not path.name.startswith(prefix) or not path.name.endswith(suffix):
        raise PythonArtifactVerificationError(f"unexpected sdist filename: {path.name}")
    version = path.name[len(prefix) : -len(suffix)]
    if not version or "/" in version or "\\" in version:
        raise PythonArtifactVerificationError(f"unexpected sdist filename: {path.name}")
    return version


def _member_parts(raw_name: str) -> tuple[str, ...]:
    """Return canonical POSIX member parts, rejecting traversal and aliases."""
    if not raw_name or "\x00" in raw_name or "\\" in raw_name or raw_name.startswith("/"):
        raise PythonArtifactVerificationError("artifact contains an invalid member path")
    name = raw_name[:-1] if raw_name.endswith("/") else raw_name
    parts = tuple(name.split("/"))
    if not name or any(part in {"", ".", ".."} for part in parts):
        raise PythonArtifactVerificationError("artifact contains a non-canonical member path")
    if PurePosixPath(name).as_posix() != name:
        raise PythonArtifactVerificationError("artifact contains a non-canonical member path")
    return parts


def _check_forbidden_path(parts: tuple[str, ...], display_name: str) -> None:
    """Reject test, cache, credential, and local-data member paths."""
    lowered = tuple(part.lower() for part in parts)
    if any(part in _FORBIDDEN_DIRECTORY_NAMES for part in lowered):
        raise PythonArtifactVerificationError(f"forbidden directory in artifact: {display_name}")

    basename = lowered[-1]
    if basename in {"conftest.py", "test.py", "tests.py"} or (
        basename.endswith(".py") and (basename.startswith("test_") or basename.endswith("_test.py"))
    ):
        raise PythonArtifactVerificationError(f"test implementation in artifact: {display_name}")
    if basename in _FORBIDDEN_EXACT_NAMES:
        raise PythonArtifactVerificationError(
            f"sensitive or local file in artifact: {display_name}"
        )
    if basename.startswith((".env", ".vault_pass")):
        raise PythonArtifactVerificationError(f"credential-like file in artifact: {display_name}")
    if basename.startswith(("vault.yml.", "vault.yaml.")):
        raise PythonArtifactVerificationError(f"vault backup in artifact: {display_name}")
    if basename.startswith(_FORBIDDEN_KEY_PREFIXES):
        raise PythonArtifactVerificationError(f"private-key-like file in artifact: {display_name}")
    if basename.endswith(_FORBIDDEN_SUFFIXES) or basename.endswith("~"):
        raise PythonArtifactVerificationError(f"local-data file in artifact: {display_name}")


def _entry_points(raw: bytes) -> dict[tuple[str, str], str]:
    """Parse a wheel entry-points file into an exact, comparable map."""
    parser = _EntryPointParser(interpolation=None, delimiters=("=",), strict=True)
    try:
        parser.read_file(io.StringIO(raw.decode("utf-8")))
    except (UnicodeDecodeError, configparser.Error) as exc:
        raise PythonArtifactVerificationError("wheel has invalid entry-point metadata") from exc
    if parser.defaults():
        raise PythonArtifactVerificationError("wheel has unexpected default entry points")
    return {
        (section, name): target.strip()
        for section in parser.sections()
        for name, target in parser.items(section, raw=True)
    }


def _verify_entry_points(raw: bytes) -> None:
    """Require the sole supported public console entry point."""
    expected = {("console_scripts", name): target for name, target in _EXPECTED_SCRIPTS.items()}
    if _entry_points(raw) != expected:
        raise PythonArtifactVerificationError("wheel does not expose exactly the sccfm-cli command")


def _verify_sdist_pyproject(raw: bytes) -> None:
    """Ensure a wheel rebuilt from the sdist retains the public package policy."""
    try:
        pyproject: dict[str, Any] = tomllib.loads(raw.decode("utf-8"))
        poetry = pyproject["tool"]["poetry"]
    except (KeyError, TypeError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PythonArtifactVerificationError("sdist has invalid Poetry metadata") from exc
    if not isinstance(poetry, dict):
        raise PythonArtifactVerificationError("sdist has invalid Poetry metadata")

    packages = poetry.get("packages")
    if not isinstance(packages, list) or len(packages) != len(_PACKAGE_ROOTS):
        raise PythonArtifactVerificationError("sdist declares unexpected package roots")
    package_roots: set[str] = set()
    for package in packages:
        if not isinstance(package, dict) or set(package) != {"include"}:
            raise PythonArtifactVerificationError("sdist declares unexpected package roots")
        included = package.get("include")
        if not isinstance(included, str):
            raise PythonArtifactVerificationError("sdist declares unexpected package roots")
        package_roots.add(included)
    if package_roots != _PACKAGE_ROOTS:
        raise PythonArtifactVerificationError("sdist declares unexpected package roots")

    scripts = poetry.get("scripts")
    if scripts != _EXPECTED_SCRIPTS:
        raise PythonArtifactVerificationError("sdist does not expose exactly the sccfm-cli command")


def _verify_wheel(path: Path, version: str) -> int:
    """Verify wheel roots, paths, member types, and entry-point metadata."""
    expected_dist_info = f"{_DISTRIBUTION_STEM}-{version}.dist-info"
    allowed_roots = _PACKAGE_ROOTS | {expected_dist_info}
    try:
        with zipfile.ZipFile(path) as archive:
            members: dict[str, zipfile.ZipInfo] = {}
            for member in archive.infolist():
                parts = _member_parts(member.filename)
                name = "/".join(parts)
                if name in members:
                    raise PythonArtifactVerificationError(
                        f"wheel contains a duplicate member: {name}"
                    )
                mode = member.external_attr >> 16
                if member.is_dir() or stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                    raise PythonArtifactVerificationError(
                        f"wheel contains a non-regular member: {name}"
                    )
                if parts[0] not in allowed_roots:
                    raise PythonArtifactVerificationError(
                        f"unexpected wheel top-level path: {parts[0]}"
                    )
                _check_forbidden_path(parts, name)
                members[name] = member

            actual_roots = {name.split("/", maxsplit=1)[0] for name in members}
            if actual_roots != allowed_roots:
                raise PythonArtifactVerificationError("wheel does not contain the expected roots")
            entry_points_name = f"{expected_dist_info}/entry_points.txt"
            if entry_points_name not in members:
                raise PythonArtifactVerificationError("wheel has no entry-point metadata")
            _verify_entry_points(archive.read(members[entry_points_name]))
    except (OSError, zipfile.BadZipFile) as exc:
        raise PythonArtifactVerificationError("wheel is not a readable ZIP archive") from exc
    return len(members)


def _read_tar_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    """Read a required regular sdist member."""
    extracted = archive.extractfile(member)
    if extracted is None:
        raise PythonArtifactVerificationError(f"could not read sdist member: {member.name}")
    return extracted.read()


def _verify_sdist(path: Path, version: str) -> int:
    """Verify sdist roots, paths, member types, and embedded build metadata."""
    expected_prefix = f"{_DISTRIBUTION_STEM}-{version}"
    allowed_roots = _PACKAGE_ROOTS | _SDIST_METADATA_ROOTS
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members: dict[str, tarfile.TarInfo] = {}
            relative_members: dict[str, tarfile.TarInfo] = {}
            for member in archive.getmembers():
                parts = _member_parts(member.name)
                name = "/".join(parts)
                if name in members:
                    raise PythonArtifactVerificationError(
                        f"sdist contains a duplicate member: {name}"
                    )
                if not (member.isfile() or member.isdir()):
                    raise PythonArtifactVerificationError(
                        f"sdist contains a non-regular member: {name}"
                    )
                if parts[0] != expected_prefix:
                    raise PythonArtifactVerificationError(
                        f"unexpected sdist archive prefix: {parts[0]}"
                    )
                members[name] = member
                if len(parts) == 1:
                    if not member.isdir():
                        raise PythonArtifactVerificationError(
                            "sdist root member is not a directory"
                        )
                    continue

                relative_parts = parts[1:]
                relative_name = "/".join(relative_parts)
                if relative_name in relative_members:
                    raise PythonArtifactVerificationError(
                        f"sdist contains a duplicate member: {relative_name}"
                    )
                if relative_parts[0] not in allowed_roots:
                    raise PythonArtifactVerificationError(
                        f"unexpected sdist top-level path: {relative_parts[0]}"
                    )
                _check_forbidden_path(relative_parts, relative_name)
                relative_members[relative_name] = member

            actual_package_roots = {
                name.split("/", maxsplit=1)[0]
                for name, member in relative_members.items()
                if member.isfile() and name.split("/", maxsplit=1)[0] in _PACKAGE_ROOTS
            }
            if actual_package_roots != _PACKAGE_ROOTS:
                raise PythonArtifactVerificationError(
                    "sdist does not contain the expected packages"
                )
            pyproject_name = "pyproject.toml"
            pyproject_member = relative_members.get(pyproject_name)
            if pyproject_member is None or not pyproject_member.isfile():
                raise PythonArtifactVerificationError("sdist has no pyproject.toml")
            _verify_sdist_pyproject(_read_tar_member(archive, pyproject_member))
    except (OSError, tarfile.TarError) as exc:
        raise PythonArtifactVerificationError("sdist is not a readable tar.gz archive") from exc
    return sum(member.isfile() for member in members.values())


def verify_python_artifacts(wheel: Path, sdist: Path) -> PythonArtifactVerification:
    """Verify one matching wheel and sdist against the public artifact policy."""
    if wheel.is_symlink() or not wheel.is_file():
        raise PythonArtifactVerificationError("wheel must be a regular file")
    if sdist.is_symlink() or not sdist.is_file():
        raise PythonArtifactVerificationError("sdist must be a regular file")

    wheel_version = _wheel_version(wheel)
    sdist_version = _sdist_version(sdist)
    if wheel_version != sdist_version:
        raise PythonArtifactVerificationError("wheel and sdist versions do not match")

    return PythonArtifactVerification(
        wheel_files=_verify_wheel(wheel, wheel_version),
        sdist_files=_verify_sdist(sdist, sdist_version),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line wrapper for CI and publication automation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("sdist", type=Path)
    args = parser.parse_args(argv)

    try:
        result = verify_python_artifacts(args.wheel, args.sdist)
    except PythonArtifactVerificationError as exc:
        print(f"Python artifacts rejected: {exc}")
        return 1

    print(
        "Python artifacts verified: "
        f"wheel_files={result.wheel_files} sdist_files={result.sdist_files}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
