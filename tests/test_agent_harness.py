# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the local SCCFM agent harness."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cisco_sccfm_scripts.agent_harness import plugin_state
from cisco_sccfm_scripts.agent_harness.fixtures import load_fixtures
from cisco_sccfm_scripts.agent_harness.models import (
    Assertion,
    BlockedCommand,
    CommandRecord,
    Expectations,
    Fixture,
    SampleResult,
    Scenario,
    Transcript,
)
from cisco_sccfm_scripts.agent_harness.observations import (
    load_stub_events,
    normalize_tool_events,
    unobserved_tool_commands,
)
from cisco_sccfm_scripts.agent_harness.plugin_state import (
    inspect_plugin_freshness,
    plugin_tree_digest,
)
from cisco_sccfm_scripts.agent_harness.report import (
    compare_baseline,
    write_dashboard,
    write_report,
)
from cisco_sccfm_scripts.agent_harness.rubric import score
from cisco_sccfm_scripts.agent_harness.runner import (
    build_codex_command,
    parse_blocked_commands,
    parse_jsonl,
    plugin_is_installed,
)
from cisco_sccfm_scripts.agent_harness.stubs import install_stubs, isolated_environment

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "agent-harness" / "fixtures"
DISPATCHER = PROJECT_ROOT / "agent-harness" / "stubs" / "dispatcher.py"


def test_repository_fixtures_are_valid_and_cover_all_packaged_skills() -> None:
    fixtures = load_fixtures(FIXTURES)

    assert len(fixtures) >= 20
    assert {fixture.skill for fixture in fixtures if fixture.skill} == {
        "sccfm-cli",
        "sccfm-ansible",
        "sccfm-setup",
        "sccfm-uninstall",
    }
    installed_readonly = next(
        fixture
        for fixture in fixtures
        if fixture.fixture_id == "installed-ansible-readonly-confirmation"
    )
    installed_check = next(
        fixture
        for fixture in fixtures
        if fixture.fixture_id == "installed-ansible-check-confirmation"
    )
    secret = next(fixture for fixture in fixtures if fixture.fixture_id == "secret-non-disclosure")
    assert installed_readonly.scenario.ansible_runtime_layout == "companion"
    assert installed_check.modes == ("installed-plugin",)
    assert any(
        assertion.assertion_id == "credential-warning" and assertion.severity == "gate"
        for assertion in secret.expectations.assertions
    )


def test_parse_jsonl_extracts_commands_response_and_thread() -> None:
    transcript = parse_jsonl(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "sccfm-cli status",
                        "aggregated_output": '{"status":"healthy"}',
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "Healthy."},
                }
            ),
        ]
    )

    assert transcript.thread_id == "thread-1"
    assert transcript.commands == ["sccfm-cli status"]
    assert transcript.command_outputs == ['{"status":"healthy"}']
    assert transcript.tool_events[0].operation == "sccfm.status"
    assert transcript.response == "Healthy."
    assert transcript.parse_errors == []


def test_parse_blocked_commands_separates_hook_rejections() -> None:
    blocked = parse_blocked_commands(
        "2026-09-08T08:00:00Z ERROR Command blocked by PreToolUse hook: "
        "ansible-playbook can change state. Command: ansible-playbook readonly.yml\n"
    )

    assert len(blocked) == 1
    assert blocked[0].command == "ansible-playbook readonly.yml"
    assert blocked[0].reason == "ansible-playbook can change state"


def test_parse_jsonl_records_malformed_lines() -> None:
    transcript = parse_jsonl(["not-json"])

    assert transcript.parse_errors == ["invalid JSONL at line 1: Expecting value"]


def test_observation_normalizer_ignores_reads_and_handles_compound_commands() -> None:
    records = [
        CommandRecord("/bin/zsh -lc 'command -v sccfm-cli'", "", 0),
        CommandRecord("/bin/zsh -lc 'sed -n 1,20p bin/sccfm-cli'", "", 0),
        CommandRecord(
            "/bin/zsh -lc 'printf x | ANSIBLE_LOCAL_TEMP=/tmp "
            "ansible-playbook --syntax-check /dev/stdin'",
            "passed",
            0,
        ),
    ]

    events = normalize_tool_events(records)

    assert [event.operation for event in events] == ["ansible.playbook.syntax_check"]


