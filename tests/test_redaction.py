# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from cisco_sccfm_cli.utils import redact_data, redact_text


def test_redact_text_replaces_longest_sensitive_values_first() -> None:
    assert (
        redact_text(
            "long-secret and short",
            ("short", "long-secret", "secret", ""),
        )
        == "<redacted> and <redacted>"
    )


def test_redact_text_redacts_smart_license_tokens_without_known_values() -> None:
    assert (
        redact_text("LICENSE smart register IDTOKEN synthetic-token\nwrite memory")
        == "LICENSE smart register IDTOKEN <redacted>\nwrite memory"
    )


def test_redact_data_recurses_without_mutating_input() -> None:
    sentinel = "SEC004-NESTED-SENTINEL"
    payload = {
        f"key-{sentinel}": [
            f"value-{sentinel}",
            (f"tuple-{sentinel}", {f"set-{sentinel}"}),
        ],
        "unchanged": 42,
    }

    redacted = redact_data(payload, (sentinel,))

    assert sentinel in next(iter(payload))
    assert redacted == {
        "key-<redacted>": [
            "value-<redacted>",
            ("tuple-<redacted>", {"set-<redacted>"}),
        ],
        "unchanged": 42,
    }
