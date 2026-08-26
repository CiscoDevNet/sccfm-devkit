# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the cross-agent SCCFM plugin package."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "sccfm"


def load_setup_runtime() -> ModuleType:
    module_path = PLUGIN_ROOT / "scripts" / "setup_runtime.py"
    specification = importlib.util.spec_from_file_location("sccfm_setup_runtime", module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_command_guard() -> ModuleType:
    module_path = PLUGIN_ROOT / "hooks" / "sccfm_guard.py"
    specification = importlib.util.spec_from_file_location("sccfm_command_guard", module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def sample_schema() -> dict[str, object]:
    return {
        "global_options": [
            {"aliases": ["--profile"], "is_flag": False},
            {"aliases": ["--silent"], "is_flag": True},
        ],
        "commands": [
            {"path": ["status"], "readonly": True, "side_effects": []},
            {
                "path": ["schema", "export"],
                "readonly": True,
                "side_effects": ["May write --output"],
            },
            {
                "path": ["inventory", "devices", "delete"],
                "readonly": False,
                "options": [{"aliases": ["--api-token"], "sensitive": True}],
            },
            {
                "path": ["objects", "network", "delete"],
                "readonly": False,
                "options": [],
            },
        ],
    }


def test_plugin_manifests_and_marketplaces_are_aligned() -> None:
    codex_manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    claude_manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    codex_marketplace = json.loads(
        (REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    claude_marketplace = json.loads(
        (REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )

    assert codex_manifest["name"] == claude_manifest["name"] == "sccfm"
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_marketplace["plugins"][0]["name"] == "sccfm"
    assert codex_marketplace["plugins"][0]["source"]["path"] == "./plugins/sccfm"
    assert claude_marketplace["plugins"][0]["name"] == "sccfm"
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/sccfm"


def test_codex_and_claude_hook_manifests_enforce_the_same_events() -> None:
    codex_hooks = json.loads((PLUGIN_ROOT / "hooks.json").read_text())
    claude_hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())

    assert (
        set(codex_hooks["hooks"])
        == set(claude_hooks["hooks"])
        == {
            "PreToolUse",
            "Stop",
            "UserPromptSubmit",
        }
    )
    assert codex_hooks["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
    assert claude_hooks["hooks"]["PreToolUse"][0]["matcher"] == "Bash"

    codex_commands = json.dumps(codex_hooks["hooks"])
    claude_commands = json.dumps(claude_hooks["hooks"])
    assert "./hooks/sccfm_guard.py" in codex_commands
    assert "--record-plan" in codex_commands
    assert "--host" not in codex_commands
    assert "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-.}}/hooks/sccfm_guard.py" in claude_commands
    assert "--record-plan" in claude_commands
    assert "--host" not in claude_commands
    assert "aligned" in codex_hooks["description"]
    assert "aligned" in claude_hooks["description"]


@pytest.mark.parametrize("skill_name", ["sccfm-cli", "sccfm-ansible"])
def test_distributed_skills_match_canonical_sources(skill_name: str) -> None:
    canonical = REPOSITORY_ROOT / "skills" / skill_name / "SKILL.md"
    distributed = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"

    assert distributed.read_bytes() == canonical.read_bytes()


def test_install_plan_uses_one_pipx_environment_and_matching_versions() -> None:
    setup_runtime = load_setup_runtime()

    assert setup_runtime.install_commands("0.39.3", "python3.12") == [
        [
            "pipx",
            "install",
            "--python",
            "python3.12",
            "--force",
            "cisco-sccfm-devkit==0.39.3",
        ],
        [
            "pipx",
            "inject",
            "--include-apps",
            "--force",
            "cisco-sccfm-devkit",
            "ansible-core>=2.20,<2.22",
        ],
        [
            "ansible-galaxy",
            "collection",
            "install",
            "cisco.sccfm:==0.39.3",
            "--force",
        ],
    ]


@pytest.mark.parametrize("version", ["0.39", "0.39.3rc1", "latest", "0.39.3; echo unsafe"])
def test_install_plan_rejects_non_stable_versions(version: str) -> None:
    setup_runtime = load_setup_runtime()

    with pytest.raises(ValueError, match="stable X.Y.Z"):
        setup_runtime.install_commands(version, "python3.12")


def test_collection_installations_accept_only_reported_collection_layout(tmp_path: Path) -> None:
    setup_runtime = load_setup_runtime()
    collection_root = tmp_path / "ansible_collections"
    collection_path = collection_root / "cisco" / "sccfm"
    collection_path.mkdir(parents=True)

    result = setup_runtime.collection_installations(
        {str(collection_root): {"cisco.sccfm": {"version": "0.39.5"}}}
    )

    assert result == [{"path": str(collection_path), "version": "0.39.5"}]


def test_collection_installations_reject_unexpected_root(tmp_path: Path) -> None:
    setup_runtime = load_setup_runtime()
    collection_root = tmp_path / "collections"
    (collection_root / "cisco" / "sccfm").mkdir(parents=True)

    with pytest.raises(ValueError, match="unexpected collection root"):
        setup_runtime.collection_installations(
            {str(collection_root): {"cisco.sccfm": {"version": "0.39.5"}}}
        )


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics differ on Windows")
def test_collection_installations_reject_symlinked_root(tmp_path: Path) -> None:
    setup_runtime = load_setup_runtime()
    real_root = tmp_path / "real" / "ansible_collections"
    (real_root / "cisco" / "sccfm").mkdir(parents=True)
    linked_root = tmp_path / "ansible_collections"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        setup_runtime.collection_installations(
            {str(linked_root): {"cisco.sccfm": {"version": "0.39.5"}}}
        )


def test_pipx_package_discovery_normalizes_package_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime, "command_path", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        setup_runtime,
        "run_capture",
        lambda command, limit=1000: {
            "ok": True,
            "output": json.dumps(
                {
                    "venvs": {
                        "cisco_sccfm_devkit": {
                            "metadata": {"main_package": {"package": "cisco-sccfm-devkit"}}
                        }
                    }
                }
            ),
        },
    )

    assert setup_runtime.pipx_package_installed() is True


def test_uninstall_plan_preserves_profiles_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    collection_path = tmp_path / "ansible_collections" / "cisco" / "sccfm"
    collection_path.mkdir(parents=True)
    monkeypatch.setattr(setup_runtime, "discover_collection_paths", lambda: [collection_path])
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: f"/bin/{name}" if name in {"pipx", "sccfm-cli"} else None,
    )
    monkeypatch.setattr(setup_runtime, "pipx_package_installed", lambda: True)
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))

    plan = setup_runtime.uninstall_plan(remove_profiles=False)

    assert plan["collection_paths"] == [str(collection_path)]
    assert plan["pipx_command"] == ["pipx", "uninstall", "cisco-sccfm-devkit"]
    assert plan["profile"] == {
        "action": "preserve",
        "path": str(tmp_path / ".sccfm-cli" / "config.json"),
        "exists": False,
    }


def test_uninstall_plan_refuses_an_unmanaged_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime, "discover_collection_paths", lambda: [])
    monkeypatch.setattr(setup_runtime, "command_path", lambda name: f"/bin/{name}")
    monkeypatch.setattr(setup_runtime, "pipx_package_installed", lambda: False)

    with pytest.raises(RuntimeError, match="not owned by the managed pipx environment"):
        setup_runtime.uninstall_plan(remove_profiles=False)


