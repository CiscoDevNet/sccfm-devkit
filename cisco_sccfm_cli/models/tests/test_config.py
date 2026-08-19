# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from cisco_sccfm_cli.models import Config


def test_config_repr_should_not_expose_api_token() -> None:
    api_token = "sec005-repr-token-8c0d3"
    config = Config(profile="default", region="us", api_token=api_token)

    representation = repr(config)

    if api_token in representation:
        raise AssertionError("Config repr exposed its API token")
    assert representation == "Profile(profile='default', region='us')"
