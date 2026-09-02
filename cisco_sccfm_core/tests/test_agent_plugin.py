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
                "options": [
                    {
                        "name": "uid",
                        "aliases": ["--uid"],
                        "is_flag": False,
                        "nargs": 1,
                    },
                    {
                        "name": "check",
                        "aliases": ["--check"],
                        "is_flag": True,
                        "nargs": 1,
                    },
                    {
                        "name": "api_token",
                        "aliases": ["--api-token"],
                        "is_flag": False,
                        "nargs": 1,
                        "sensitive": True,
                    },
                ],
                "constraints": [
                    {
                        "type": "mode",
                        "option": "check",
                        "effect": ("Preflight only; do not perform the SCCFM-changing operation."),
                    }
                ],
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
    for manifest in (codex_hooks, claude_hooks):
        for event_groups in manifest["hooks"].values():
            for event_group in event_groups:
                for handler in event_group["hooks"]:
                    assert handler["commandWindows"].startswith("py -3 ")
    assert "aligned" in codex_hooks["description"]
    assert "aligned" in claude_hooks["description"]


@pytest.mark.parametrize("skill_name", ["sccfm-cli", "sccfm-ansible"])
def test_distributed_skills_match_canonical_sources(skill_name: str) -> None:
    canonical = REPOSITORY_ROOT / "skills" / skill_name / "SKILL.md"
    distributed = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"

    assert distributed.read_bytes() == canonical.read_bytes()


def test_install_plan_uses_one_pipx_environment_and_matching_versions(tmp_path: Path) -> None:
    setup_runtime = load_setup_runtime()
    collection_base = tmp_path / "collections"

    assert setup_runtime.install_commands("0.39.3", "python3.12", collection_base) == [
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
            "--collections-path",
            str(collection_base),
        ],
    ]


def test_homebrew_plan_uses_a_private_matching_ansible_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    collection_base = tmp_path / ".ansible" / "collections"
    runtime = tmp_path / ".sccfm-agent-plugin" / "ansible-runtime"

    assert setup_runtime.homebrew_ansible_install_commands(
        "0.40.0", "python3.12", collection_base
    ) == [
        ["python3.12", "-m", "venv", str(runtime)],
        [
            str(runtime / "bin" / "python"),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--upgrade",
            "ansible-core>=2.20,<2.22",
            "cisco-sccfm-devkit==0.40.0",
        ],
        [
            str(runtime / "bin" / "ansible-galaxy"),
            "collection",
            "install",
            "cisco.sccfm:==0.40.0",
            "--force",
            "--collections-path",
            str(collection_base),
        ],
    ]


def test_homebrew_install_state_records_the_private_ansible_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    collection_path = setup_runtime.expected_collection_path()

    setup_runtime.write_install_state(
        collection_path,
        "0.40.0",
        runtime_kind=setup_runtime.HOMEBREW_ANSIBLE_RUNTIME_KIND,
    )

    assert setup_runtime.load_install_state() == {
        "ansible_runtime_path": str(setup_runtime.expected_ansible_runtime_path()),
        "collection_path": str(collection_path),
        "runtime_kind": "homebrew-ansible",
        "schema_version": 2,
        "version": "0.40.0",
    }


def test_legacy_install_state_defaults_to_the_pipx_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    state_path = setup_runtime.install_state_path()
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "collection_path": str(setup_runtime.expected_collection_path()),
                "version": "0.39.5",
            }
        )
    )

    assert setup_runtime.load_install_state()["runtime_kind"] == "pipx"


def test_homebrew_install_state_selects_the_private_ansible_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    collection_path = setup_runtime.expected_collection_path()
    ansible_doc = setup_runtime.ansible_runtime_executable("ansible-doc")
    ansible_doc.parent.mkdir(parents=True)
    ansible_doc.touch()
    setup_runtime.write_install_state(
        collection_path,
        "0.40.0",
        runtime_kind=setup_runtime.HOMEBREW_ANSIBLE_RUNTIME_KIND,
    )

    assert setup_runtime.ansible_command_path("ansible-doc") == str(ansible_doc)


