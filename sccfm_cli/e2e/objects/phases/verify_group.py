"""List ci-test network groups and verify the test group appears."""

from __future__ import annotations

from sccfm_cli.e2e._profile import ProfileContext
from sccfm_cli.e2e._runner import get_json, run_cli
from sccfm_cli.e2e.objects.phases.test_data import TEST_GROUP_NAME, TEST_QUERY


def run(ctx: ProfileContext) -> None:
    result = run_cli(
        "objects",
        "network-group",
        "list",
        "--query",
        TEST_QUERY,
        "--limit",
        "50",
        "--format",
        "json",
        profile=ctx.profile,
        config_path=ctx.config_path,
    )
    payload = get_json(result)
    items = payload.get("items") or payload.get("network_groups") or []
    names = {item.get("name") for item in items}
    assert (
        TEST_GROUP_NAME in names
    ), f"Expected {TEST_GROUP_NAME!r} in group listing, got {sorted(names)!r}"
