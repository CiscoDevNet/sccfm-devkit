# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services.inventory.cdfmc_access_policy_service import (
    CdfmcAccessPolicyService,
    FmcAccessPolicy,
    FmcAccessPolicyPage,
)


def test_should_return_access_policies_as_json_with_pagination_options(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    captured_params: dict[str, Any] = {}

    def fake_init(self: CdfmcAccessPolicyService, config: Any) -> None:
        return None

    def fake_get_access_policies(
        self: CdfmcAccessPolicyService,
        domain_uid: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> FmcAccessPolicyPage:
        captured_params["domain_uid"] = domain_uid
        captured_params["limit"] = limit
        captured_params["offset"] = offset
        return FmcAccessPolicyPage(
            items=[FmcAccessPolicy(uid="policy-1", name="Default Access Policy")],
            count=10,
            limit=limit,
            offset=offset,
        )

    monkeypatch.setattr(CdfmcAccessPolicyService, "__init__", fake_init)
    monkeypatch.setattr(
        CdfmcAccessPolicyService,
        "get_access_policies",
        fake_get_access_policies,
    )

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "manager",
            "access-policies",
            "list",
            "--domain-uid",
            "domain-1",
            "--limit",
            "5",
            "--offset",
            "5",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured_params == {"domain_uid": "domain-1", "limit": 5, "offset": 5}
    assert json.loads(result.output) == [{"uid": "policy-1", "name": "Default Access Policy"}]


def test_should_display_access_policies_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    monkeypatch: MonkeyPatch,
) -> None:
    def fake_init(self: CdfmcAccessPolicyService, config: Any) -> None:
        return None

    def fake_get_access_policies(
        self: CdfmcAccessPolicyService,
        domain_uid: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> FmcAccessPolicyPage:
        return FmcAccessPolicyPage(
            items=[FmcAccessPolicy(uid="policy-1", name="Default Access Policy")],
            count=10,
            limit=limit,
            offset=offset,
        )

    monkeypatch.setattr(CdfmcAccessPolicyService, "__init__", fake_init)
    monkeypatch.setattr(
        CdfmcAccessPolicyService,
        "get_access_policies",
        fake_get_access_policies,
    )

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "manager",
            "access-policies",
            "list",
            "--domain-uid",
            "domain-1",
            "--offset",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "Number of entries:" in result.output
    assert "Page:" in result.output
    assert "FMC Access Policies" in result.output
    assert "Default Access Policy" in result.output
