# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for project environment setup scripts."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPTS = (
    PROJECT_ROOT / "cisco_sccfm_scripts" / "setup_ci_environment.sh",
    PROJECT_ROOT / "cisco_sccfm_scripts" / "setup_environment.sh",
)
LOCAL_SETUP_SCRIPT = PROJECT_ROOT / "cisco_sccfm_scripts" / "setup_environment.sh"
POETRY_GROUP_ARGUMENT = re.compile(
    r"\binstall --with (?P<groups>[A-Za-z0-9_-]+(?:,[A-Za-z0-9_-]+)*)"
)


def _defined_poetry_groups() -> set[str]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file_handle:
        pyproject: dict[str, object] = tomllib.load(file_handle)

    tool = pyproject["tool"]
    assert isinstance(tool, dict)
    poetry = tool["poetry"]
    assert isinstance(poetry, dict)
    groups = poetry["group"]
    assert isinstance(groups, dict)
    return {str(group) for group in groups}


def test_setup_scripts_request_defined_poetry_groups() -> None:
    defined_groups = _defined_poetry_groups()

    for script in SETUP_SCRIPTS:
        source = script.read_text(encoding="utf-8")
        matches = list(POETRY_GROUP_ARGUMENT.finditer(source))
        assert matches, f"{script.name} does not install a Poetry dependency group"

        for match in matches:
            requested_groups = set(match.group("groups").split(","))
            assert requested_groups <= defined_groups, (
                f"{script.name} requests undefined Poetry groups: "
                f"{sorted(requested_groups - defined_groups)}"
            )


def test_setup_scripts_read_all_pyenv_versions_with_pipefail_enabled() -> None:
    for script in SETUP_SCRIPTS:
        source = script.read_text(encoding="utf-8")

        assert 'grep -Fx "${PYTHON_VERSION}" >/dev/null' in source
        assert "grep -q" not in source


def test_setup_scripts_isolate_poetry_from_project_runtime() -> None:
    for script in SETUP_SCRIPTS:
        source = script.read_text(encoding="utf-8")
        poetry_install_lines = [
            line.strip() for line in source.splitlines() if 'pip" install poetry' in line
        ]

        assert 'poetry_venv="${VENV_DIR}/.poetry"' in source
        assert poetry_install_lines == ['"${poetry_venv}/bin/pip" install poetry']
        assert '"${poetry_venv}/bin/poetry" install --with dev' in source
        assert 'ln -sfn "../.poetry/bin/poetry" "${VENV_DIR}/bin/poetry"' in source


def test_local_setup_validates_runtime_dependencies() -> None:
    source = LOCAL_SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "python -m pip check" in source
    assert 'importlib.metadata.version("poetry")' in source


@pytest.mark.parametrize("install_status", [0, 73])
def test_ci_setup_installs_al2023_dependencies_and_propagates_failures(
    tmp_path: Path, install_status: int
) -> None:
    """Run the real installer with a controlled AL2023 package manager."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "packages.log"
    commands = {
        "sudo": '#!/bin/bash\nexec "$@"\n',
        "dnf": (
            "#!/bin/bash\n"
            'printf "%s\\n" "$*" >> "$SCCFM_TEST_LOG"\n'
            'if [[ "$1" == groupinstall ]]; then exit 0; fi\n'
            'for arg in "$@"; do\n'
            '  if [[ "$arg" == openssl11-devel ]]; then\n'
            '    echo "No match for argument: openssl11-devel" >&2; exit 1\n'
            "  fi\n"
            "done\n"
            f"exit {install_status}\n"
        ),
    }
    for name, content in commands.items():
        executable = bin_dir / name
        executable.write_text(content, encoding="utf-8")
        executable.chmod(0o755)
    (bin_dir / "yum").symlink_to(bin_dir / "dnf")

    result = subprocess.run(
        ["/bin/bash", "-c", f"{_ci_setup_functions()}\ninstall_system_packages"],
        env={"PATH": str(bin_dir), "SCCFM_TEST_LOG": str(log)},
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == install_status, result.stderr
    assert "openssl-devel" in log.read_text(encoding="utf-8")


def _ci_setup_functions() -> str:
    """Load real definitions without running the script's orchestration."""
    source = SETUP_SCRIPTS[0].read_text(encoding="utf-8")
    functions = source[source.index("install_system_packages() {") :]
    return "set -euo pipefail\n" + functions[: functions.index("\ninstall_system_packages\n")]


def test_ci_setup_rejects_python_without_ssl_before_creating_venv(
    tmp_path: Path,
) -> None:
    python = tmp_path / "versions/3.12.4/bin/python3"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == -c ]]; then echo "No module named ssl" >&2; exit 1; fi\n'
        'echo "venv creation attempted"; exit 87\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    result = subprocess.run(
        [
            "/bin/bash",
            "-c",
            f"{_ci_setup_functions()}\n"
            "PYTHON_VERSION=3.12.4\n"
            'VENV_DIR="$1/venv"\n'
            'pyenv() { printf "%s\\n" "$SCCFM_TEST_PYENV_ROOT"; }\n'
            "create_venv",
            "setup-test",
            str(tmp_path),
        ],
        env={"SCCFM_TEST_PYENV_ROOT": str(tmp_path)},
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert "No module named ssl" in result.stderr
    assert "venv creation attempted" not in result.stdout
