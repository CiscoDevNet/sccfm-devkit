# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cisco_sccfm_scripts import (
    check_doc_artifacts,
    generate_ansible_docs,
    generate_cli_docs,
    generate_cli_man_docs,
)


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


def test_cli_man_docs_refuse_to_overwrite_non_empty_custom_directory(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "man1"
    default_docs_root = tmp_path / "default-man1"
    docs_root.mkdir()
    sentinel = docs_root / "sccfm-cli.1"
    sentinel.write_text(".TH old\n", encoding="utf-8")

    with pytest.raises(generate_cli_man_docs.OutputDirectoryError):
        generate_cli_man_docs._write_files(
            {docs_root / "sccfm-cli.1": ".TH new\n"},
            docs_root,
            default_docs_root,
        )

    assert sentinel.read_text(encoding="utf-8") == ".TH old\n"


def test_cli_man_docs_replace_default_directory(tmp_path: Path) -> None:
    docs_root = tmp_path / "man1"
    default_docs_root = docs_root
    docs_root.mkdir()
    stale = docs_root / "old.1"
    stale.write_text("old\n", encoding="utf-8")

    generate_cli_man_docs._write_files(
        {docs_root / "sccfm-cli.1": ".TH new\n"},
        docs_root,
        default_docs_root,
    )

    assert not stale.exists()
    assert (docs_root / "sccfm-cli.1").read_text(encoding="utf-8") == ".TH new\n"


def test_cli_man_docs_restore_source_date_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "123")

    with generate_cli_man_docs._source_date_environment("456"):
        assert os.environ["SOURCE_DATE_EPOCH"] == "456"

    assert os.environ["SOURCE_DATE_EPOCH"] == "123"


def test_cli_man_docs_remove_paragraph_macro_after_section() -> None:
    content = ".SH COMMANDS\n.PP\n\\fBconfigure\\fP\n"

    cleaned = generate_cli_man_docs._clean_man_page(content)

    assert cleaned == ".SH COMMANDS\n\\fBconfigure\\fP\n"


def test_doc_artifacts_detect_terminal_escape_sequences(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    artifact = docs_root / "sccfm-cli.1"
    artifact.write_text("NAME\n\x1b[1msccfm-cli\x1b[0m\n", encoding="utf-8")

    issues = check_doc_artifacts.check_docs(docs_root)

    assert len(issues) == 1
    assert issues[0].path == artifact
    assert issues[0].description == "contains ANSI terminal escape sequence"
    assert issues[0].line == 2
    assert issues[0].column == 1


def test_doc_artifacts_detect_replacement_characters(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    artifact = docs_root / "module.md"
    artifact.write_text("MODULE �[1mcisco.sccfm.example\n", encoding="utf-8")

    issues = check_doc_artifacts.check_docs(docs_root)

    assert len(issues) == 1
    assert issues[0].path == artifact
    assert issues[0].description == "contains Unicode replacement character"
    assert issues[0].line == 1
    assert issues[0].column == 8


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


def test_generated_docs_include_jekyll_front_matter() -> None:
    cli_page = generate_cli_docs._render_page((), "Usage: sccfm-cli [OPTIONS]")
    ansible_page = generate_ansible_docs._render_page(
        "cisco.sccfm.sccfm",
        "ansible-doc -t inventory cisco.sccfm.sccfm",
        "Inventory docs",
    )

    assert cli_page.startswith('---\nlayout: page\ntitle: "sccfm-cli"\n---\n\n')
    assert ansible_page.startswith('---\nlayout: page\ntitle: "cisco.sccfm.sccfm"\n---\n\n')


def test_generated_docs_include_reference_back_links() -> None:
    cli_page = generate_cli_docs._render_page((), "Usage: sccfm-cli [OPTIONS]")
    ansible_page = generate_ansible_docs._render_page(
        "cisco.sccfm.sccfm",
        "ansible-doc -t inventory cisco.sccfm.sccfm",
        "Inventory docs",
    )

    assert "[Back to CLI Reference](index.html){:.doc-button}" in cli_page
    assert "[Back to Ansible Reference](../index.html){:.doc-button}" in ansible_page


def test_generated_indexes_include_home_back_links() -> None:
    cli_index = generate_cli_docs._render_index(())
    ansible_index = generate_ansible_docs._render_index((), ())

    assert "[Back to Documentation Home](../index.html){:.doc-button}" in cli_index
    assert "[Back to Documentation Home](../index.html){:.doc-button}" in ansible_index


def test_generated_docs_do_not_duplicate_page_titles() -> None:
    cli_page = generate_cli_docs._render_page((), "Usage: sccfm-cli [OPTIONS]")
    cli_index = generate_cli_docs._render_index(())
    ansible_page = generate_ansible_docs._render_page(
        "cisco.sccfm.sccfm",
        "ansible-doc -t inventory cisco.sccfm.sccfm",
        "Inventory docs",
    )
    ansible_index = generate_ansible_docs._render_index((), ())

    assert "\n# sccfm-cli\n" not in cli_page
    assert "\n# sccfm-cli Reference\n" not in cli_index
    assert "\n# cisco.sccfm.sccfm\n" not in ansible_page
    assert "\n# cisco.sccfm Ansible Reference\n" not in ansible_index


def test_generated_indexes_separate_front_matter_from_content() -> None:
    cli_index = generate_cli_docs._render_index(())
    ansible_index = generate_ansible_docs._render_index((), ())

    assert 'title: "sccfm-cli Reference"\n---\n\n<!-- Generated by' in cli_index
    assert 'title: "cisco.sccfm Ansible Reference"\n---\n\n<!-- Generated by' in ansible_index


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


def test_ansible_docs_strip_terminal_control_sequences(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    collection_path = tmp_path / "tmp-collection"
    temp_source = collection_path / "ansible_collections" / "cisco" / "sccfm"
    output = (
        f"> MODULE \x1b[1mcisco.sccfm.list_managers\x1b[0m "
        f"({temp_source}/plugins/modules/list_managers.py)\n"
        "\x1b[1mOPTIONS\x1b[0m"
    )

    cleaned = generate_ansible_docs._clean_ansible_doc_output(
        output,
        project_root,
        collection_path,
    )

    assert "\x1b" not in cleaned
    assert "MODULE cisco.sccfm.list_managers" in cleaned
    assert "OPTIONS" in cleaned
    assert "sccfm-ansible/plugins/modules/list_managers.py" in cleaned


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