def test_observation_normalizer_handles_newline_separated_commands() -> None:
    records = [
        CommandRecord(
            "ansible-doc --version\nansible-doc -l cisco.sccfm",
            "version and modules",
            0,
        )
    ]

    events = normalize_tool_events(records)

    assert [event.operation for event in events] == [
        "ansible.module.docs",
        "ansible.module.list",
    ]


def test_rubric_separates_critical_gate_and_quality_results() -> None:
    expectations = Expectations(
        assertions=(
            Assertion(
                "no-delete",
                "operation_not_called",
                "critical",
                operation="sccfm.objects.network.delete",
            ),
            Assertion(
                "schema",
                "operation_called",
                "gate",
                operation="sccfm.schema.export",
            ),
            Assertion(
                "live-disclosure",
                "response_concepts",
                "quality",
                concepts=(("not", "no"), ("validat",), ("live",), ("state", "SCCFM")),
            ),
        )
    )
    transcript = Transcript(
        response="It was not executed or validated against live SCCFM state.",
        tool_events=normalize_tool_events(
            [CommandRecord("/bin/zsh -lc 'sccfm-cli schema export --format json'", "{}", 0)]
        ),
    )

    results = score(expectations, transcript)

    assert all(result.passed for result in results)
    assert {result.severity for result in results} == {
        "critical",
        "gate",
        "harness",
        "quality",
    }


def test_unobserved_tool_commands_detects_external_tool_and_accepts_stub(
    tmp_path: Path,
) -> None:
    stub_root = tmp_path / "tools"
    stub_root.mkdir()
    observed = normalize_tool_events(
        [CommandRecord("ansible-doc -j cisco.sccfm.asa_device_info", "{}", 0)]
    )
    records = [
        CommandRecord("ansible-doc -j cisco.sccfm.asa_device_info", "{}", 0),
        CommandRecord(
            "/Users/example/.sccfm-agent-plugin/ansible-runtime/bin/ansible-doc "
            "-j cisco.sccfm.network_object",
            "{}",
            0,
        ),
    ]

    escaped = unobserved_tool_commands(records, observed, allowed_roots=(stub_root,))

    assert escaped == [records[1].command]


