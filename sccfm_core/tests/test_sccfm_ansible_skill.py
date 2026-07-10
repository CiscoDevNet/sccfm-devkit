# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "skills" / "sccfm-ansible" / "SKILL.md"
CLI_SKILL_PATH = ROOT / "skills" / "sccfm-cli" / "SKILL.md"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _cli_skill_text() -> str:
    return CLI_SKILL_PATH.read_text(encoding="utf-8")


def _frontmatter(skill: str) -> str:
    return skill.split("---", maxsplit=2)[1]


def test_sccfm_skills_route_cli_and_ansible_requests_explicitly() -> None:
    ansible_skill = _skill_text()
    cli_skill = _cli_skill_text()
    ansible_routing = ansible_skill.replace("\n", " ")
    cli_routing = cli_skill.replace("\n", " ")
    mixed_request_rule = (
        "For requests spanning both surfaces, apply each skill only to its respective "
        "operations."
    )

    assert "use the sccfm-ansible skill instead" in _frontmatter(cli_skill)
    assert "use the sccfm-cli skill instead" in _frontmatter(ansible_skill)
    assert "use the `sccfm-ansible` skill" in cli_routing
    assert "use the `sccfm-cli` skill" in ansible_routing
    assert mixed_request_rule in cli_routing
    assert mixed_request_rule in ansible_routing
    assert "unless the user explicitly wants the CLI" not in cli_skill
    assert "unless the user explicitly wants Ansible" not in ansible_skill


def test_sccfm_ansible_skill_is_ansible_doc_driven() -> None:
    skill = _skill_text()

    assert "Do NOT use for sccfm-cli commands" in skill
    assert "ansible-doc -j -l -t module cisco.sccfm" in skill
    assert "ansible-doc -j cisco.sccfm.<module_name>" in skill
    assert "ansible-doc -j -l -t inventory cisco.sccfm" in skill
    assert "ansible-doc -j -t inventory <inventory_plugin_fqcn>" in skill
    assert "cisco.sccfm.sccfm" not in skill
    assert "Do not hardcode module names" in skill
    assert "All module knowledge comes from `ansible-doc`" in skill
    assert "only hardcoded bootstrap commands" in skill
    assert "ansible-galaxy collection install dist/cisco-sccfm-*.tar.gz --force" in skill
    assert "only to detect a stale" in skill
    assert "Do not use source filenames" in skill


def test_sccfm_ansible_skill_documents_safety_and_secret_rules() -> None:
    skill = _skill_text()

    assert "Class A: Readonly, no local writes" in skill
    assert "Class B: Readonly, local-write/export side effects" in skill
    assert "Class C: Mutating SCCFM or managed devices" in skill
    assert "Never ask the user to paste secrets into chat" in skill
    assert "name or description indicates a token, password, key, or secret" in skill
    assert "module_defaults: group/cisco.sccfm.all" in skill
    assert "supports_check_mode=True" in skill
    assert "EXECUTE cisco.sccfm <module-fqcn> <target-summary>" in skill


def test_sccfm_ansible_skill_blocks_made_up_query_semantics() -> None:
    skill = _skill_text()

    assert "Natural-Language Filters and Queries" in skill
    assert "Do not assume it accepts Lucene" in skill
    assert "Do not invent query fields or values" in skill
    assert "verify host variables from generated docs or" in skill
    assert "Module parameters belong in YAML" in skill


def test_sccfm_ansible_skill_avoids_hardcoded_module_fqcns() -> None:
    skill = _skill_text()
    module_dir = ROOT / "sccfm-ansible" / "plugins" / "modules"
    assert module_dir.is_dir()

    module_names = {path.stem for path in module_dir.glob("*.py") if path.name != "__init__.py"}
    assert module_names

    hardcoded_fqcns = [f"cisco.sccfm.{module_name}" for module_name in sorted(module_names)]

    assert not any(fqcn in skill for fqcn in hardcoded_fqcns)


def test_skill_discovery_symlinks_point_at_canonical_skills() -> None:
    claude_skills = ROOT / ".claude" / "skills"
    codex_ansible_skill = ROOT / ".agents" / "skills" / "sccfm-ansible"
    codex_cli_skill = ROOT / ".agents" / "skills" / "sccfm-cli"

    assert claude_skills.is_symlink()
    assert claude_skills.readlink() == Path("../skills")

    assert codex_ansible_skill.is_symlink()
    assert codex_ansible_skill.readlink() == Path("../../skills/sccfm-ansible")

    assert codex_cli_skill.is_symlink()
    assert codex_cli_skill.readlink() == Path("../../skills/sccfm-cli")