def test_homebrew_install_creates_only_the_private_ansible_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: "/usr/local/bin/python3.12" if name == "python3.12" else None,
    )
    monkeypatch.setattr(
        setup_runtime,
        "homebrew_formula_installation",
        lambda: {"versions": ["0.40.0"]},
    )
    commands: list[list[str]] = []

    def run_install(command: list[str], check: bool) -> None:
        assert check is True
        commands.append(command)
        runtime = setup_runtime.expected_ansible_runtime_path()
        if command[1:3] == ["-m", "venv"]:
            (runtime / "bin").mkdir(parents=True)
            for executable in ("python", "ansible-galaxy", "ansible-doc"):
                (runtime / "bin" / executable).touch()
        if "collection" in command:
            setup_runtime.expected_collection_path().mkdir(parents=True)

    monkeypatch.setattr(setup_runtime.subprocess, "run", run_install)

    setup_runtime.install("0.40.0", "python3.12", confirmed=True)

    assert all(command[0] != "pipx" for command in commands)
    assert setup_runtime.load_install_state()["runtime_kind"] == "homebrew-ansible"


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


def test_collection_metadata_prefers_the_recorded_copy_when_two_roots_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    managed_path = setup_runtime.expected_collection_path()
    managed_root = managed_path.parents[1]
    unmanaged_root = tmp_path / "vendor" / "ansible_collections"
    (unmanaged_root / "cisco" / "sccfm").mkdir(parents=True)
    managed_path.mkdir(parents=True)
    setup_runtime.write_install_state(managed_path, "0.39.5")
    monkeypatch.setattr(
        setup_runtime,
        "collection_listing",
        lambda environment: {
            str(unmanaged_root): {"cisco.sccfm": {"version": "0.39.0"}},
            str(managed_root): {"cisco.sccfm": {"version": "0.39.5"}},
        },
    )

    metadata = setup_runtime.collection_metadata({})

    assert metadata["version"] == "0.39.5"
    assert metadata["selected_path"] == str(managed_path)
    assert metadata["managed"] is True


def test_pipx_package_discovery_normalizes_package_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    pipx_home = tmp_path / "pipx"
    metadata_path = pipx_home / "venvs" / "cisco_sccfm_devkit" / "pipx_metadata.json"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(json.dumps({"main_package": {"package": "cisco-sccfm-devkit"}}))
    monkeypatch.setenv("PIPX_HOME", str(pipx_home))

    assert setup_runtime.pipx_package_environment() == metadata_path.parent
    assert setup_runtime.pipx_package_installed() is True


def test_homebrew_formula_discovery_uses_the_canonical_tap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: "/opt/homebrew/bin/brew" if name == "brew" else None,
    )

    def fake_run_capture(
        command: list[str], *, environment: dict[str, str] | None = None, limit: int = 1000
    ) -> dict[str, object]:
        del environment, limit
        if "--full-name" in command:
            return {"ok": True, "exit_code": 0, "output": "ciscodevnet/tap/sccfm-cli"}
        return {"ok": True, "exit_code": 0, "output": "sccfm-cli 0.39.3"}

    monkeypatch.setattr(setup_runtime, "run_capture", fake_run_capture)

    assert setup_runtime.homebrew_formula_installation() == {
        "formula": "ciscodevnet/tap/sccfm-cli",
        "versions": ["0.39.3"],
        "command": [
            "/opt/homebrew/bin/brew",
            "uninstall",
            "ciscodevnet/tap/sccfm-cli",
        ],
        "environment": {"HOMEBREW_NO_AUTOREMOVE": "1"},
    }


def test_homebrew_formula_discovery_ignores_a_different_tap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime, "command_path", lambda name: "/bin/brew")
    monkeypatch.setattr(
        setup_runtime,
        "run_capture",
        lambda command, limit: {
            "ok": True,
            "exit_code": 0,
            "output": "example/tap/sccfm-cli",
        },
    )

    assert setup_runtime.homebrew_formula_installation() is None


