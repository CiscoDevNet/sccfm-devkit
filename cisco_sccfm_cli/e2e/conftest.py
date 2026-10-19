# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Top-level conftest for the sccfm-cli e2e suite.

Suite ordering mirrors ``sccfm-ansible/e2e/conftest.py`` because the
underlying constraint is identical: provisioning the test access group
on the ASA leaves the device NOT_SYNCED, blocking subsequent ASA-touching
tests.  Run ``objects`` and ``asa`` first, then ``access_rules``; ``ftd``
and anything else fall through to the end.
"""

from __future__ import annotations

from typing import Final, Generator

import pytest

from cisco_sccfm_cli.e2e._profile import ProfileContext, resolve_profile

_SUITE_ORDER: Final[tuple[str, ...]] = (
    "objects",
    "asa",
    "access_rules",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    def _suite_key(index_item: tuple[int, pytest.Item]) -> tuple[int, int]:
        index, item = index_item
        parts = item.nodeid.split("/")
        for i, part in enumerate(parts):
            if part == "e2e" and i + 1 < len(parts):
                suite = parts[i + 1]
                try:
                    return (_SUITE_ORDER.index(suite), index)
                except ValueError:
                    break
        return (len(_SUITE_ORDER), index)

    items[:] = [item for _, item in sorted(enumerate(items), key=_suite_key)]


@pytest.fixture(scope="session")
def e2e_profile() -> Generator[ProfileContext, None, None]:
    """Use the canonical configured profile for all e2e suites."""
    ctx = resolve_profile()
    try:
        yield ctx
    finally:
        ctx.state.clear()
