# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import generate_ansible_docs, generate_cli_docs


def test_cli_docs_refuse_to_overwrite_non_empty_custom_directory(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    default_docs_root = tmp_path / "default-cli"
    docs_root.mkdir()
    sentinel = docs_root / "README.md"
    sentinel.write_text("# Hand-written docs\n", encoding="utf-8")

    with pytest.raises(generate_cli_docs.OutputDirectoryError):
        generate_cli_docs._write_files(
            {docs_root / "index.md": "new\n"},
            docs_root,
            default_docs_root,
        )

    assert sentinel.read_text(encoding="utf-8") == "# Hand-written docs\n"


def test_cli_docs_replace_default_directory(tmp_path: Path) -> None:
    docs_root = tmp_path / "cli"
    default_docs_root = docs_root
    docs_root.mkdir()
    stale = docs_root / "old.md"
    stale.write_text("old\n", encoding="utf-8")

    generate_cli_docs._write_files(
        {docs_root / "index.md": "new\n"},
        docs_root,
        default_docs_root,
    )

    assert not stale.exists()
    assert (docs_root / "index.md").read_text(encoding="utf-8") == "new\n"


def test_ansible_docs_refuse_to_overwrite_non_empty_custom_directory(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    default_docs_root = tmp_path / "default-ansible"
    docs_root.mkdir()
    sentinel = docs_root / "README.md"
    sentinel.write_text("# Hand-written docs\n", encoding="utf-8")

    with pytest.raises(generate_ansible_docs.OutputDirectoryError):
        generate_ansible_docs._write_files(
            {docs_root / "index.md": "new\n"},
            docs_root,
            default_docs_root,
        )

    assert sentinel.read_text(encoding="utf-8") == "# Hand-written docs\n"


def test_ansible_docs_wrap_output_in_liquid_raw_tags() -> None:
    output = "api_token: \"{{ lookup('env', 'SCCFM_API_TOKEN') }}\""

    page = generate_ansible_docs._render_page(
        "cisco.sccfm.sccfm",
        "ansible-doc -t inventory cisco.sccfm.sccfm",
        output,
    )

    assert "{% raw %}\n```text" in page
    assert "```\n{% endraw %}\n" in page
    assert output in page


def test_ansible_docs_normalize_temporary_source_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    collection_path = tmp_path / "tmp-collection"
    temp_source = collection_path / "ansible_collections" / "cisco" / "sccfm"
    repo_source = project_root / "sccfm-ansible"
    output = (
        f"> MODULE cisco.sccfm.list_managers ({temp_source}/plugins/modules/list_managers.py)\n"
        f"> MODULE cisco.sccfm.get_object ({repo_source}/plugins/modules/get_object.py)"
    )

    normalized = generate_ansible_docs._normalize_source_paths(
        output,
        project_root,
        collection_path,
    )

    assert str(temp_source) not in normalized
    assert str(repo_source) not in normalized
    assert "sccfm-ansible/plugins/modules/list_managers.py" in normalized
    assert "sccfm-ansible/plugins/modules/get_object.py" in normalized


def test_ansible_docs_replace_default_directory(tmp_path: Path) -> None:
    docs_root = tmp_path / "ansible"
    default_docs_root = docs_root
    module_dir = docs_root / "modules"
    module_dir.mkdir(parents=True)
    stale = module_dir / "old.md"
    stale.write_text("old\n", encoding="utf-8")

    generate_ansible_docs._write_files(
        {docs_root / "index.md": "new\n"},
        docs_root,
        default_docs_root,
    )

    assert not stale.exists()
    assert (docs_root / "index.md").read_text(encoding="utf-8") == "new\n"
