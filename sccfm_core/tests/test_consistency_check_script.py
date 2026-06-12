# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from scripts import consistency_check


def _patch_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(consistency_check, "ROOT", tmp_path)
    monkeypatch.setattr(
        consistency_check,
        "CLI_COMMANDS",
        tmp_path / "sccfm_cli" / "commands",
    )
    monkeypatch.setattr(
        consistency_check,
        "ANSIBLE_MODULES",
        tmp_path / "sccfm-ansible" / "plugins" / "modules",
    )


def _write_file(tmp_path: Path, relative_path: str, content: str) -> Path:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _require_yaml() -> None:
    if not consistency_check._HAS_YAML:
        pytest.skip("PyYAML is required for consistency-check tests")


def test_ansible_contract_checks_flag_missing_return_docs_and_example_refs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_roots(monkeypatch, tmp_path)
    module_path = _write_file(
        tmp_path,
        "sccfm-ansible/plugins/modules/list_asa_not_on_version.py",
        '''
        from ansible.module_utils.basic import AnsibleModule

        DOCUMENTATION = r"""
        ---
        module: list_asa_not_on_version
        options:
          version:
            type: str
        """

        EXAMPLES = r"""
        - name: Run example
          cisco.sccfm.list_asa_not_on_version:
            version: "9.20(3)13"
          register: result

        - name: Show undocumented key
          ansible.builtin.debug:
            var: result.missing_key
        """

        RETURN = r"""
        devices:
          description: Example payload
          returned: success
          type: list
        """

        def run_module() -> None:
            module = AnsibleModule(argument_spec={})
            module.exit_json(changed=False, devices=[], device_count=0)
        ''',
    )

    metadata = consistency_check._build_ansible_metadata(module_path)
    issues = consistency_check.check_ansible_examples(
        module_path, metadata
    ) + consistency_check.check_ansible_return_contract(module_path, metadata)
    messages = [issue.message for issue in issues]

    assert any("missing_key" in message for message in messages)
    assert any("device_count" in message for message in messages)


def test_cli_command_name_must_match_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_roots(monkeypatch, tmp_path)
    command_path = _write_file(
        tmp_path,
        "sccfm_cli/commands/objects/network/list/command.py",
        """
        from __future__ import annotations

        import click


        class ListNetworkObjectCommand:
            @property
            def name(self) -> str:
                return "show-network"

            def build_params(self) -> list[click.Parameter]:
                return [click.Option(["--limit"])]
        """,
    )

    metadata = consistency_check._build_cli_metadata(command_path)
    issues = consistency_check.check_cli_command_naming(command_path, metadata)

    assert len(issues) == 1
    assert "show-network" in issues[0].message
    assert "list" in issues[0].message


def test_cross_device_cli_consistency_flags_missing_shared_option(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_roots(monkeypatch, tmp_path)
    asa_file = _write_file(
        tmp_path,
        "sccfm_cli/commands/inventory/devices/asa/upgrade/trigger/command.py",
        """
        from __future__ import annotations

        import click


        class AsaUpgradeTriggerCommand:
            @property
            def name(self) -> str:
                return "trigger"

            def build_params(self) -> list[click.Parameter]:
                return [
                    click.Option(["--software-version"]),
                    click.Option(["--wait"]),
                ]
        """,
    )
    _write_file(
        tmp_path,
        "sccfm_cli/commands/inventory/devices/ftd/upgrade/trigger/command.py",
        """
        from __future__ import annotations

        import click


        class FtdUpgradeTriggerCommand:
            @property
            def name(self) -> str:
                return "trigger"

            def build_params(self) -> list[click.Parameter]:
                return [click.Option(["--software-version"])]
        """,
    )

    issues = consistency_check.check_cross_device_cli_consistency([asa_file])

    assert any("wait" in issue.message for issue in issues)


def test_cli_ansible_alignment_normalizes_device_uids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_roots(monkeypatch, tmp_path)
    cli_file = _write_file(
        tmp_path,
        "sccfm_cli/commands/inventory/devices/asa/upgrade/trigger/command.py",
        """
        from __future__ import annotations

        import click


        class AsaUpgradeTriggerCommand:
            @property
            def name(self) -> str:
                return "trigger"

            def build_params(self) -> list[click.Parameter]:
                return [
                    *asa_device_filter_params(
                        include_device_name=True,
                        query_help_text="Filter devices by query.",
                    ),
                    click.Option(["--software-version"]),
                    wait_option(),
                    format_option(),
                    config_path_option(),
                ]
        """,
    )
    _write_file(
        tmp_path,
        "sccfm-ansible/plugins/modules/trigger_asa_upgrade.py",
        '''
        DOCUMENTATION = r"""
        ---
        module: trigger_asa_upgrade
        options:
          query:
            type: str
          uids:
            type: list
          limit:
            type: int
          offset:
            type: int
          software_version:
            type: str
          wait:
            type: bool
          region:
            type: str
          api_token:
            type: str
        """

        RETURN = r"""
        transaction:
          description: Transaction payload
          returned: success
          type: dict
        """

        def run_module() -> None:
            module.exit_json(changed=False, transaction={})
        ''',
    )

    issues = consistency_check.check_cli_ansible_alignment([cli_file])

    assert issues == []