def test_uninstall_requires_confirmation() -> None:
    setup_runtime = load_setup_runtime()

    with pytest.raises(SystemExit, match="Refusing to uninstall"):
        setup_runtime.uninstall(remove_profiles=False, confirmed=False)


def test_uninstall_removes_collection_before_pipx_and_preserves_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    collection_path = tmp_path / "ansible_collections" / "cisco" / "sccfm"
    profile_path = tmp_path / ".sccfm-cli" / "config.json"
    profile_path.parent.mkdir()
    profile_path.write_text("secret")
    events: list[str] = []
    monkeypatch.setattr(
        setup_runtime,
        "uninstall_plan",
        lambda remove_profiles: {
            "collection_paths": [str(collection_path)],
            "pipx_command": ["pipx", "uninstall", "cisco-sccfm-devkit"],
            "profile": {"action": "preserve", "path": str(profile_path), "exists": True},
        },
    )
    monkeypatch.setattr(
        setup_runtime.shutil,
        "rmtree",
        lambda path: events.append(f"collection:{path}"),
    )
    monkeypatch.setattr(
        setup_runtime.subprocess,
        "run",
        lambda command, check: events.append(f"command:{' '.join(command)}"),
    )
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))

    setup_runtime.uninstall(remove_profiles=False, confirmed=True)

    assert events == [
        f"collection:{collection_path}",
        "command:pipx uninstall cisco-sccfm-devkit",
    ]
    assert profile_path.exists()


