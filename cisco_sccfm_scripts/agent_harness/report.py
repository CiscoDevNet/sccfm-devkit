# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Machine-readable, Markdown, and browser-based harness reports."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence, cast

from .models import Fixture, SampleResult

DASHBOARD_TEMPLATE = Path(__file__).resolve().parents[2] / "agent-harness" / "dashboard.html"


def write_report(
    output_directory: Path,
    results: Sequence[SampleResult],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Write JSON, Markdown, and HTML reports and return the JSON payload."""

    output_directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 6,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "overall": _category(results, "passed"),
            "harness": _harness_category(results),
            "safety": _category(results, "safety_passed", valid_only=True),
            "functional": _category(results, "functional_passed", valid_only=True),
            "quality": _category(results, "quality_passed", valid_only=True),
            "quality_warnings": sum(len(result.warnings) for result in results),
        },
        "reliability": {
            "confidence_level": 0.95,
            "fixtures": _reliability(results),
        },
        "metadata": metadata,
        "results": [result.to_dict() for result in results],
    }
    (output_directory / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_directory / "results.md").write_text(_markdown(payload), encoding="utf-8")
    write_dashboard(output_directory / "results.html", payload)
    return payload


def write_dashboard(
    output_path: Path,
    payload: dict[str, Any],
    fixtures: Sequence[Fixture] = (),
) -> None:
    """Write a self-contained dashboard, enriching older reports from fixtures."""

    template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    dashboard_payload = _with_fixture_context(payload, fixtures)
    serialized = json.dumps(dashboard_payload, separators=(",", ":"), ensure_ascii=False)
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.replace("__SCCFM_HARNESS_DATA__", serialized), encoding="utf-8")


def compare_baseline(current: dict[str, Any], baseline_path: Path) -> list[str]:
    """Report fixture/mode gate pass-rate regressions from a prior JSON report."""

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    incompatibility = _baseline_incompatibility(current, baseline)
    if incompatibility is not None:
        return [incompatibility]
    before = _pass_rates(baseline)
    after = _pass_rates(current)
    regressions = []
    for key, prior_rate in before.items():
        current_rate = after.get(key)
        if current_rate is None:
            regressions.append(f"missing baseline case: {key}")
        elif current_rate < prior_rate:
            regressions.append(
                f"pass-rate regression for {key}: {prior_rate:.2f} -> {current_rate:.2f}"
            )
    return regressions


def _baseline_incompatibility(current: dict[str, Any], baseline: dict[str, Any]) -> str | None:
    current_fingerprint = current.get("metadata", {}).get("comparison_fingerprint")
    baseline_fingerprint = baseline.get("metadata", {}).get("comparison_fingerprint")
    if not isinstance(current_fingerprint, dict) or not isinstance(baseline_fingerprint, dict):
        return "baseline comparison requires matching comparison fingerprints; regenerate it"
    if current_fingerprint == baseline_fingerprint:
        return None
    changed = sorted(
        key
        for key in set(current_fingerprint) | set(baseline_fingerprint)
        if current_fingerprint.get(key) != baseline_fingerprint.get(key)
    )
    return "incompatible baseline fingerprint: " + ", ".join(changed)


def _category(
    results: Sequence[SampleResult], attribute: str, *, valid_only: bool = False
) -> dict[str, int]:
    selected = [result for result in results if result.harness_valid or not valid_only]
    passed = sum(bool(getattr(result, attribute)) for result in selected)
    return {"passed": passed, "failed": len(selected) - passed, "total": len(selected)}


def _harness_category(results: Sequence[SampleResult]) -> dict[str, int]:
    valid = sum(result.harness_valid for result in results)
    return {"valid": valid, "invalid": len(results) - valid, "total": len(results)}


def _reliability(results: Sequence[SampleResult]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], list[SampleResult]] = {}
    for result in results:
        buckets.setdefault((result.fixture_id, result.agent, result.mode), []).append(result)

    reliability = []
    for (fixture_id, agent, mode), attempts in sorted(buckets.items()):
        valid = [result for result in attempts if result.harness_valid]
        passed = sum(result.passed for result in valid)
        failed = len(valid) - passed
        lower, upper = _wilson_interval(passed, len(valid))
        reliability.append(
            {
                "fixture_id": fixture_id,
                "agent": agent,
                "mode": mode,
                "attempted": len(attempts),
                "valid": len(valid),
                "invalid": len(attempts) - len(valid),
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / len(valid) if valid else None,
                "confidence_lower": lower,
                "confidence_upper": upper,
                "flaky": passed > 0 and failed > 0,
            }
        )
    return reliability


def _wilson_interval(passed: int, total: int) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    z = 1.959963984540054
    proportion = passed / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _pass_rates(payload: dict[str, Any]) -> dict[str, float]:
    buckets: dict[str, list[bool]] = {}
    for result in payload.get("results", []):
        if result.get("harness_valid", True) is False:
            continue
        agent = result.get("agent", payload.get("metadata", {}).get("agent", "codex"))
        key = f"{result['fixture_id']}[{agent}/{result['mode']}]"
        buckets.setdefault(key, []).append(bool(result["passed"]))
    return {key: sum(values) / len(values) for key, values in buckets.items()}


def _with_fixture_context(payload: dict[str, Any], fixtures: Sequence[Fixture]) -> dict[str, Any]:
    fixture_map = {fixture.fixture_id: fixture for fixture in fixtures}
    enriched = cast(dict[str, Any], json.loads(json.dumps(payload)))
    for result in enriched.get("results", []):
        result.setdefault("agent", enriched.get("metadata", {}).get("agent", "codex"))
        fixture = fixture_map.get(result.get("fixture_id"))
        if fixture is None:
            continue
        result.setdefault("tier", fixture.tier)
        result.setdefault("skill", fixture.skill)
        result.setdefault("prompt", fixture.prompt)
        result.setdefault(
            "scenario",
            {
                "profile_state": fixture.scenario.profile_state,
                "region": fixture.scenario.region,
                "devices": list(fixture.scenario.devices),
                "schema_state": fixture.scenario.schema_state,
                "device_list_state": fixture.scenario.device_list_state,
                "ansible_playbook_state": fixture.scenario.ansible_playbook_state,
                "runtime_state": fixture.scenario.runtime_state,
                "ansible_runtime_layout": fixture.scenario.ansible_runtime_layout,
            },
        )
    return enriched


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    overall = summary["overall"]
    safety = summary["safety"]
    functional = summary["functional"]
    quality = summary["quality"]
    lines = [
        "# SCCFM agent harness results",
        "",
        f"Overall gate: **{overall['passed']} / {overall['total']} passed**",
        "",
        f"- Harness: **{summary.get('harness', {}).get('valid', overall['total'])} / "
        f"{summary.get('harness', {}).get('total', overall['total'])} valid samples**",
        f"- Safety: **{safety['passed']} / {safety['total']}**",
        f"- Functional: **{functional['passed']} / {functional['total']}**",
        f"- Quality: **{quality['passed']} / {quality['total']}** "
        f"({summary['quality_warnings']} warnings)",
        "",
        "| Fixture | Agent | Mode | Sample | Runtime tries | Outcome | Safety "
        "| Functional | Quality | Gate | Duration |",
        "|---|---|---|---:|---:|---|---|---|---|---|---:|",
    ]
    freshness = payload.get("metadata", {}).get("plugin_freshness")
    if isinstance(freshness, dict):
        lines[8:8] = [
            f"- Installed plugin: **{'CURRENT' if freshness.get('fresh') else 'STALE'}** "
            f"(`{freshness.get('version', 'unknown')}`)",
            "",
        ]
    for result in payload["results"]:
        lines.append(
            f"| {result['fixture_id']} | {result.get('agent', 'codex')} | "
            f"{result['mode']} | {result['sample']} | {result.get('runtime_attempts', 1)} | "
            f"{result.get('outcome', 'pass' if result['passed'] else 'agent-fail')} | "
            f"{_status(result['safety_passed'])} | {_status(result['functional_passed'])} | "
            f"{_status(result['quality_passed'])} | {_status(result['passed'])} | "
            f"{result['duration_seconds']:.3f}s |"
        )
        if result.get("prior_runtime_errors"):
            lines.extend(
                [
                    "",
                    *[
                        f"- **RECOVERED RUNTIME ERROR** `{result['fixture_id']}`: {item}"
                        for item in result["prior_runtime_errors"]
                    ],
                ]
            )
        if result["failures"]:
            lines.extend(
                [
                    "",
                    *[
                        f"- **FAIL** `{result['fixture_id']}`: {item}"
                        for item in result["failures"]
                    ],
                ]
            )
        if result["warnings"]:
            lines.extend(
                [
                    "",
                    *[
                        f"- **WARNING** `{result['fixture_id']}`: {item}"
                        for item in result["warnings"]
                    ],
                ]
            )
    reliability = payload.get("reliability", {}).get("fixtures", [])
    if reliability:
        lines.extend(
            [
                "",
                "## Reliability by fixture",
                "",
                "Invalid harness samples are excluded from pass rates and confidence intervals.",
                "",
                "| Fixture | Agent | Valid / attempted | Pass rate "
                "| 95% confidence interval | Flaky |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for item in reliability:
            rate = _percentage(item.get("pass_rate"))
            lower = _percentage(item.get("confidence_lower"))
            upper = _percentage(item.get("confidence_upper"))
            interval = f"{lower}–{upper}" if item.get("valid") else "n/a"
            lines.append(
                f"| {item['fixture_id']} | {item.get('agent', 'codex')} | "
                f"{item['valid']} / {item['attempted']} | "
                f"{rate} | {interval} | {'yes' if item['flaky'] else 'no'} |"
            )
    return "\n".join(lines) + "\n"


def _status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _percentage(value: object) -> str:
    return "n/a" if not isinstance(value, (int, float)) else f"{value * 100:.1f}%"
