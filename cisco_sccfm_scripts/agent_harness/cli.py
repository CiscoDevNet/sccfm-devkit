# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Command-line interface for local and CI agent evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence, cast

from .credentials import (
    SCRUB_VARIABLE,
    install_probe,
    isolation_settings,
    preserved_credential_names,
    read_probe,
    redact,
)
from .fixtures import load_fixtures
from .models import Agent, Fixture, Mode, Scenario
from .plugin_state import (
    PLUGIN_ID,
    inspect_plugin_freshness,
    plugin_tree_digest,
    refresh_local_plugin,
)
from .report import compare_baseline, write_dashboard, write_report
from .runner import build_agent_command, run_sample
from .stubs import isolated_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = REPOSITORY_ROOT / "agent-harness" / "fixtures"


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the SCCFM agent harness CLI."""

    parser = _parser()
    options = parser.parse_args(arguments)
    try:
        if options.command == "validate":
            return _validate(Path(options.fixtures))
        if options.command == "run":
            return _run(options)
        if options.command == "dashboard":
            return _dashboard(options)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    parser.error("a subcommand is required")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sccfm-agent-harness",
        description="Evaluate SCCFM agent skills against deterministic command doubles.",
    )
    subparsers = parser.add_subparsers(dest="command")
    validate = subparsers.add_parser("validate", help="validate fixtures and local assets")
    validate.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))

    dashboard = subparsers.add_parser(
        "dashboard", help="render a local HTML dashboard from an existing JSON report"
    )
    dashboard.add_argument("results", type=Path)
    dashboard.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    dashboard.add_argument("--output", type=Path)

    run = subparsers.add_parser("run", help="run one or more evaluation cases")
    run.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    run.add_argument("--fixture", action="append", dest="fixture_ids")
    run.add_argument("--tier", choices=("required", "aspirational", "all"), default="required")
    run.add_argument(
        "--mode", choices=("explicit-skill", "installed-plugin"), default="explicit-skill"
    )
    run.add_argument("--agent", choices=("codex", "claude"), default="codex")
    run.add_argument("--samples", type=int, default=1)
    run.add_argument("--model")
    run.add_argument("--timeout", type=int, default=300)
    run.add_argument(
        "--runtime-retries",
        type=int,
        default=1,
        help="retry provider/runtime failures only; assertion failures are never retried",
    )
    run.add_argument("--output", type=Path)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--compare-baseline", type=Path)
    run.add_argument("--write-baseline", type=Path)
    run.add_argument("--bypass-hook-trust", action="store_true")
    run.add_argument(
        "--refresh-installed-plugin",
        action="store_true",
        help=(
            "when installed-plugin mode is stale, add a local cachebuster and reinstall it "
            "from this checkout"
        ),
    )
    run.add_argument(
        "--strict-quality",
        action="store_true",
        help="promote quality-only semantic failures to the process exit gate",
    )
    return parser


def _validate(fixtures_directory: Path) -> int:
    fixtures = load_fixtures(fixtures_directory)
    dispatcher = REPOSITORY_ROOT / "agent-harness" / "stubs" / "dispatcher.py"
    if not dispatcher.is_file():
        raise ValueError(f"missing stub dispatcher: {dispatcher}")
    for fixture in fixtures:
        if fixture.skill:
            skill_path = (
                REPOSITORY_ROOT / "plugins" / "sccfm" / "skills" / fixture.skill / "SKILL.md"
            )
            if not skill_path.is_file():
                raise ValueError(f"{fixture.source}: missing skill {skill_path}")
    manifest = REPOSITORY_ROOT / "plugins" / "sccfm" / ".codex-plugin" / "plugin.json"
    json.loads(manifest.read_text(encoding="utf-8"))
    print(f"validated {len(fixtures)} fixtures, stub dispatcher, skills, and plugin manifest")
    return 0


def _run(options: argparse.Namespace) -> int:
    if options.samples < 1:
        raise ValueError("--samples must be at least 1")
    if options.timeout < 1:
        raise ValueError("--timeout must be at least 1")
    if options.runtime_retries < 0:
        raise ValueError("--runtime-retries must be non-negative")
    if (options.compare_baseline or options.write_baseline) and not options.model:
        raise ValueError("--model is required when reading or writing a baseline")
    mode = cast(Mode, options.mode)
    agent = cast(Agent, options.agent)
    fixtures = _select_fixtures(
        load_fixtures(Path(options.fixtures)), options.fixture_ids, options.tier, mode
    )
    if not fixtures:
        raise ValueError("no fixtures matched the selection")
    executable = shutil.which(agent)
    if executable is None:
        raise ValueError(f"{agent} executable is not on PATH")
    if options.refresh_installed_plugin and mode != "installed-plugin":
        raise ValueError("--refresh-installed-plugin requires --mode installed-plugin")
    if options.refresh_installed_plugin and agent != "codex":
        raise ValueError(
            "--refresh-installed-plugin is unnecessary for Claude; Claude loads the current "
            "checkout directly with --plugin-dir"
        )
    if options.bypass_hook_trust and agent != "codex":
        raise ValueError("--bypass-hook-trust is supported only by Codex")
    if agent == "claude" and not options.dry_run:
        _validate_claude_isolation(executable, options.model, options.timeout)
    plugin_freshness = None
    if mode == "installed-plugin" and agent == "codex":
        plugin_payload = _plugin_list_payload(executable)
        plugin_freshness = inspect_plugin_freshness(plugin_payload, REPOSITORY_ROOT)
        if not plugin_freshness.fresh and options.refresh_installed_plugin:
            refresh_local_plugin(executable, REPOSITORY_ROOT, plugin_payload)
            plugin_payload = _plugin_list_payload(executable)
            plugin_freshness = inspect_plugin_freshness(plugin_payload, REPOSITORY_ROOT)
        if not plugin_freshness.fresh:
            raise ValueError(
                f"installed {PLUGIN_ID} is stale: {plugin_freshness.reason}; rerun with "
                "--refresh-installed-plugin to update this confirmed local installation"
            )

    if options.dry_run:
        workspace = Path("/tmp/sccfm-agent-harness-WORKSPACE")
        settings_path = (
            Path("/tmp/sccfm-agent-tools-TOOLS/claude-settings.json") if agent == "claude" else None
        )
        for fixture in fixtures:
            command = build_agent_command(
                agent,
                fixture,
                mode,
                workspace,
                REPOSITORY_ROOT,
                options.model,
                options.bypass_hook_trust,
                settings_path,
            )
            print(f"{fixture.fixture_id}: {json.dumps(command)}")
        return 0

    results = []
    for fixture in fixtures:
        for sample in range(1, options.samples + 1):
            print(
                f"running {fixture.fixture_id} [{agent}/{mode}] "
                f"sample {sample}/{options.samples}"
            )
            prior_runtime_errors: list[str] = []
            total_duration = 0.0
            for attempt in range(1, options.runtime_retries + 2):
                result = run_sample(
                    fixture,
                    mode,
                    sample,
                    REPOSITORY_ROOT,
                    options.model,
                    options.timeout,
                    options.bypass_hook_trust,
                    options.strict_quality,
                    agent,
                )
                total_duration += result.duration_seconds
                result.duration_seconds = round(total_duration, 3)
                result.runtime_attempts = attempt
                result.prior_runtime_errors = list(prior_runtime_errors)
                if result.outcome != "runtime-error" or attempt > options.runtime_retries:
                    break
                prior_runtime_errors.append("; ".join(result.failures))
                print(
                    f"runtime failure; retrying {fixture.fixture_id} "
                    f"({attempt}/{options.runtime_retries})"
                )
            results.append(result)
            if result.outcome == "harness-invalid":
                print(f"HARNESS INVALID: {'; '.join(result.failures)}")
            elif result.outcome == "runtime-error":
                print(f"RUNTIME ERROR: {'; '.join(result.failures)}")
            elif result.passed and result.warnings:
                print(f"PASS WITH WARNINGS: {'; '.join(result.warnings)}")
            else:
                print("PASS" if result.passed else f"FAIL: {'; '.join(result.failures)}")

    output_directory = options.output or _default_output_directory()
    agent_version = _command_version([executable, "--version"])
    source_digest = plugin_tree_digest(REPOSITORY_ROOT / "plugins" / "sccfm")
    fixture_digest = _fixture_digest(fixtures)
    model = options.model or "configured default"
    fingerprint = {
        "agent": agent,
        "agent_version": agent_version,
        "fixture_digest": fixture_digest,
        "mode": mode,
        "model": model,
        "source_digest": source_digest,
    }
    payload = write_report(
        output_directory,
        results,
        {
            "mode": mode,
            "agent": agent,
            "model": model,
            "agent_version": agent_version,
            "codex_version": agent_version if agent == "codex" else None,
            "source_digest": source_digest,
            "fixture_digest": fixture_digest,
            "comparison_fingerprint": fingerprint,
            "plugin_id": "sccfm@sccfm-devkit" if mode == "installed-plugin" else None,
            "plugin_freshness": (
                plugin_freshness.to_dict()
                if plugin_freshness is not None
                else (
                    _claude_source_freshness()
                    if mode == "installed-plugin" and agent == "claude"
                    else None
                )
            ),
            "samples": options.samples,
            "runtime_retries": options.runtime_retries,
            "strict_quality": options.strict_quality,
        },
    )
    print(
        "reports: "
        f"{output_directory / 'results.json'}, "
        f"{output_directory / 'results.md'}, and "
        f"{output_directory / 'results.html'}"
    )

    failures = sum(not result.passed for result in results)
    if options.compare_baseline:
        regressions = compare_baseline(payload, options.compare_baseline)
        for regression in regressions:
            print(f"REGRESSION: {regression}", file=sys.stderr)
        failures += len(regressions)
    if options.write_baseline:
        options.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output_directory / "results.json", options.write_baseline)
        print(f"baseline: {options.write_baseline}")
    return 1 if failures else 0


def _select_fixtures(
    fixtures: list[Fixture], fixture_ids: list[str] | None, tier: str, mode: Mode
) -> list[Fixture]:
    requested = set(fixture_ids or [])
    known = {fixture.fixture_id for fixture in fixtures}
    unknown = requested - known
    if unknown:
        raise ValueError(f"unknown fixture ids: {', '.join(sorted(unknown))}")
    return [
        fixture
        for fixture in fixtures
        if (not requested or fixture.fixture_id in requested)
        and (tier == "all" or fixture.tier == tier)
        and mode in fixture.modes
    ]


def _dashboard(options: argparse.Namespace) -> int:
    results_path = Path(options.results)
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    output_path = options.output or results_path.with_suffix(".html")
    fixtures = load_fixtures(Path(options.fixtures))
    write_dashboard(output_path, payload, fixtures)
    print(f"dashboard: {output_path}")
    return 0


def _plugin_list_payload(codex: str) -> str:
    completed = subprocess.run(
        [codex, "plugin", "list", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            "could not inspect installed plugins: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )
    return completed.stdout


def _claude_source_freshness() -> dict[str, object]:
    """Describe Claude's direct, per-session checkout plugin loading."""

    plugin = REPOSITORY_ROOT / "plugins" / "sccfm"
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    digest = plugin_tree_digest(plugin)
    return {
        "plugin_id": PLUGIN_ID,
        "version": manifest.get("version", "unknown"),
        "marketplace": "checkout",
        "source_path": str(plugin),
        "cache_path": None,
        "source_digest": digest,
        "installed_digest": digest,
        "fresh": True,
        "reason": "Claude loads a staged copy of this checkout with --plugin-dir",
    }