def test_uninstall_plan_preserves_profiles_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    collection_path = setup_runtime.expected_collection_path()
    collection_path.mkdir(parents=True)
    setup_runtime.write_install_state(collection_path, "0.39.5")
    monkeypatch.setattr(setup_runtime, "discover_collection_paths", lambda: [collection_path])
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: f"/bin/{name}" if name in {"pipx", "sccfm-cli"} else None,
    )
    monkeypatch.setattr(setup_runtime, "pipx_package_installed", lambda: True)

    plan = setup_runtime.uninstall_plan(remove_profiles=False)

    assert plan["collection_paths"] == [str(collection_path)]
    assert plan["preserved_collection_paths"] == []
    assert plan["pipx_command"] == ["pipx", "uninstall", "cisco-sccfm-devkit"]
    assert plan["profile"] == {
        "action": "preserve",
        "path": str(tmp_path / ".sccfm-cli" / "config.json"),
        "exists": False,
    }


def test_uninstall_plan_refuses_an_unmanaged_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(setup_runtime, "discover_collection_paths", lambda: [])
    monkeypatch.setattr(setup_runtime, "command_path", lambda name: f"/bin/{name}")
    monkeypatch.setattr(setup_runtime, "pipx_package_installed", lambda: False)

    with pytest.raises(RuntimeError, match="not owned by the managed pipx environment"):
        setup_runtime.uninstall_plan(remove_profiles=False)


def test_uninstall_plan_removes_only_the_recorded_collection_when_two_roots_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    managed_path = setup_runtime.expected_collection_path()
    unmanaged_path = tmp_path / "vendor" / "ansible_collections" / "cisco" / "sccfm"
    managed_path.mkdir(parents=True)
    unmanaged_path.mkdir(parents=True)
    setup_runtime.write_install_state(managed_path, "0.39.5")
    monkeypatch.setattr(
        setup_runtime,
        "discover_collection_paths",
        lambda: [managed_path, unmanaged_path],
    )
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: f"/bin/{name}" if name in {"pipx", "sccfm-cli"} else None,
    )
    monkeypatch.setattr(setup_runtime, "pipx_package_installed", lambda: True)

    plan = setup_runtime.uninstall_plan(remove_profiles=False)

    assert plan["collection_paths"] == [str(managed_path)]
    assert plan["preserved_collection_paths"] == [str(unmanaged_path)]


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
            "preserved_collection_paths": [],
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
            "preserved_collection_paths": [],
            "pipx_command": None,
            "profile": {"action": "delete", "path": str(profile_path), "exists": True},
        },
    )
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))

    setup_runtime.uninstall(remove_profiles=True, confirmed=True)

    assert not profile_path.exists()


def test_setup_skill_routes_teardown_to_the_uninstall_skill() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sccfm-setup" / "SKILL.md").read_text()

    assert "Route uninstall, teardown, and complete-cleanup requests" in skill
    assert "`sccfm-uninstall` skill" in skill


def test_setup_skill_supports_pipx_and_homebrew_companion_paths() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sccfm-setup" / "SKILL.md").read_text()

    assert "pipx is the canonical installation method" in skill
    assert "This skill never installs through Homebrew" in skill
    assert "brew install CiscoDevNet/tap/sccfm-cli" not in skill
    assert "Bash(brew *)" not in skill
    assert "Homebrew CLI" in skill
    assert "ansible-runtime" in skill
    assert "without exposing a second `sccfm-cli`" in skill


def test_setup_skill_uses_a_fast_install_path_and_exact_config_command() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sccfm-setup" / "SKILL.md").read_text()
    normalized_skill = " ".join(skill.split())

    assert "Do not run the full doctor before installation" in normalized_skill
    assert "query the PyPI and Ansible Galaxy release metadata in parallel" in normalized_skill
    assert "run exactly one helper command" in normalized_skill
    assert "Do not run connectivity checks before the user configures a profile" in normalized_skill
    assert "sccfm-cli --profile default configure --region us" in skill
    assert "never return placeholders" in normalized_skill


def test_cli_skill_keeps_homebrew_scoped_to_cli_only_installation() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sccfm-cli" / "SKILL.md").read_text()

    assert "Optional CLI-only Homebrew installation" in skill
    assert "brew tap CiscoDevNet/tap" in skill
    assert "brew trust --formula CiscoDevNet/tap/sccfm-cli" in skill
    assert "brew install CiscoDevNet/tap/sccfm-cli" in skill
    assert "INSTALL SCCFM CLI WITH HOMEBREW" in skill
    assert "Homebrew installs the CLI and Python library only" in skill
    assert "`cisco.sccfm` Ansible collection" in skill


