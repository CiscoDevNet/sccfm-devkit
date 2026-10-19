# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Test data for the access_rules/ e2e suite.

Mirrors ``sccfm-ansible/e2e/access_rules/playbooks/vars/test_data.yml``.
"""

from __future__ import annotations

import os

# CI guarantees exactly one onboarded ASA matches this query during the
# test run. The device is deleted afterward.
#
# Defaults to a CLI-dedicated vASA prefix so this suite doesn't share a
# device with the Ansible suite (which would leave the device NOT_SYNCED
# and block our ASA CLI script pushes).  Override via SCCFM_E2E_ASA_QUERY.
_DEFAULT_ASA_NAME_PREFIX = os.environ.get("SCCFM_E2E_ASA_NAME_PREFIX", "ci-e2e-cli-asa-")
ASA_TEST_QUERY = os.environ.get(
    "SCCFM_E2E_ASA_QUERY",
    f"name:{_DEFAULT_ASA_NAME_PREFIX}* AND connectivityState:ONLINE",
)

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
