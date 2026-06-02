# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for the network object/group e2e suite."""

from __future__ import annotations

from typing import Generator

import pytest

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e.objects.phases import cleanup as cleanup_phase


@pytest.fixture(scope="session", autouse=True)
def lifecycle_cleanup(e2e_profile: ProfileContext) -> Generator[None, None, None]:
    """Pre-clean before tests, and always clean up after — even on failure."""
    try:
        cleanup_phase.run(e2e_profile)
    except AssertionError as exc:
        pytest.exit(f"Pre-test cleanup failed, aborting suite: {exc}", returncode=1)
    yield
    cleanup_phase.run(e2e_profile)
