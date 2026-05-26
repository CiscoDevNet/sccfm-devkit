"""Test data for the access_rules/ e2e suite.

Mirrors ``sccfm-ansible/e2e/access_rules/playbooks/vars/test_data.yml``.
"""

from __future__ import annotations

# CI guarantees exactly one onboarded ASA matches this query during the
# test run. The device is deleted afterward.
ASA_TEST_QUERY = "name:ci-e2e-asa-* AND connectivityState:ONLINE"

TEST_ACL_NAME = "ci-e2e-test-acl"
ACCESS_GROUP_QUERY = f"name:{TEST_ACL_NAME}"

TEST_SOURCE_NETWORK = "ci-e2e-src-host"
TEST_SOURCE_VALUE = "198.51.100.1"
TEST_DESTINATION_NETWORK = "ci-e2e-dst-host"
TEST_DESTINATION_VALUE = "198.51.100.2"

TEST_RULE_INDEX = 1
TEST_RULE_ACTION = "PERMIT"
TEST_RULE_REMARK = "CI test rule - allow traffic"
UPDATED_RULE_REMARK = "CI test rule - allow traffic (updated)"

# CDO can take some time to index a freshly provisioned access group.
# Mirrors the 12 retries × 10s wait used by the Ansible suite's
# list_access_groups playbook.
LIST_ACCESS_GROUP_RETRIES = 12
LIST_ACCESS_GROUP_DELAY_SEC = 10