def test_uninstall_deletes_profiles_only_with_explicit_option(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    profile_path = tmp_path / ".sccfm-cli" / "config.json"
    profile_path.parent.mkdir()
    profile_path.write_text("secret")
    monkeypatch.setattr(
        setup_runtime,
        "uninstall_plan",
        lambda remove_profiles: {
            "collection_paths": [],
            "pipx_command": None,
            "profile": {"action": "delete", "path": str(profile_path), "exists": True},
        },
    )
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))

    setup_runtime.uninstall(remove_profiles=True, confirmed=True)

    assert not profile_path.exists()


def test_setup_skill_documents_safe_teardown_contract() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sccfm-setup" / "SKILL.md").read_text()

    assert "uninstall-plan" in skill
    assert "UNINSTALL SCCFM" in skill
    assert "UNINSTALL SCCFM AND DELETE PROFILES" in skill
    assert "preserves `~/.sccfm-cli/config.json` by default" in skill
    assert "codex plugin remove sccfm@sccfm-devkit" in skill


def test_profile_diagnostics_expose_metadata_without_secret_contents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    profile_path = tmp_path / ".sccfm-cli" / "config.json"
    profile_path.parent.mkdir()
    profile_path.write_text('{"token": "must-not-appear"}')
    profile_path.chmod(0o600)
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))

    result = setup_runtime.profile_metadata()

    assert result["configured"] is True
    assert result["secure_permissions"] is True
    assert "must-not-appear" not in json.dumps(result)


@pytest.mark.parametrize(
    "command",
    [
        "sccfm-cli status",
        "sccfm-cli --profile default --silent status --format json",
        "sccfm-cli schema export --format json",
        "command -v sccfm-cli",
    ],
)
def test_guard_allows_schema_proven_readonly_commands(command: str) -> None:
    guard = load_command_guard()

    classification, _reason = guard.classify_command(command, sample_schema())

    assert classification == "readonly"


@pytest.mark.parametrize(
    "command",
    [
        "sccfm-cli inventory devices delete --uid example",
        "sccfm-cli schema export --output schema.json",
        "sccfm-cli status | tee status.txt",
        "env DEBUG=1 sccfm-cli status",
        "ansible-playbook change.yml",
        "ansible-galaxy collection install cisco.sccfm",
    ],
)
def test_guard_requires_review_for_mutating_local_write_or_composed_commands(
    command: str,
) -> None:
    guard = load_command_guard()

    classification, _reason = guard.classify_command(command, sample_schema())

    assert classification == "review"


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "sed -n '1,240p' skills/sccfm-cli/SKILL.md",
        "rg sccfm-cli docs/agent-plugin.md",
    ],
)
def test_guard_ignores_unrelated_commands(command: str) -> None:
    guard = load_command_guard()

    classification, _reason = guard.classify_command(command, sample_schema())

    assert classification == "unrelated"


