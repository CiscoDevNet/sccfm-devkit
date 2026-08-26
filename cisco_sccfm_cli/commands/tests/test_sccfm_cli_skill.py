# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from pathlib import Path

from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = PROJECT_ROOT / "skills" / "sccfm-cli" / "SKILL.md"
CLAUDE_SKILL_PATH = PROJECT_ROOT / ".claude" / "skills" / "sccfm-cli" / "SKILL.md"
CODEX_SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "sccfm-cli"
CODEX_SKILL_PATH = CODEX_SKILL_DIR / "SKILL.md"


def test_cisco_sccfm_cli_skill_should_be_available_at_claude_discovery_path() -> None:
    assert SKILL_PATH.is_file()
    assert CLAUDE_SKILL_PATH.is_file()
    assert CLAUDE_SKILL_PATH.resolve() == SKILL_PATH.resolve()


def test_cisco_sccfm_cli_skill_should_be_available_at_codex_discovery_path() -> None:
    assert CODEX_SKILL_DIR.is_symlink()
    assert CODEX_SKILL_PATH.is_file()
    assert CODEX_SKILL_PATH.resolve() == SKILL_PATH.resolve()


def test_cisco_sccfm_cli_skill_frontmatter_should_be_claude_compatible() -> None:
    metadata, _body = _parse_skill()

    assert metadata["name"] == "sccfm-cli"
    assert "schema" in metadata["description"]
    assert "allowed-tools" in metadata
    assert "Bash(sccfm-cli *)" in metadata["allowed-tools"]
    assert "Bash(brew *)" in metadata["allowed-tools"]
    assert "Bash(python *)" not in metadata["allowed-tools"]


def test_cisco_sccfm_cli_skill_should_cover_schema_driven_operation() -> None:
    _metadata, body = _parse_skill()

    expected_fragments = [
        "sccfm-cli schema export --format json",
        "generate-only mode",
        "Class A",
        "Class B",
        "Class C",
        "EXECUTE <exact shell command>",
        "SCCFM_APPROVAL_COMMAND: <exact shell command>",
        "Match User Intent Conservatively",
        "schema export",
        "not validated against live state",
        "Credential Verification Algorithm",
        "only hardcoded command exception",
        "AWS credentials and internal SystemDB tokens are out of scope",
        "developer.cisco.com",
        "SystemDB",
        "Homebrew",
        "macOS",
        "Linux",
        "Windows",
        "schema choices",
        "Natural-Language Query Filters",
        "Option Placement",
        "sccfm-cli <global options> <schema command path> <command options>",
        "Never place a `global_options` flag after the leaf command",
        "`queryable_fields`",
        "`field_notes`",
        "prefer that command over a generic command plus a",
        "Never pass bare words like `online` as a query",
        "Do not retry automatically",
    ]

    for fragment in expected_fragments:
        assert fragment in body

    assert "sccfm-cli-interactive" in body
    assert "SCCFM_API_TOKEN" not in body
    assert "SCCFM_REGION" not in body


def test_cisco_sccfm_cli_skill_should_reference_fields_emitted_by_schema(
    cli_runner: CliRunner,
) -> None:
    result = cli_runner.invoke(cli, ["schema", "export"], prog_name="sccfm-cli")
    assert result.exit_code == 0, result.output

    command = json.loads(result.output)["commands"][0]
    schema_fields = {
        "command",
        "path",
        "description",
        "readonly",
        "side_effects",
        "auth",
        "queryable_fields",
        "field_notes",
        "options",
        "constraints",
        "option_groups",
        "examples",
    }
    _metadata, body = _parse_skill()

    assert schema_fields <= set(command)
    for field in schema_fields:
        assert f"`{field}`" in body


def test_cisco_sccfm_cli_skill_should_not_hardcode_operational_command_examples() -> None:
    _metadata, body = _parse_skill()

    command_lines = [
        line.strip() for line in body.splitlines() if line.strip().startswith("sccfm-cli ")
    ]
    assert command_lines == [
        "sccfm-cli schema export --format json",
        "sccfm-cli <global options> <schema command path> <command options>",
    ]
    assert re.search(r"sccfm-cli (?!schema export\b)[a-z0-9_-]+", body) is None

    stale_hardcoded_fragments = [
        "Top-level groups",
        "Common workflows",
        "inventory devices",
        "objects network",
        "policies access",
        "--device-name",
        "--wait",
        "--timeout",
    ]
    for fragment in stale_hardcoded_fragments:
        assert fragment not in body


def _parse_skill() -> tuple[dict[str, str], str]:
    lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end_index = lines.index("---", 1)
    metadata = _parse_frontmatter(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return metadata, body


def _parse_frontmatter(lines: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in lines:
        key, value = line.split(":", maxsplit=1)
        metadata[key] = value.strip().strip('"')
    return metadata