def test_uninstall_skill_documents_discovered_cleanup_contract() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sccfm-uninstall" / "SKILL.md").read_text()

    assert "cleanup-plan --json" in skill
    assert "ciscodevnet/tap/sccfm-cli" in skill
    assert "--include-editable" in skill
    assert "UNINSTALL SCCFM" in skill
    assert "UNINSTALL SCCFM AND PROFILES" in skill
    assert "UNINSTALL SCCFM AND DELETE PROFILES" not in skill
    assert "--plan-digest <digest> --yes" in skill
    assert "codex plugin remove sccfm@sccfm-devkit" in skill


def test_cleanup_collection_discovery_validates_the_standard_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(setup_runtime, "command_path", lambda name: None)
    collection_path = setup_runtime.expected_collection_path()
    collection_path.mkdir(parents=True)
    (collection_path / "MANIFEST.json").write_text(
        json.dumps({"collection_info": {"namespace": "cisco", "name": "sccfm"}})
    )

    assert setup_runtime.discover_cleanup_collection_paths() == [collection_path]


def test_cleanup_plan_preserves_editable_python_installs_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(setup_runtime, "discover_cleanup_collection_paths", lambda: [])
    monkeypatch.setattr(setup_runtime, "pipx_package_environment", lambda: None)
    monkeypatch.setattr(setup_runtime, "homebrew_formula_installation", lambda: None)
    editable_installation = {
        "interpreter": "/work/.venv/bin/python",
        "version": "0.39.5",
        "location": "/work/.venv/lib/python3.12/site-packages",
        "environment": "/work/.venv",
        "editable": True,
        "source": "file:///work/sccfm-devkit",
        "command": [
            "/work/.venv/bin/python",
            "-m",
            "pip",
            "uninstall",
            "--yes",
            "cisco-sccfm-devkit",
        ],
    }
    monkeypatch.setattr(
        setup_runtime,
        "discover_python_installations",
        lambda include_cli_candidate: [editable_installation],
    )

    plan = setup_runtime.cleanup_plan(remove_profiles=False, include_editable=False)

    assert plan["python_installations"] == []
    assert plan["preserved_python_installations"] == [editable_installation]
    assert len(plan["plan_digest"]) == 64


def test_cleanup_plan_includes_editable_python_installs_only_after_opt_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(setup_runtime, "discover_cleanup_collection_paths", lambda: [])
    monkeypatch.setattr(setup_runtime, "pipx_package_environment", lambda: None)
    monkeypatch.setattr(setup_runtime, "homebrew_formula_installation", lambda: None)
    editable_installation = {
        "interpreter": "/work/.venv/bin/python",
        "version": "0.39.5",
        "location": "/work/.venv/lib/python3.12/site-packages",
        "environment": "/work/.venv",
        "editable": True,
        "source": "file:///work/sccfm-devkit",
        "command": ["/work/.venv/bin/python", "-m", "pip", "uninstall"],
    }
    monkeypatch.setattr(
        setup_runtime,
        "discover_python_installations",
        lambda include_cli_candidate: [editable_installation],
    )

    plan = setup_runtime.cleanup_plan(remove_profiles=False, include_editable=True)

    assert plan["python_installations"] == [editable_installation]
    assert plan["preserved_python_installations"] == []


def test_cleanup_plan_includes_homebrew_and_skips_cli_python_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(setup_runtime, "discover_cleanup_collection_paths", lambda: [])
    monkeypatch.setattr(setup_runtime, "pipx_package_environment", lambda: None)
    homebrew_installation = {
        "formula": "ciscodevnet/tap/sccfm-cli",
        "versions": ["0.39.3"],
        "command": ["/opt/homebrew/bin/brew", "uninstall", "ciscodevnet/tap/sccfm-cli"],
        "environment": {"HOMEBREW_NO_AUTOREMOVE": "1"},
    }
    monkeypatch.setattr(
        setup_runtime,
        "homebrew_formula_installation",
        lambda: homebrew_installation,
    )
    discovery_modes: list[bool] = []

    def record_discovery_mode(include_cli_candidate: bool) -> list[dict[str, object]]:
        discovery_modes.append(include_cli_candidate)
        return []

    monkeypatch.setattr(
        setup_runtime,
        "discover_python_installations",
        record_discovery_mode,
    )

    plan = setup_runtime.cleanup_plan(remove_profiles=False, include_editable=False)

    assert plan["homebrew_installation"] == homebrew_installation
    assert discovery_modes == [False]


