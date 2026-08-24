# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Report optional runtime dependency imports after module argument parsing."""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from ansible.module_utils.basic import missing_required_lib

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule

_IMPORT_ERRORS: list[tuple[str, str]] = []
_PAIRED_DEVKIT_REQUIREMENT = "cisco-sccfm-devkit==0.39.4"


def record_import_error(error: ImportError) -> None:
    """Record an import failure without preventing Ansible from inspecting a module."""
    library = (error.name or "cisco-sccfm-devkit").split(".", maxsplit=1)[0]
    _IMPORT_ERRORS.append((library, traceback.format_exc()))


def ensure_required_dependencies(module: "AnsibleModule") -> None:
    """Fail with Ansible's actionable dependency message when an import failed."""
    if not _IMPORT_ERRORS:
        return

    import_traceback = _IMPORT_ERRORS[0][1]
    module.fail_json(
        msg=missing_required_lib(
            _PAIRED_DEVKIT_REQUIREMENT,
            reason="by this cisco.sccfm collection release",
        ),
        exception=import_traceback,
    )
