# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field

from scc_firewall_manager_sdk import FtdVersion


@dataclass(frozen=True)
class FtdGroupCompatibleVersions:
    """Compatible upgrade versions for a group of FTD devices.

    ``common_versions`` contains only versions whose ``software_version``
    appears in the compatible list of **every** device in the group.
    ``per_device`` maps each device UID to its own full list.
    ``skipped`` maps device UIDs that the API rejected to the error message.
    """

    per_device: dict[str, list[FtdVersion]] = field(default_factory=dict)
    common_versions: list[FtdVersion] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
