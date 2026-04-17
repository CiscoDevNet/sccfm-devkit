"""Top-level conftest for E2E suite ordering.

Suites that modify the ASA config (e.g. access_rules provisions an ACL via
CLI) can leave the device in a non-SYNCED state.  Run those suites **after**
suites that depend on a synced device (asa, objects).
"""

from __future__ import annotations

from typing import Final

import pytest

# Suites are executed in this order.  Any suite not listed here runs last.
_SUITE_ORDER: Final[tuple[str, ...]] = (
    "objects",
    "asa",
    "access_rules",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Sort collected tests so suites run in the order defined above.

    Within each suite the original collection order (declaration order in
    the test file) is preserved.
    """

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
