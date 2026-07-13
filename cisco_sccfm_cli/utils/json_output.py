# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CLI JSON output contract.

This module is the single emit point for machine-readable JSON output produced
by the CLI. Commands MUST go through `print_json` instead of calling
`json.dumps` and `print`/`console.print` directly so that:

- output goes to plain stdout, not through Rich (no ANSI colors, no soft wrap,
  no width-driven re-flow that would corrupt JSON for downstream tools)
- options like `--silent` cannot accidentally suppress JSON payloads
- non-ASCII characters and non-trivially-serializable values (e.g. datetime,
  UUID) are handled the same way everywhere
"""

from __future__ import annotations

import json
from typing import Any


def json_text(payload: Any) -> str:
    """Return `payload` using the canonical CLI JSON serialization contract."""
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def print_json(payload: Any) -> None:
    """Emit `payload` as the canonical CLI JSON output.

    Always writes to stdout (not Rich) with `indent=2`, `ensure_ascii=False`,
    and `default=str` so callers can pass dicts, lists, dataclasses, or any
    payload that contains datetimes/UUIDs without further conversion.
    """
    print(json_text(payload))
