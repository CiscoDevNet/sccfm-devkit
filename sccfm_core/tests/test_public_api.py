# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the public sccfm_core package surface."""

from __future__ import annotations

from pathlib import Path

import sccfm_core


def test_public_exports_are_importable() -> None:
    """The documented public API should be exported from the package root."""
    expected_exports = {
        "AccessGroupService",
        "AccessRuleService",
        "ApiClientFactory",
        "HealthService",
        "InventoryService",
        "NetworkGroupService",
        "NetworkObjectService",
        "ObjectOverrideService",
        "SccApiError",
    }

    assert expected_exports <= set(sccfm_core.__all__)
    for export_name in expected_exports:
        assert getattr(sccfm_core, export_name) is not None


def test_package_is_marked_as_typed() -> None:
    """The PyPI package should expose type hints to downstream users."""
    package_root = Path(sccfm_core.__file__).parent

    assert (package_root / "py.typed").is_file()
