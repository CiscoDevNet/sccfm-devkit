# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Redact sensitive values before rendering CLI output."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

REDACTED_VALUE = "<redacted>"

_SMART_LICENSE_TOKEN = re.compile(
    r"(\blicense\s+smart\s+register\s+idtoken\s+)(?:\S+)",
    flags=re.IGNORECASE,
)


def redact_text(value: str, sensitive_values: Sequence[str] = ()) -> str:
    """Return text with exact secrets and Smart Licensing tokens redacted."""
    redacted = value
    for sensitive_value in _longest_first(sensitive_values):
        redacted = redacted.replace(sensitive_value, REDACTED_VALUE)
    return _SMART_LICENSE_TOKEN.sub(rf"\1{REDACTED_VALUE}", redacted)


def redact_data(value: Any, sensitive_values: Sequence[str] = ()) -> Any:
    """Recursively redact strings in JSON-like data without mutating the input."""
    if isinstance(value, str):
        return redact_text(value, sensitive_values)
    if isinstance(value, dict):
        return {
            redact_data(key, sensitive_values): redact_data(item, sensitive_values)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item, sensitive_values) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item, sensitive_values) for item in value)
    if isinstance(value, set):
        return {redact_data(item, sensitive_values) for item in value}
    if isinstance(value, frozenset):
        return frozenset(redact_data(item, sensitive_values) for item in value)
    return value


def _longest_first(sensitive_values: Sequence[str]) -> list[str]:
    return sorted({value for value in sensitive_values if value}, key=len, reverse=True)
