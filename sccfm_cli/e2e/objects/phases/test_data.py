"""Single source of truth for the objects/ suite test data.

Mirrors ``sccfm-ansible/e2e/objects/playbooks/vars/test_data.yml``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkObjectFixture:
    name: str
    value: str
    description: str


TEST_OBJECTS: tuple[NetworkObjectFixture, ...] = (
    NetworkObjectFixture(
        name="ci-test-host-01",
        value="10.99.1.100",
        description="CI test host object",
    ),
    NetworkObjectFixture(
        name="ci-test-subnet-01",
        value="10.99.2.0/24",
        description="CI test subnet object",
    ),
)

TEST_OBJECT_NAMES: tuple[str, ...] = tuple(obj.name for obj in TEST_OBJECTS)

OBJECT_LABELS: tuple[str, ...] = ("ci-test",)
OBJECT_TAGS: tuple[str, ...] = ("ci=integration",)

TEST_GROUP_NAME = "ci-test-group-01"
TEST_GROUP_LITERALS: tuple[str, ...] = ("10.99.3.1", "10.99.3.2")
TEST_GROUP_DESCRIPTION = "CI test network group"

UPDATED_HOST_VALUE = "10.99.1.200"
UPDATED_HOST_DESCRIPTION = "CI test host object - updated"
UPDATED_SUBNET_LABELS: tuple[str, ...] = ("ci-test", "monitored")

TEST_QUERY = "name:ci-test-*"
