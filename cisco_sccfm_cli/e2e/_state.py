# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cross-phase data store for the sccfm-cli e2e suite.

Replaces the ``/tmp/ci_*_uid`` files used by the Ansible suite: a phase
that creates a resource stashes its UID via ``state.set("rule_uid", ...)``
and later phases read it back.  State is process-local and cleared at
session start so a previous run's stale UID can never leak into a fresh
session.
"""

from __future__ import annotations

from typing import Any


class PhaseStateStore:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str) -> Any:
        if key not in self._data:
            raise KeyError(f"phase state missing key: {key!r}")
        return self._data[key]

    def pop(self, key: str, default: Any = None) -> Any:
        return self._data.pop(key, default)

    def clear(self) -> None:
        self._data.clear()
