"""Top-level conftest for the sccfm-cli e2e suite.

Suite ordering mirrors ``sccfm-ansible/e2e/conftest.py`` because the
underlying constraint is identical: provisioning the test access group
on the ASA leaves the device NOT_SYNCED, blocking subsequent ASA-touching
tests.  Run ``objects`` and ``asa`` first, then ``access_rules``; ``ftd``
and anything else fall through to the end.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, Generator

import pytest

from sccfm_cli.e2e._profile import ProfileContext, bootstrap_profile

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
def e2e_profile(tmp_path_factory: pytest.TempPathFactory) -> Generator[ProfileContext, None, None]:
    """Decode the Ansible vault and write a fresh ``e2e`` profile.

    Session-scoped so all four suites share the same temp profile and
    state store.  The config holds the decrypted tenant API token, so the
    temp directory is removed eagerly on teardown rather than relying on
    ``tmp_path_factory`` retention (pytest keeps the last few runs by
    default, which would leave a live token on disk).  Tenant-side cleanup
    is each suite's ``cleanup`` phase.
    """
    config_dir: Path = tmp_path_factory.mktemp("sccfm-cli-e2e")
    ctx = bootstrap_profile(config_dir)
    try:
        yield ctx
    finally:
        ctx.state.clear()
        shutil.rmtree(config_dir, ignore_errors=True)
