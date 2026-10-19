# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from io import StringIO

import pytest
from rich.console import Console
from scc_firewall_manager_sdk import CdoCliResult, Device

from cisco_sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import (
    render_cli_results,
)


def _sample_results() -> list[CdoCliResult]:
    return [
        CdoCliResult(
            uid="result-1",
            device_uid="uid-1",
            result="show version output",
            error_msg=None,
        ),
        CdoCliResult(
            uid="result-2",
            device_uid="uid-2",
            result="show inventory output",
            error_msg="timeout",
        ),
    ]


def _sample_uid_to_device() -> dict[str, Device]:
    return {
        "uid-1": Device(uid="uid-1", name="asa-1", deviceType="ASA"),
        "uid-2": Device(uid="uid-2", name="asa-2", deviceType="ASA"),
    }


def test_render_cli_results_json(capsys: pytest.CaptureFixture[str]) -> None:
    render_cli_results(
        console=Console(file=StringIO()),
        results=_sample_results(),
        uid_to_device=_sample_uid_to_device(),
        script="show version",
        output_format="json",
    )
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 2
    assert payload[0]["device_uid"] == "uid-1"
    assert payload[1]["error_msg"] == "timeout"


def test_render_cli_results_table() -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=120)
    render_cli_results(
        console=console,
        results=_sample_results(),
        uid_to_device=_sample_uid_to_device(),
        script="show version",
        output_format="table",
    )
    output = stream.getvalue()
    assert "Executed script: show version" in output
    assert "asa-1" in output
    assert "asa-2" in output
    assert "uid-1" in output
    assert "uid-2" in output
    assert "timeout" in output


@pytest.mark.parametrize("output_format", ["table", "json"])
def test_render_cli_results_redacts_sensitive_values(
    output_format: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "SEC004-SYNTHETIC-SENTINEL"
    result = CdoCliResult(
        uid="result-sensitive",
        device_uid="uid-1",
        script=f"license smart register idtoken {sentinel}",
        result=f"device echoed {sentinel}",
        error_msg=f"failed to apply {sentinel}",
    )
    stream = StringIO()

    render_cli_results(
        console=Console(file=stream, force_terminal=False, width=120),
        results=[result],
        uid_to_device=_sample_uid_to_device(),
        script=f"license smart register idtoken {sentinel}",
        output_format=output_format,
        sensitive_values=(sentinel,),
    )

    output = capsys.readouterr().out if output_format == "json" else stream.getvalue()
    _assert_not_exposed(output, sentinel)
    assert "<redacted>" in output

    if output_format == "json":
        payload = json.loads(output)
        assert payload[0]["script"] == "license smart register idtoken <redacted>"
        assert payload[0]["result"] == "device echoed <redacted>"
        assert payload[0]["error_msg"] == "failed to apply <redacted>"


@pytest.mark.parametrize("output_format", ["table", "json"])
def test_render_cli_results_defensively_redacts_smart_license_token(
    output_format: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "UNREGISTERED-SMART-LICENSE-TOKEN"
    result = CdoCliResult(
        uid="result-sensitive",
        device_uid="uid-1",
        script=f"LICENSE SMART REGISTER IDTOKEN {sentinel}",
        result=f"license smart register idtoken {sentinel}",
        error_msg=None,
    )
    stream = StringIO()

    render_cli_results(
        console=Console(file=stream, force_terminal=False, width=120),
        results=[result],
        uid_to_device=_sample_uid_to_device(),
        script=f"license  smart register idtoken\t{sentinel}",
        output_format=output_format,
    )

    output = capsys.readouterr().out if output_format == "json" else stream.getvalue()
    _assert_not_exposed(output, sentinel)
    assert "<redacted>" in output


def _assert_not_exposed(output: str, sensitive_value: str) -> None:
    if sensitive_value in output:
        pytest.fail("Sensitive value was exposed in rendered output.", pytrace=False)
