from __future__ import annotations

import json
from io import StringIO

import pytest
from rich.console import Console
from scc_firewall_manager_sdk import CdoCliResult, Device

from sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import (
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
