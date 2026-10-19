# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from cisco_sccfm_core.constants import normalize_sccfm_region


@pytest.mark.parametrize(
    ("region", "expected"),
    [
        (None, None),
        (" US ", "us"),
        ("AUS", "au"),
        ("", ""),
    ],
)
def test_normalize_sccfm_region(region: str | None, expected: str | None) -> None:
    assert normalize_sccfm_region(region) == expected