def test_cleanup_plan_removes_the_owned_homebrew_ansible_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    collection_path = setup_runtime.expected_collection_path()
    runtime_path = setup_runtime.expected_ansible_runtime_path()
    runtime_path.mkdir(parents=True)
    setup_runtime.write_install_state(
        collection_path,
        "0.40.0",
        runtime_kind=setup_runtime.HOMEBREW_ANSIBLE_RUNTIME_KIND,
    )
    monkeypatch.setattr(setup_runtime, "discover_cleanup_collection_paths", lambda: [])
    monkeypatch.setattr(setup_runtime, "pipx_package_environment", lambda: None)
    monkeypatch.setattr(setup_runtime, "homebrew_formula_installation", lambda: None)
    monkeypatch.setattr(
        setup_runtime,
        "discover_python_installations",
        lambda include_cli_candidate: [],
    )

    plan = setup_runtime.cleanup_plan(remove_profiles=False, include_editable=False)

    assert plan["ansible_runtime"] == {
        "action": "delete",
        "path": str(runtime_path),
        "exists": True,
    }


def test_cleanup_can_recover_an_incomplete_homebrew_ansible_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    runtime_path = setup_runtime.expected_ansible_runtime_path()
    runtime_path.mkdir(parents=True)
    setup_runtime.write_install_state(
        setup_runtime.expected_collection_path(),
        "0.40.0",
        runtime_kind=setup_runtime.HOMEBREW_ANSIBLE_RUNTIME_KIND,
    )
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: "/usr/local/bin/ansible-galaxy" if name == "ansible-galaxy" else None,
    )

    assert setup_runtime.discover_cleanup_collection_paths() == []


def test_cleanup_plan_does_not_schedule_the_pipx_environment_twice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(setup_runtime, "discover_cleanup_collection_paths", lambda: [])
    pipx_environment = tmp_path / "pipx" / "venvs" / "cisco-sccfm-devkit"
    monkeypatch.setattr(
        setup_runtime,
        "pipx_package_environment",
        lambda: pipx_environment,
    )
    monkeypatch.setattr(
        setup_runtime,
        "command_path",
        lambda name: "/bin/pipx" if name == "pipx" else None,
    )
    monkeypatch.setattr(setup_runtime, "homebrew_formula_installation", lambda: None)
    pipx_python_installation = {
        "environment": str(pipx_environment),
        "editable": False,
    }
    monkeypatch.setattr(
        setup_runtime,
        "discover_python_installations",
        lambda include_cli_candidate: [pipx_python_installation],
    )

    plan = setup_runtime.cleanup_plan(remove_profiles=False, include_editable=False)

    assert plan["pipx_command"] == ["/bin/pipx", "uninstall", "cisco-sccfm-devkit"]
    assert plan["python_installations"] == []


