# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass

import pytest
from rich.console import Console

from cisco_sccfm_cli.commands.objects.utils import check_object_exists


@dataclass(frozen=True)
class _Entity:
    uid: str
    name: str


@pytest.mark.parametrize(
    ("uid", "name"),
    [("object-uid", None), (None, "object-name")],
)
def test_check_object_exists_uses_keyword_only_lookups(
    uid: str | None,
    name: str | None,
) -> None:
    entity = _Entity(uid="object-uid", name="object-name")

    def lookup_by_uid(*, uid: str) -> _Entity | None:
        assert uid == "object-uid"
        return entity

    def lookup_by_name(*, name: str) -> _Entity | None:
        assert name == "object-name"
        return entity

    result = check_object_exists(
        console=Console(),
        uid=uid,
        name=name,
        get_by_uid_fn=lookup_by_uid,
        get_by_name_fn=lookup_by_name,
        object_name="Network object",
        emit=False,
    )

    assert result == {
        "entity_type": "Network object",
        "identifier": uid or name,
        "operation": "update",
        "exists": True,
        "can_proceed": True,
        "reason": "exists",
        "uid": "object-uid",
        "name": "object-name",
    }
