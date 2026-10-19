# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from operations import fetch_object_by_identifier, run_delete_with_idempotency


@dataclass(frozen=True)
class _Entity:
    uid: str


def test_fetch_object_uses_keyword_only_name_lookup() -> None:
    requested_names: list[str] = []

    def list_objects(_query: str, _limit: int) -> Any:
        raise AssertionError("Unexpected list lookup")

    def lookup_by_name(*, name: str) -> _Entity | None:
        requested_names.append(name)
        return _Entity(uid="object-uid")

    result = fetch_object_by_identifier(
        uid=None,
        name="object-name",
        list_fn=list_objects,
        get_by_name_fn=lookup_by_name,
        entity_name="Network object",
    )

    assert result.uid == "object-uid"
    assert requested_names == ["object-name"]


@pytest.mark.parametrize(
    ("uid", "name"),
    [("object-uid", None), (None, "object-name")],
)
def test_delete_check_mode_uses_keyword_only_lookups(
    uid: str | None,
    name: str | None,
) -> None:
    module = MagicMock()
    module.check_mode = True
    module.exit_json.side_effect = SystemExit(0)
    module.fail_json.side_effect = AssertionError("Lookup failed")
    entity = _Entity(uid="object-uid")

    def delete_object(*, uid: str | None, name: str | None) -> str:
        raise AssertionError(f"Unexpected delete: uid={uid}, name={name}")

    def lookup_by_uid(*, uid: str) -> _Entity | None:
        assert uid == "object-uid"
        return entity

    def lookup_by_name(*, name: str) -> _Entity | None:
        assert name == "object-name"
        return entity

    with pytest.raises(SystemExit):
        run_delete_with_idempotency(
            module,
            delete_fn=delete_object,
            uid=uid,
            name=name,
            entity_name="Network object",
            get_by_uid_fn=lookup_by_uid,
            get_by_name_fn=lookup_by_name,
        )

    module.exit_json.assert_called_once_with(
        changed=True,
        msg=f"Would delete Network object '{uid or name}'.",
        deleted_uid="object-uid",
    )
    module.fail_json.assert_not_called()