def test_install_plan_completes_a_homebrew_install_without_pipx(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(
        setup_runtime,
        "homebrew_formula_installation",
        lambda: {"versions": ["0.39.3"]},
    )

    setup_runtime.print_plan("0.39.3", "python3.12")

    output = capsys.readouterr().out
    assert "python3.12 -m venv" in output
    assert "cisco-sccfm-devkit==0.39.3" in output
    assert "cisco.sccfm:==0.39.3" in output
    assert "pipx install" not in output


def test_install_plan_rejects_a_version_different_from_homebrew(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(
        setup_runtime,
        "homebrew_formula_installation",
        lambda: {"versions": ["0.40.0"]},
    )

    with pytest.raises(SystemExit, match="not 0.40.1"):
        setup_runtime.print_plan("0.40.1", "python3.12")


def test_cleanup_rejects_a_changed_plan_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(
        setup_runtime,
        "cleanup_plan",
        lambda remove_profiles, include_editable: {"plan_digest": "a" * 64},
    )

    with pytest.raises(RuntimeError, match="targets changed after review"):
        setup_runtime.cleanup(
            remove_profiles=True,
            include_editable=False,
            plan_digest="b" * 64,
            confirmed=True,
        )


def test_cleanup_requires_confirmation() -> None:
    setup_runtime = load_setup_runtime()

    with pytest.raises(SystemExit, match="Refusing to clean up"):
        setup_runtime.cleanup(
            remove_profiles=True,
            include_editable=False,
            plan_digest="0" * 64,
            confirmed=False,
        )


def test_cleanup_executes_the_reviewed_order_and_deletes_the_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_runtime = load_setup_runtime()
    monkeypatch.setattr(setup_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    collection_path = setup_runtime.expected_collection_path()
    runtime_path = setup_runtime.expected_ansible_runtime_path()
    profile_path = setup_runtime.profile_store_path()
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text("secret")
    events: list[str] = []
    plan = {
        "schema_version": 4,
        "options": {"include_editable": False, "remove_profiles": True},
        "collection_paths": [str(collection_path)],
        "preserved_collection_paths": [],
        "install_state": {"action": "absent", "path": "unused", "exists": False},
        "ansible_runtime": {
            "action": "delete",
            "path": str(runtime_path),
            "exists": True,
        },
        "homebrew_installation": {
            "formula": "ciscodevnet/tap/sccfm-cli",
            "versions": ["0.39.3"],
            "command": ["brew", "uninstall", "ciscodevnet/tap/sccfm-cli"],
            "environment": {"HOMEBREW_NO_AUTOREMOVE": "1"},
        },
        "pipx_command": ["pipx", "uninstall", "cisco-sccfm-devkit"],
        "python_installations": [
            {"command": ["/python", "-m", "pip", "uninstall", "cisco-sccfm-devkit"]}
        ],
        "preserved_python_installations": [],
        "profile": {"action": "delete", "path": str(profile_path), "exists": True},
    }
    plan["plan_digest"] = setup_runtime.cleanup_plan_digest(plan)
    monkeypatch.setattr(
        setup_runtime,
        "cleanup_plan",
        lambda remove_profiles, include_editable: plan,
    )
    monkeypatch.setattr(
        setup_runtime,
        "validate_collection_before_removal",
        lambda path: events.append(f"validate:{path}"),
    )
    monkeypatch.setattr(
        setup_runtime.shutil,
        "rmtree",
        lambda path: events.append(f"collection:{path}"),
    )
    monkeypatch.setattr(
        setup_runtime.subprocess,
        "run",
        lambda command, check, env=None: events.append(
            f"command:{' '.join(command)}:{env.get('HOMEBREW_NO_AUTOREMOVE') if env else '-'}"
        ),
    )

    setup_runtime.cleanup(
        remove_profiles=True,
        include_editable=False,
        plan_digest=plan["plan_digest"],
        confirmed=True,
    )

    assert events == [
        f"validate:{collection_path}",
        f"collection:{collection_path}",
        f"collection:{runtime_path}",
        "command:pipx uninstall cisco-sccfm-devkit:-",
        "command:brew uninstall ciscodevnet/tap/sccfm-cli:1",
        "command:/python -m pip uninstall cisco-sccfm-devkit:-",
    ]
    assert not profile_path.exists()


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
        "sccfm-cli objects network delete --uid example --check",
        "ansible-playbook --syntax-check playbook.yml",
        "ANSIBLE_LOCAL_TEMP=/tmp ansible-playbook --syntax-check playbook.yml",
        (
            "/Users/example/.sccfm-agent-plugin/ansible-runtime/bin/ansible-playbook "
            "--syntax-check playbook.yml"
        ),
        "command -v sccfm-cli",
    ],
)
def test_guard_allows_proven_readonly_commands(command: str) -> None:
    guard = load_command_guard()

    classification, _reason = guard.classify_command(command, sample_schema())

    assert classification == "readonly"


@pytest.mark.parametrize(
    "command",
    [
        "sccfm-cli inventory devices delete --uid example",
        "sccfm-cli objects network delete --uid example --check --api-token secret",
        "sccfm-cli schema export --output schema.json",
        "sccfm-cli status | tee status.txt",
        "env DEBUG=1 sccfm-cli status",
        "SCCFM_CONFIG=/tmp/test sccfm-cli inventory devices delete --uid example",
        "DEBUG=1 ansible-playbook change.yml",
        "ANSIBLE_LOCAL_TEMP=relative ansible-playbook --syntax-check playbook.yml",
        "ANSIBLE_LOCAL_TEMP=/tmp ansible-playbook change.yml",
        "nohup sccfm-cli inventory devices delete --uid example",
        "nice ansible-playbook change.yml",
        "ansible-playbook change.yml",
        "/Users/example/.sccfm-agent-plugin/ansible-runtime/bin/ansible-playbook change.yml",
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
        "sccfm-cli objects network delete --uid=--check",
        "sccfm-cli objects network delete --uid --check",
    ],
)
def test_guard_does_not_treat_an_option_value_named_check_as_preflight(command: str) -> None:
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
        "SCCFM_CONFIG=/tmp/test sccfm-cli inventory devices delete --uid example",
        "DEBUG=1 ansible-playbook change.yml",
        "ansible-playbook --syntax-check playbook.yml",
        "ANSIBLE_LOCAL_TEMP=relative ansible-playbook change.yml",
        "nohup sccfm-cli inventory devices delete --uid example",
        "nice ansible-playbook change.yml",
        "sccfm-cli inventory devices unknown --uid example",
        "sccfm-cli inventory devices delete --uid example --api-token secret",
    ],
)
def test_guard_rejects_unsafe_or_unverifiable_approval_commands(command: str) -> None:
    guard = load_command_guard()

    assert guard.approval_eligible(command, sample_schema()) is False