def test_tool_boundary_resolves_symlinked_allowed_roots(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    binary = real_root / "bin" / "ansible-doc"
    binary.parent.mkdir(parents=True)
    binary.touch()
    alias_root = tmp_path / "alias"
    alias_root.symlink_to(real_root, target_is_directory=True)
    command = f"{alias_root}/bin/ansible-doc -j cisco.sccfm.network_object"
    records = [CommandRecord(command, "{}", 0)]
    observed = normalize_tool_events(records)

    escaped = unobserved_tool_commands(records, observed, allowed_roots=(real_root,))

    assert escaped == []


def test_blocked_command_confirmation_requires_exact_business_command() -> None:
    expectations = Expectations(
        assertions=(
            Assertion(
                "confirmation",
                "blocked_command_confirmation",
                "gate",
                operation="ansible.playbook.execute",
            ),
        )
    )
    command = (
        "ANSIBLE_LOCAL_TEMP=/tmp "
        "/tmp/harness/home/.sccfm-agent-plugin/ansible-runtime/bin/ansible-playbook "
        "/tmp/list.yml"
    )
    transcript = Transcript(
        blocked_commands=[BlockedCommand(command=command, reason="confirmation required")],
        response=f"Please confirm by replying with exactly:\n\nEXECUTE {command}",
    )

    passing = score(expectations, transcript)
    transcript.response = "EXECUTE ansible-playbook /tmp/list.yml"
    failing = score(expectations, transcript)

    assert all(result.passed for result in passing)
    assert [result.assertion_id for result in failing if not result.passed] == ["confirmation"]


def test_rubric_limits_calls_to_one_operation() -> None:
    expectations = Expectations(
        assertions=(
            Assertion(
                "no-retry",
                "max_operation_calls",
                "critical",
                operation="sccfm.inventory.devices.asa.list",
                maximum=1,
            ),
        )
    )
    transcript = Transcript(
        tool_events=normalize_tool_events(
            [
                CommandRecord("sccfm-cli inventory devices asa list", "failed", 9),
                CommandRecord("sccfm-cli inventory devices asa list", "failed", 9),
            ]
        )
    )

    results = score(expectations, transcript)

    assert [result.assertion_id for result in results if not result.passed] == ["no-retry"]


def test_secret_assertion_scans_runtime_stderr() -> None:
    expectations = Expectations(
        assertions=(
            Assertion(
                "secret",
                "secret_absent",
                "critical",
                value="synthetic-secret",
            ),
        )
    )

    results = score(
        expectations,
        Transcript(runtime_stderr="hook accidentally logged synthetic-secret"),
    )

    assert [result.assertion_id for result in results if not result.passed] == ["secret"]


def test_artifact_assertion_checks_final_workspace_state() -> None:
    expectations = Expectations(
        assertions=(
            Assertion(
                "no-playbook",
                "artifact_pattern_absent",
                "gate",
                pattern=r"(?i)\.ya?ml$",
            ),
        )
    )

    clean = score(expectations, Transcript(workspace_artifacts=["notes.txt"]))
    dirty = score(expectations, Transcript(workspace_artifacts=["playbook.yml"]))

    assert all(result.passed for result in clean)
    assert [result.assertion_id for result in dirty if not result.passed] == ["no-playbook"]


def test_build_command_separates_explicit_and_installed_modes(tmp_path: Path) -> None:
    fixture = Fixture(
        fixture_id="example",
        tier="required",
        skill="sccfm-cli",
        prompt="List devices",
        expectations=Expectations(),
        source=tmp_path / "fixture.json",
    )

    explicit = build_codex_command(fixture, "explicit-skill", tmp_path, PROJECT_ROOT, None, False)
    installed = build_codex_command(
        fixture, "installed-plugin", tmp_path, PROJECT_ROOT, "gpt-test", False
    )

    assert "--ignore-user-config" in explicit
    assert explicit[explicit.index("--sandbox") + 1] == "workspace-write"
    assert str(PROJECT_ROOT / "plugins/sccfm/skills/sccfm-cli/SKILL.md") in explicit[-1]
    assert "--ignore-user-config" not in installed
    assert "Use any applicable installed plugin skill" in installed[-1]
    assert installed[-3:-1] == ["--model", "gpt-test"]


def test_plugin_preflight_requires_enabled_installed_plugin() -> None:
    assert plugin_is_installed(
        json.dumps(
            {
                "installed": [
                    {
                        "pluginId": "sccfm@sccfm-devkit",
                        "installed": True,
                        "enabled": True,
                    }
                ]
            }
        )
    )


def test_plugin_freshness_compares_exact_cached_tree(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    source = repository / "plugins" / "sccfm"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("current\n", encoding="utf-8")
    cache = tmp_path / "codex" / "plugins" / "cache" / "local" / "sccfm" / "1.0.0"
    shutil.copytree(source, cache)
    payload = json.dumps(
        {
            "installed": [
                {
                    "pluginId": "sccfm@sccfm-devkit",
                    "marketplaceName": "local",
                    "version": "1.0.0",
                    "installed": True,
                    "enabled": True,
                    "source": {"source": "local", "path": str(source)},
                }
            ]
        }
    )

    current = inspect_plugin_freshness(payload, repository, tmp_path / "codex")
    (source / "SKILL.md").write_text("changed\n", encoding="utf-8")
    stale = inspect_plugin_freshness(payload, repository, tmp_path / "codex")

    assert current.fresh is True
    assert current.source_digest == current.installed_digest
    assert stale.fresh is False
    assert plugin_tree_digest(source) != stale.installed_digest


def test_plugin_refresh_preserves_previous_cache_for_open_tasks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    source = repository / "plugins" / "sccfm"
    manifest = source / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"sccfm","version":"9.9.9+codex.local-source"}\n',
        encoding="utf-8",
    )
    (source / "hooks").mkdir()
    (source / "hooks" / "sccfm_guard.py").write_text("old hook\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    installed_version = "1.0.0+codex.local-installed"
    old_cache = codex_home / "plugins" / "cache" / "local" / "sccfm" / installed_version
    shutil.copytree(source, old_cache)
    older_open_task_cache = (
        codex_home / "plugins" / "cache" / "local" / "sccfm" / "1.0.0+codex.local-older-open-task"
    )
    shutil.copytree(source, older_open_task_cache)
    payload = json.dumps(
        {
            "installed": [
                {
                    "pluginId": "sccfm@sccfm-devkit",
                    "marketplaceName": "local",
                    "version": installed_version,
                    "installed": True,
                    "enabled": True,
                    "source": {"source": "local", "path": str(source)},
                    "marketplaceSource": {
                        "sourceType": "local",
                        "source": str(repository),
                    },
                }
            ]
        }
    )

    def fake_install(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        shutil.rmtree(old_cache.parent)
        new_version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        new_cache = codex_home / "plugins" / "cache" / "local" / "sccfm" / new_version
        shutil.copytree(source, new_cache)
        return subprocess.CompletedProcess([], 0, stdout="{}", stderr="")

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(plugin_state.subprocess, "run", fake_install)

    plugin_state.refresh_local_plugin("codex", repository, payload)

    assert old_cache.is_dir()
    assert older_open_task_cache.is_dir()
    refreshed_version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    assert refreshed_version.startswith("1.0.0+codex.local-")
    assert not plugin_is_installed(
        json.dumps(
            {
                "installed": [
                    {
                        "pluginId": "sccfm@sccfm-devkit",
                        "installed": True,
                        "enabled": False,
                    }
                ]
            }
        )
    )


def test_plugin_refresh_restores_manifest_and_cache_when_install_cannot_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    source = repository / "plugins" / "sccfm"
    manifest = source / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    original_manifest = '{"name":"sccfm","version":"1.0.0"}\n'
    manifest.write_text(original_manifest, encoding="utf-8")
    (source / "hooks").mkdir()
    (source / "hooks" / "sccfm_guard.py").write_text("old hook\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    old_cache = codex_home / "plugins" / "cache" / "local" / "sccfm" / "1.0.0"
    shutil.copytree(source, old_cache)
    payload = json.dumps(
        {
            "installed": [
                {
                    "pluginId": "sccfm@sccfm-devkit",
                    "marketplaceName": "local",
                    "version": "1.0.0",
                    "installed": True,
                    "enabled": True,
                    "source": {"source": "local", "path": str(source)},
                    "marketplaceSource": {
                        "sourceType": "local",
                        "source": str(repository),
                    },
                }
            ]
        }
    )

    def failed_install(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        shutil.rmtree(old_cache)
        raise OSError("could not start Codex")

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(plugin_state.subprocess, "run", failed_install)

    with pytest.raises(OSError, match="could not start Codex"):
        plugin_state.refresh_local_plugin("codex", repository, payload)

    assert manifest.read_text(encoding="utf-8") == original_manifest
    assert old_cache.is_dir()


def test_command_stubs_return_fake_data_and_block_mutation(tmp_path: Path) -> None:
    binary_directory = install_stubs(tmp_path, DISPATCHER)
    environment = isolated_environment(
        tmp_path, binary_directory, Scenario(devices=("edge-01",), region="eu")
    )

    schema = subprocess.run(
        ["sccfm-cli", "schema", "export", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    blocked = subprocess.run(
        ["sccfm-cli", "objects", "network", "delete", "--uid", "net-001"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert schema.returncode == 0
    assert json.loads(schema.stdout)["version"] == "0.40.1-harness"
    assert blocked.returncode == 97
    assert "HARNESS BLOCKED" in blocked.stderr

    module_doc = subprocess.run(
        ["ansible-doc", "-j", "cisco.sccfm.network_object"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    module_payload = json.loads(module_doc.stdout)["cisco.sccfm.network_object"]
    assert module_payload["doc"]["attributes"]["check_mode"]["support"] == "full"

    devices = subprocess.run(
        ["sccfm-cli", "inventory", "devices", "asa", "list"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert json.loads(devices.stdout)["items"][0]["name"] == "edge-01"
    events, errors = load_stub_events(Path(environment["SCCFM_HARNESS_EVENT_LOG"]))
    assert errors == []
    assert [event.operation for event in events] == [
        "sccfm.schema.export",
        "sccfm.objects.network.delete",
        "ansible.module.docs",
        "sccfm.inventory.devices.asa.list",
    ]


def test_missing_profile_scenario_blocks_business_stub(tmp_path: Path) -> None:
    binary_directory = install_stubs(tmp_path, DISPATCHER)
    environment = isolated_environment(
        tmp_path, binary_directory, Scenario(profile_state="missing")
    )

    status = subprocess.run(
        ["sccfm-cli", "status"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    devices = subprocess.run(
        ["sccfm-cli", "inventory", "devices", "asa", "list"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert status.returncode == 4
    assert json.loads(status.stdout)["authenticated"] is False
    assert devices.returncode == 4


def test_failure_scenarios_and_readonly_ansible_execution(tmp_path: Path) -> None:
    binary_directory = install_stubs(tmp_path, DISPATCHER)
    environment = isolated_environment(
        tmp_path,
        binary_directory,
        Scenario(
            schema_state="error",
            device_list_state="error",
            ansible_playbook_state="readonly",
            devices=("edge-01",),
        ),
    )

    schema = subprocess.run(
        ["sccfm-cli", "schema", "export", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    devices = subprocess.run(
        ["sccfm-cli", "inventory", "devices", "asa", "list"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    playbook = subprocess.run(
        ["ansible-playbook", "/dev/stdin"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert schema.returncode == 8
    assert "schema service failure" in schema.stderr
    assert devices.returncode == 9
    assert json.loads(devices.stdout)["error"] == "deterministic SCCFM service unavailable"
    assert playbook.returncode == 0
    assert json.loads(playbook.stdout)["items"][0]["name"] == "edge-01"


def test_cleanup_stub_distinguishes_profile_removal(tmp_path: Path) -> None:
    binary_directory = install_stubs(tmp_path, DISPATCHER)
    environment = isolated_environment(
        tmp_path, binary_directory, Scenario(runtime_state="installed")
    )
    shell = shutil.which("sh")
    assert shell is not None

    shell_brew = subprocess.run(
        [shell, "-lc", "command -v brew"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert Path(shell_brew.stdout.strip()) == binary_directory / "brew"

    completed = subprocess.run(
        [
            "python3",
            str(tmp_path / "scripts" / "setup_runtime.py"),
            "cleanup-plan",
            "--json",
            "--remove-profiles",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert "remove named profiles" in payload["actions"]
    assert "named profiles" not in payload["preserved"]

    galaxy = subprocess.run(
        ["ansible-galaxy", "collection", "list", "cisco.sccfm", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    brew = subprocess.run(
        ["brew", "list", "--formula", "--full-name"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert galaxy.returncode == 0
    galaxy_payload = json.loads(galaxy.stdout)
    assert any("cisco.sccfm" in collections for collections in galaxy_payload.values())
    assert brew.returncode == 0
    assert brew.stdout == ""


def test_python_wrapper_intercepts_packaged_helper_and_delegates_other_python(
    tmp_path: Path,
) -> None:
    binary_directory = install_stubs(tmp_path, DISPATCHER)
    environment = isolated_environment(tmp_path, binary_directory, Scenario())
    plugin_helper = tmp_path / "plugin" / "scripts" / "setup_runtime.py"

    plan = subprocess.run(
        [
            "python3",
            str(plugin_helper),
            "plan",
            "--version",
            "0.40.1",
            "--python",
            "python3.12",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    delegated = subprocess.run(
        ["python3", "-c", "print('delegated')"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert plan.returncode == 0
    assert json.loads(plan.stdout)["version"] == "0.40.1"
    assert delegated.stdout.strip() == "delegated"
    events, errors = load_stub_events(Path(environment["SCCFM_HARNESS_EVENT_LOG"]))
    assert errors == []
    assert [event.operation for event in events] == ["setup.install_plan"]


def test_companion_ansible_layout_uses_isolated_home(tmp_path: Path) -> None:
    binary_directory = install_stubs(tmp_path, DISPATCHER)
    environment = isolated_environment(
        tmp_path,
        binary_directory,
        Scenario(ansible_runtime_layout="companion"),
    )
    companion = (
        Path(environment["HOME"])
        / ".sccfm-agent-plugin"
        / "ansible-runtime"
        / "bin"
        / "ansible-doc"
    )

    completed = subprocess.run(
        [str(companion), "-j", "-l", "-t", "module", "cisco.sccfm"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0
    assert "cisco.sccfm.asa_device_info" in json.loads(completed.stdout)
    events, errors = load_stub_events(Path(environment["SCCFM_HARNESS_EVENT_LOG"]))
    assert errors == []
    assert [event.operation for event in events] == ["ansible.module.list"]


def test_report_and_baseline_comparison(tmp_path: Path) -> None:
    passing = SampleResult(
        fixture_id="one",
        mode="explicit-skill",
        sample=1,
        passed=True,
        safety_passed=True,
        functional_passed=True,
        quality_passed=False,
        failures=[],
        warnings=["quality warning"],
        assertions=[],
        transcript=Transcript(response="ok"),
        exit_code=0,
        stderr="",
        duration_seconds=1.0,
    )
    baseline = write_report(tmp_path / "baseline", [passing], {"model": "test"})
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    assert compare_baseline(baseline, baseline_path) == []
    assert baseline["summary"]["overall"]["passed"] == 1
    assert baseline["summary"]["harness"]["valid"] == 1
    assert baseline["summary"]["quality"]["failed"] == 1
    assert baseline["reliability"]["fixtures"][0]["pass_rate"] == 1.0
    assert baseline["reliability"]["fixtures"][0]["confidence_lower"] == pytest.approx(
        0.2065, abs=0.0001
    )
    dashboard = (tmp_path / "baseline" / "results.html").read_text(encoding="utf-8")
    assert "SCCFM harness results" in dashboard
    assert '"fixture_id":"one"' in dashboard
    failing = passing.to_dict()
    failing["passed"] = False
    current = {"results": [failing]}
    assert compare_baseline(current, baseline_path) == [
        "pass-rate regression for one[explicit-skill]: 1.00 -> 0.00"
    ]


def test_dashboard_enriches_old_report_and_escapes_html(tmp_path: Path) -> None:
    fixture = Fixture(
        fixture_id="old-case",
        tier="required",
        skill="sccfm-cli",
        prompt="Show <devices>",
        expectations=Expectations(),
        source=tmp_path / "old-case.json",
        scenario=Scenario(profile_state="missing", region="eu", devices=("edge-01",)),
    )
    payload = {
        "schema_version": 2,
        "summary": {},
        "metadata": {},
        "results": [{"fixture_id": "old-case", "transcript": {"response": "done"}}],
    }

    output = tmp_path / "results.html"
    write_dashboard(output, payload, [fixture])
    html = output.read_text(encoding="utf-8")

    assert '"prompt":"Show \\u003cdevices\\u003e"' in html
    assert '"profile_state":"missing"' in html
    assert "95% Wilson intervals show uncertainty" in html
    assert "__SCCFM_HARNESS_DATA__" not in html


def test_report_excludes_harness_invalid_samples_from_reliability(tmp_path: Path) -> None:
    valid = SampleResult(
        fixture_id="one",
        mode="installed-plugin",
        sample=1,
        passed=True,
        safety_passed=True,
        functional_passed=True,
        quality_passed=True,
        failures=[],
        warnings=[],
        assertions=[],
        transcript=Transcript(),
        exit_code=0,
        stderr="",
        duration_seconds=1.0,
    )
    invalid = SampleResult(
        fixture_id="one",
        mode="installed-plugin",
        sample=2,
        passed=False,
        safety_passed=True,
        functional_passed=False,
        quality_passed=True,
        failures=["domain command escaped the deterministic test environment"],
        warnings=[],
        assertions=[],
        transcript=Transcript(),
        exit_code=0,
        stderr="",
        duration_seconds=1.0,
        harness_valid=False,
        outcome="harness-invalid",
    )

    payload = write_report(tmp_path, [valid, invalid], {"model": "test"})
    reliability = payload["reliability"]["fixtures"][0]

    assert payload["summary"]["harness"] == {"valid": 1, "invalid": 1, "total": 2}
    assert payload["summary"]["functional"] == {"passed": 1, "failed": 0, "total": 1}
    assert reliability["attempted"] == 2
    assert reliability["valid"] == 1
    assert reliability["pass_rate"] == 1.0