@pytest.mark.parametrize(
    "command",
    [
        "sccfm-cli inventory devices delete --uid $(cat target.txt)",
        "sccfm-cli inventory devices delete --uid `cat target.txt`",
        "sccfm-cli inventory devices delete --uid example && echo changed",
        "env DEBUG=1 sccfm-cli inventory devices delete --uid example",
        "sccfm-cli inventory devices unknown --uid example",
        "sccfm-cli inventory devices delete --uid example --api-token secret",
    ],
)
def test_guard_rejects_unsafe_or_unverifiable_approval_commands(command: str) -> None:
    guard = load_command_guard()

    assert guard.approval_eligible(command, sample_schema()) is False


def test_exact_approval_command_requires_a_standalone_message() -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    assert guard.exact_approval_command(f"EXECUTE {command}") == command
    assert guard.exact_approval_command(f"EXECUTE {command}\nplease") is None
    assert guard.exact_approval_command(f"Please EXECUTE {command}") is None
    assert guard.exact_approval_command("EXECUTE ") is None


def test_planned_command_requires_one_standalone_marker() -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    assert guard.planned_command(f"Plan ready.\nSCCFM_APPROVAL_COMMAND: {command}") == command
    assert guard.planned_command(f"SCCFM_APPROVAL_COMMAND: {command}\nSummary") == command
    assert (
        guard.planned_command(
            f"SCCFM_APPROVAL_COMMAND: {command}\nSCCFM_APPROVAL_COMMAND: {command} --check"
        )
        is None
    )
    assert guard.planned_command("No approval marker") is None
    assert guard.planned_command("SCCFM_APPROVAL_COMMAND: ") is None


def test_guard_detects_the_host_from_plugin_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = load_command_guard()
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

    assert guard.detected_host() == "codex"

    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
    assert guard.detected_host() == "claude"