def _fixture_digest(fixtures: Sequence[Fixture]) -> str:
    """Hash the exact selected fixture definitions used by a run."""

    digest = hashlib.sha256()
    for fixture in sorted(fixtures, key=lambda item: item.fixture_id):
        digest.update(fixture.fixture_id.encode())
        digest.update(b"\0")
        digest.update(fixture.source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_claude_isolation(claude: str, model: str | None, timeout_seconds: int) -> None:
    """Prove the parent session authenticates and its subprocesses see no credentials.

    Claude keeps its provider variables so Bedrock, Vertex, Foundry, and API-key
    logins work, and relies on ``CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`` to strip them
    from every subprocess. This preflight refuses to run the suite unless a real
    Claude session starts and a hook subprocess of that session confirms each
    credential variable is absent. It records and reports variable names only.
    """

    with tempfile.TemporaryDirectory(prefix="sccfm-claude-preflight-") as temporary:
        root = Path(temporary)
        environment = isolated_environment(root, root / "bin", Scenario(), "claude")
        names = preserved_credential_names()
        settings, report = install_probe(root, names, isolation_settings(Path.home(), (root,)))
        command = [
            claude,
            "Reply with the single word ready.",
            "--print",
            "--output-format",
            "text",
            "--no-session-persistence",
            "--permission-mode",
            "default",
            "--restricted",
            "--tools",
            "Read",
            "--allowedTools",
            "Read",
            "--settings",
            str(settings),
        ]
        if model:
            command.extend(["--model", model])
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout_seconds,
                env=environment,
                cwd=root,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(
                "Claude did not start a session within "
                f"{timeout_seconds} seconds during the credential-isolation preflight"
            ) from None
        if completed.returncode != 0:
            diagnostic = redact(completed.stderr.strip() or completed.stdout.strip())
            raise ValueError(
                "Claude could not start a session in the harness environment. Confirm the "
                "provider login this shell uses works for a plain `claude --print` call. "
                f"Claude reported: {diagnostic[-500:]}"
            )
        completed_probe, visible = read_probe(report)
    if not completed_probe:
        raise ValueError(
            "the credential-isolation preflight probe did not run, so the harness cannot "
            "confirm that evaluated subprocesses are credential free; expected the "
            "SessionStart hook to execute"
        )
    if visible:
        raise ValueError(
            "Claude subprocesses can still read provider credentials "
            f"({', '.join(visible)}); the harness requires "
            f"{SCRUB_VARIABLE}=1 to remove them from Bash commands, hooks, and MCP "
            "servers. Upgrade the Claude CLI or unset those variables and use a login "
            "that does not rely on the environment."
        )


def _default_output_directory() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return REPOSITORY_ROOT / "agent-harness" / "results" / timestamp


def _command_version(command: list[str]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return completed.stdout.strip() or completed.stderr.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
