"""Update the test group to reference both test objects."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.objects.phases.test_data import TEST_GROUP_NAME, TEST_OBJECT_NAMES


def run(ctx: ProfileContext) -> None:
    args = ["objects", "network-group", "update", "--name", TEST_GROUP_NAME]
    for ref in TEST_OBJECT_NAMES:
        args += ["--referenced-object", ref]
    args += ["--format", "json"]

    result = run_cli(*args, profile=ctx.profile, config_path=ctx.config_path)
    payload = get_json(result)
    referenced_uids = payload.get("referenced_object_uids") or [
        obj.get("uid") for obj in payload.get("referenced_objects") or []
    ]
    referenced_uids = [uid for uid in referenced_uids if uid]
    assert len(referenced_uids) == len(
        TEST_OBJECT_NAMES
    ), f"Expected {len(TEST_OBJECT_NAMES)} referenced object UIDs, got {payload!r}"
