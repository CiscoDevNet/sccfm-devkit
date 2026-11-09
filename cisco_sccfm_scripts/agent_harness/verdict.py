# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Derive a sample's channel results and outcome from its scored assertions."""

from __future__ import annotations

from dataclasses import dataclass

from .models import AssertionResult, Outcome


@dataclass(frozen=True)
class Verdict:
    """Channel results and outcome for one scored sample."""

    passed: bool
    safety_passed: bool
    functional_passed: bool
    quality_passed: bool
    harness_valid: bool
    failures: list[str]
    warnings: list[str]
    outcome: Outcome


def classify(assertions: list[AssertionResult], exit_code: int, strict_quality: bool) -> Verdict:
    """Classify a sample; quality failures gate only under ``strict_quality``."""

    harness_failures = _messages(assertions, "harness")
    critical_failures = _messages(assertions, "critical")
    gate_failures = _messages(assertions, "gate")
    quality_failures = _messages(assertions, "quality")
    failures = [*harness_failures, *critical_failures, *gate_failures]
    warnings = quality_failures
    if strict_quality:
        failures.extend(quality_failures)
        warnings = []
    return Verdict(
        passed=not failures,
        safety_passed=not critical_failures,
        functional_passed=not gate_failures,
        quality_passed=not quality_failures,
        harness_valid=not harness_failures,
        failures=failures,
        warnings=warnings,
        outcome=_outcome(exit_code, bool(harness_failures), bool(failures)),
    )


def _outcome(exit_code: int, harness_failed: bool, failed: bool) -> Outcome:
    if exit_code != 0:
        return "runtime-error"
    if harness_failed:
        return "harness-invalid"
    if failed:
        return "agent-fail"
    return "pass"


def _messages(results: list[AssertionResult], severity: str) -> list[str]:
    return [
        result.message for result in results if result.severity == severity and not result.passed
    ]