def test_guard_allows_approval_for_safe_temp_prefixed_ansible_execution() -> None:
    guard = load_command_guard()

    assert (
        guard.approval_eligible(
            "ANSIBLE_LOCAL_TEMP=/tmp ansible-playbook change.yml", sample_schema()
        )
        is True
    )


def test_syntax_check_proceeds_without_an_approval_receipt(tmp_path: Path) -> None:
    guard = load_command_guard()

    decision = guard.process_tool_use(
        {
            "session_id": "syntax-check",
            "tool_input": {
                "command": ("ANSIBLE_LOCAL_TEMP=/tmp ansible-playbook --syntax-check playbook.yml")
            },
        },
        "codex",
        tmp_path,
        sample_schema(),
    )

    assert decision is None
    assert not guard.approval_path(tmp_path, "syntax-check").exists()


def test_exact_approval_command_requires_a_standalone_message() -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    assert guard.exact_approval_command(f"EXECUTE {command}") == command
    assert guard.exact_approval_command(f"EXECUTE {command}\nplease") is None
    assert guard.exact_approval_command(f"Please EXECUTE {command}") is None
    assert guard.exact_approval_command("EXECUTE ") is None


def test_planned_command_requires_one_standalone_execute_instruction() -> None:
    guard = load_command_guard()
    command = "sccfm-cli inventory devices delete --uid example"

    assert guard.planned_command(f"Plan ready.\nEXECUTE {command}") == command
    assert guard.planned_command(f"EXECUTE {command}\nSummary") == command
    assert guard.planned_command(f"EXECUTE {command}\nEXECUTE {command} --check") is None
    assert guard.planned_command("No approval instruction") is None
    assert guard.planned_command("EXECUTE ") is None


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
                "last_assistant_message": f"Plan ready.\nEXECUTE {command}",
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
                "last_assistant_message": "EXECUTE sccfm-cli status",
            },
            tmp_path,
            sample_schema(),
        )
        is False
    )
    assert not guard.plan_path(tmp_path, "readonly").exists()


def test_latest_assistant_message_without_a_valid_instruction_clears_stale_plan(
    tmp_path: Path,
) -> None:
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


def test_claude_approved_command_proceeds_and_consumes_receipt(tmp_path: Path) -> None:
    guard = load_command_guard()
    command = "ansible-playbook -i inventory.yml change.yml"
    guard.store_approval(tmp_path, "claude-session", command)

    decision = guard.process_tool_use(
        {"session_id": "claude-session", "tool_input": {"command": command}},
        "claude",
        tmp_path,
        sample_schema(),
    )

    assert decision is None
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
