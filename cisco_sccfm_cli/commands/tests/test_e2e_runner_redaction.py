# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the e2e runner's secret-redaction helpers.

The FTD registration phases hand the runner a one-time CLI key; these tests lock
in that the key never leaks into argv, captured output, the result repr, or JSON
field values that a command might echo back.
"""

from __future__ import annotations

from cisco_sccfm_cli.e2e._runner import (
    CLIResult,
    _json_field_secrets,
    _redact_args,
    _redact_json_fields,
    _redact_payload,
    _redact_text,
)

_SECRET = "configure manager add fmc.example regkey natid"


def test_redact_args_masks_sensitive_flag_value() -> None:
    args = ["sccfm-cli", "configure-manager", "--cli-key", _SECRET, "--ftd-host", "10.10.3.101"]
    assert _redact_args(args, ()) == (
        "sccfm-cli",
        "configure-manager",
        "--cli-key",
        "<redacted>",
        "--ftd-host",
        "10.10.3.101",
    )


def test_redact_args_masks_explicit_value_anywhere() -> None:
    # Even a secret that is not preceded by a known flag is masked when named.
    args = ["sccfm-cli", "--something", _SECRET]
    assert _redact_args(args, (_SECRET,)) == ("sccfm-cli", "--something", "<redacted>")


def test_redact_text_replaces_all_occurrences() -> None:
    text = f"first {_SECRET} then {_SECRET} again"
    assert _SECRET not in _redact_text(text, (_SECRET,))


def test_redact_json_fields_masks_named_field() -> None:
    raw = f'{{"cli_key": "{_SECRET}", "host": "10.10.3.101"}}'
    redacted = _redact_json_fields(raw, ("cli_key",))
    assert _SECRET not in redacted
    assert '"host": "10.10.3.101"' in redacted


def test_json_field_secrets_finds_nested_values() -> None:
    payload = {"outer": {"cli_key": _SECRET}, "list": [{"cli_key": "other"}]}
    secrets = _json_field_secrets(payload, frozenset({"cli_key"}))
    assert set(secrets) == {_SECRET, "other"}


def test_redact_payload_scrubs_string_values() -> None:
    payload = {"cli_key": _SECRET, "nested": [_SECRET, "safe"]}
    redacted = _redact_payload(payload, (_SECRET,))
    assert redacted == {"cli_key": "<redacted>", "nested": ["<redacted>", "safe"]}


def test_cliresult_repr_excludes_json() -> None:
    result = CLIResult(
        args=("sccfm-cli",),
        returncode=0,
        stdout="ok",
        stderr="",
        json={"cli_key": _SECRET},
    )
    # json is repr=False, so a pytest failure dump of the result cannot leak it.
    assert _SECRET not in repr(result)
    assert result.json == {"cli_key": _SECRET}
