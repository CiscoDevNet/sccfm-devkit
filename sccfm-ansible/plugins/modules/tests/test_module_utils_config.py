# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from config import Config


def test_config_should_normalize_region_case_and_legacy_aliases() -> None:
    config = Config(region="AUS", api_token="token-xyz")

    assert config.region == "au"


def test_config_should_reject_unknown_regions() -> None:
    with pytest.raises(ValueError, match="SCCFM region must be one of"):
        Config(region="mars", api_token="token-xyz")
