# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for contributor-facing lint and pre-commit configuration."""

from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any, cast

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _pre_commit_hooks() -> dict[str, dict[str, Any]]:
    config = cast(
        dict[str, Any],
        yaml.safe_load((PROJECT_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")),
    )
    hooks: dict[str, dict[str, Any]] = {}
    for repository in cast(list[dict[str, Any]], config["repos"]):
        for hook in cast(list[dict[str, Any]], repository["hooks"]):
            hooks[cast(str, hook["id"])] = hook
    return hooks


def test_type_markers_use_the_empty_file_convention() -> None:
    assert "exclude" not in _pre_commit_hooks()["end-of-file-fixer"]
    for package in ("cisco_sccfm_cli", "cisco_sccfm_core"):
        assert (PROJECT_ROOT / package / "py.typed").read_bytes() == b""


def test_doctoc_only_matches_intended_documents() -> None:
    files = cast(str, _pre_commit_hooks()["doctoc"]["files"])
    matcher = re.compile(files)

    assert matcher.fullmatch("README.md")
    assert matcher.fullmatch("INSTALL.md")
    assert matcher.fullmatch("sccfm-ansible/README.md")
    assert not matcher.fullmatch("docs/README.md")
    assert not matcher.fullmatch("skills/sccfm-ansible/README.md")


def test_flake8_e402_exception_is_limited_to_ansible_plugin_layouts() -> None:
    config = configparser.ConfigParser()
    config.read(PROJECT_ROOT / ".flake8", encoding="utf-8")
    flake8 = config["flake8"]

    assert "E402" not in flake8["extend-ignore"].split(",")
    exceptions = {line.strip() for line in flake8["per-file-ignores"].splitlines() if line.strip()}
    assert exceptions == {
        "sccfm-ansible/plugins/inventory/*.py:E402",
        "sccfm-ansible/plugins/lookup/*.py:E402",
        "sccfm-ansible/plugins/modules/*.py:E402",
    }
