# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Command-line interface for local and CI agent evaluations."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence, cast

from .fixtures import load_fixtures
from .models import Fixture, Mode
from .plugin_state import (
    PLUGIN_ID,
    inspect_plugin_freshness,
    refresh_local_plugin,
)
from .report import compare_baseline, write_dashboard, write_report
from .runner import build_codex_command, run_sample

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
        description="Evaluate SCCFM Codex skills against deterministic command doubles.",
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
    run.add_argument("--samples", type=int, default=1)
    run.add_argument("--model")
    run.add_argument("--timeout", type=int, default=300)
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
    mode = cast(Mode, options.mode)
    fixtures = _select_fixtures(
        load_fixtures(Path(options.fixtures)), options.fixture_ids, options.tier, mode
    )
    if not fixtures:
        raise ValueError("no fixtures matched the selection")
    codex = shutil.which("codex")
    if codex is None:
        raise ValueError("codex executable is not on PATH")
    if options.refresh_installed_plugin and mode != "installed-plugin":
        raise ValueError("--refresh-installed-plugin requires --mode installed-plugin")
    plugin_freshness = None
    if mode == "installed-plugin":
        plugin_payload = _plugin_list_payload(codex)
        plugin_freshness = inspect_plugin_freshness(plugin_payload, REPOSITORY_ROOT)
        if not plugin_freshness.fresh and options.refresh_installed_plugin:
            refresh_local_plugin(codex, REPOSITORY_ROOT, plugin_payload)
            plugin_payload = _plugin_list_payload(codex)
            plugin_freshness = inspect_plugin_freshness(plugin_payload, REPOSITORY_ROOT)
        if not plugin_freshness.fresh:
            raise ValueError(
                f"installed {PLUGIN_ID} is stale: {plugin_freshness.reason}; rerun with "
                "--refresh-installed-plugin to update this confirmed local installation"
            )

    if options.dry_run:
        workspace = Path("/tmp/sccfm-agent-harness-WORKSPACE")
        for fixture in fixtures:
            command = build_codex_command(
                fixture,
                mode,
                workspace,
                REPOSITORY_ROOT,
                options.model,
                options.bypass_hook_trust,
            )
            print(f"{fixture.fixture_id}: {json.dumps(command)}")
        return 0

    results = []
    for fixture in fixtures:
        for sample in range(1, options.samples + 1):
            print(f"running {fixture.fixture_id} [{mode}] sample {sample}/{options.samples}")
            result = run_sample(
                fixture,
                mode,
                sample,
                REPOSITORY_ROOT,
                options.model,
                options.timeout,
                options.bypass_hook_trust,
                options.strict_quality,
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
    payload = write_report(
        output_directory,
        results,
        {
            "mode": mode,
            "model": options.model or "configured default",
            "codex_version": _command_version([codex, "--version"]),
            "plugin_id": "sccfm@sccfm-devkit" if mode == "installed-plugin" else None,
            "plugin_freshness": (
                plugin_freshness.to_dict() if plugin_freshness is not None else None
            ),
            "samples": options.samples,
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


def _default_output_directory() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return REPOSITORY_ROOT / "agent-harness" / "results" / timestamp


def _command_version(command: list[str]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return completed.stdout.strip() or completed.stderr.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
