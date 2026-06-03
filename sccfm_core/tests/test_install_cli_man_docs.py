# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import install_cli_man_docs


def test_default_man_root_uses_xdg_data_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xdg_data_home = tmp_path / "xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))

    assert install_cli_man_docs.default_man_root() == xdg_data_home / "man"


def test_install_man_pages_replaces_existing_sccfm_pages(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    source_dir.mkdir()
    (source_dir / "sccfm-cli.1").write_text("new root page\n", encoding="utf-8")
    (source_dir / "sccfm-cli-configure.1").write_text("new configure page\n", encoding="utf-8")

    target_dir = tmp_path / "man" / "man1"
    target_dir.mkdir(parents=True)
    (target_dir / "sccfm-cli.1").write_text("old root page\n", encoding="utf-8")
    (target_dir / "other-cli.1").write_text("unrelated page\n", encoding="utf-8")

    installed = install_cli_man_docs.install_man_pages(source_dir, tmp_path / "man")

    assert installed == 2
    assert (target_dir / "sccfm-cli.1").read_text(encoding="utf-8") == "new root page\n"
    assert (target_dir / "sccfm-cli-configure.1").read_text(
        encoding="utf-8"
    ) == "new configure page\n"
    assert (target_dir / "other-cli.1").read_text(encoding="utf-8") == "unrelated page\n"


def test_install_man_pages_requires_generated_pages(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    source_dir.mkdir()

    with pytest.raises(install_cli_man_docs.ManPageInstallError):
        install_cli_man_docs.install_man_pages(source_dir, tmp_path / "man")


def test_man_root_in_manpath_resolves_paths(tmp_path: Path) -> None:
    man_root = tmp_path / "man"
    man_root.mkdir()

    assert install_cli_man_docs.man_root_in_manpath(man_root, [tmp_path / "." / "man"])
    assert not install_cli_man_docs.man_root_in_manpath(man_root, [tmp_path / "other"])
