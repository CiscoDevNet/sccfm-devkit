# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
name: profile
author: Cisco SCCFM Team (@CiscoDevNet)
version_added: "0.39.0"
short_description: Read a value from a configured SCCFM profile
description:
  - Reads a region or API token from the canonical SCCFM profile store.
  - Configure profiles with C(sccfm-cli configure) before using this lookup.
options:
  _terms:
    description: Profile names to read.
    required: true
  field:
    description: Profile field to return.
    choices: [region, api_token]
    default: api_token
  config_path:
    description: Optional path to the canonical SCCFM profile configuration file.
    type: path
"""

EXAMPLES = r"""
- name: Use a profile token in an API request
  ansible.builtin.uri:
    url: https://example.invalid/api
    headers:
      Authorization: "Bearer {{ lookup('cisco.sccfm.profile', 'default') }}"
  no_log: true
"""

RETURN = r"""
_raw:
  description: Values read from the selected SCCFM profiles.
  type: list
  elements: str
"""


from pathlib import Path
from typing import Any

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

try:
    from cisco_sccfm_core.services.profile_service import ProfileService
except ImportError as exc:
    _DEPENDENCY_IMPORT_ERROR: ImportError | None = exc
else:
    _DEPENDENCY_IMPORT_ERROR = None


class LookupModule(LookupBase):
    """Read fields from the canonical SCCFM profile store."""

    def run(
        self,
        terms: list[str],
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        if _DEPENDENCY_IMPORT_ERROR is not None:
            raise AnsibleError(
                "cisco-sccfm-devkit must be installed on the Ansible controller "
                "to use the cisco.sccfm.profile lookup"
            ) from _DEPENDENCY_IMPORT_ERROR

        self.set_options(var_options=variables, direct=kwargs)
        field = self.get_option("field")
        raw_path = self.get_option("config_path")
        service = ProfileService(path=Path(raw_path) if raw_path else None)

        values: list[str] = []
        for profile_name in terms:
            profile = service.load(profile_name)
            if profile is None:
                raise AnsibleError(
                    f"SCCFM profile '{profile_name}' not found. "
                    f"Run 'sccfm-cli --profile {profile_name} configure' to set it up."
                )
            values.append(profile.region if field == "region" else profile.api_token)
        return values