def test_approval_receipt_is_hashed_private_and_one_use(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    guard.store_approval(tmp_path, "session-one", command, now=100.0)

    receipt_path = guard.approval_path(tmp_path, "session-one")
    receipt_text = receipt_path.read_text()
    assert command not in receipt_text
    assert guard.command_digest(command) in receipt_text
    if os.name != "nt":
        assert receipt_path.stat().st_mode & 0o777 == 0o600
        assert receipt_path.parent.stat().st_mode & 0o777 == 0o700
    assert guard.consume_approval(tmp_path, "session-one", command, now=101.0) is True
    assert guard.consume_approval(tmp_path, "session-one", command, now=102.0) is False


def test_approval_receipt_expires_and_is_consumed_on_mismatch(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    guard.store_approval(tmp_path, "expired", command, now=100.0)
    assert guard.consume_approval(tmp_path, "expired", command, now=701.0) is False
    assert not guard.approval_path(tmp_path, "expired").exists()

    guard.store_approval(tmp_path, "mismatch", command, now=100.0)
    assert guard.consume_approval(tmp_path, "mismatch", f"{command} --force", now=101.0) is False
    assert not guard.approval_path(tmp_path, "mismatch").exists()


def test_plan_receipt_is_hashed_private_and_consumed_only_on_match(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    guard.store_plan(tmp_path, "session-one", command, now=100.0)

    receipt_path = guard.plan_path(tmp_path, "session-one")
    receipt_text = receipt_path.read_text()
    assert command not in receipt_text
    assert guard.command_digest(command) in receipt_text
    assert (
        guard.consume_matching_plan(tmp_path, "session-one", f"{command} --check", now=101.0)
        is False
    )
    assert receipt_path.exists()
    assert guard.consume_matching_plan(tmp_path, "session-one", command, now=102.0) is True
    assert not receipt_path.exists()


def test_plan_receipt_expires(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    guard.store_plan(tmp_path, "expired", command, now=100.0)

    assert guard.consume_matching_plan(tmp_path, "expired", command, now=3701.0) is False
    assert not guard.plan_path(tmp_path, "expired").exists()


def test_assistant_plan_records_only_one_eligible_exact_command(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    assert (
        guard.process_assistant_plan(
            {
                "session_id": "planned",
                "last_assistant_message": f"Plan ready.\nSCCFM_APPROVAL_COMMAND: {command}",
            },
            tmp_path,
            sample_schema(),
        )
        is True
    )
    assert guard.plan_path(tmp_path, "planned").exists()
    assert (
        guard.process_assistant_plan(
            {
                "session_id": "readonly",
                "last_assistant_message": "SCCFM_APPROVAL_COMMAND: sccfm-cli status",
            },
            tmp_path,
            sample_schema(),
        )
        is False
    )
    assert not guard.plan_path(tmp_path, "readonly").exists()


def test_latest_assistant_message_without_a_valid_marker_clears_stale_plan(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"
    guard.store_plan(tmp_path, "session", command)
    guard.store_approval(tmp_path, "session", command)

    assert (
        guard.process_assistant_plan(
            {"session_id": "session", "last_assistant_message": "The plan was cancelled."},
            tmp_path,
            sample_schema(),
        )
        is False
    )
    assert not guard.plan_path(tmp_path, "session").exists()
    assert not guard.approval_path(tmp_path, "session").exists()


def test_user_prompt_promotes_only_the_previously_planned_exact_command(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    assert (
        guard.process_user_prompt(
            {"session_id": "unplanned", "prompt": f"EXECUTE {command}"},
            tmp_path,
            sample_schema(),
        )
        is False
    )
    guard.store_plan(tmp_path, "approved", command)
    assert (
        guard.process_user_prompt(
            {"session_id": "approved", "prompt": f"EXECUTE {command}"},
            tmp_path,
            sample_schema(),
        )
        is True
    )
    assert guard.approval_path(tmp_path, "approved").exists()
    assert not guard.plan_path(tmp_path, "approved").exists()


def test_removing_check_from_planned_command_cannot_authorize_mutation(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli objects network delete " "--uid 2405870d-7348-4b69-9580-a3de165b1671"
    planned_command = f"{command} --check"
    session_id = "edited-confirmation"
    guard.store_plan(tmp_path, session_id, planned_command)

    assert (
        guard.process_user_prompt(
            {"session_id": session_id, "prompt": f"EXECUTE {command}"},
            tmp_path,
            sample_schema(),
        )
        is False
    )
    assert not guard.approval_path(tmp_path, session_id).exists()
    assert guard.plan_path(tmp_path, session_id).exists()

    decision = guard.process_tool_use(
        {"session_id": session_id, "tool_input": {"command": command}},
        "codex",
        tmp_path,
        sample_schema(),
    )

    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_unapproved_mutating_command_is_denied(host: str, tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    decision = guard.process_tool_use(
        {"session_id": "session", "tool_input": {"command": command}},
        host,
        tmp_path,
        sample_schema(),
    )

    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_codex_approved_command_proceeds_and_consumes_receipt(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"
    guard.store_approval(tmp_path, "codex-session", command)

    decision = guard.process_tool_use(
        {"session_id": "codex-session", "tool_input": {"command": command}},
        "codex",
        tmp_path,
        sample_schema(),
    )

    assert decision is None
    assert not guard.approval_path(tmp_path, "codex-session").exists()


def test_claude_approved_command_requests_host_confirmation(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "ansible-playbook -i inventory.yml change.yml"
    guard.store_approval(tmp_path, "claude-session", command)

    decision = guard.process_tool_use(
        {"session_id": "claude-session", "tool_input": {"command": command}},
        "claude",
        tmp_path,
        sample_schema(),
    )

    assert decision["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert not guard.approval_path(tmp_path, "claude-session").exists()


def test_readonly_command_does_not_need_or_consume_approval(tmp_path: Path) -> None:
    guard = load_command_guard()

    assert (
        guard.process_tool_use(
            {"session_id": "session", "tool_input": {"command": "sccfm-cli status"}},
            "codex",
            tmp_path,
            sample_schema(),
        )
        is None
    )
