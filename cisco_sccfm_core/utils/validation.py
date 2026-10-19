# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

import re
import uuid
from typing import List

_ASA_IMAGE_PATH_RE = re.compile(r"^[A-Za-z0-9_-]+:/\S+$")


def validate_uids(uids: List[str]) -> None:
    """Validate that all UIDs are valid UUIDv4 format.

    Args:
        uids: List of UID strings to validate.

    Raises:
        ValueError: If any UID is not a valid UUIDv4.
    """
    invalid_uids = []
    for uid in uids:
        try:
            parsed = uuid.UUID(uid)
            if parsed.version != 4:
                invalid_uids.append(uid)
        except ValueError:
            invalid_uids.append(uid)
    if invalid_uids:
        raise ValueError(f"Invalid UUIDv4(s): {', '.join(invalid_uids)}")


def validate_asa_image_path(image_path: str) -> None:
    """Validate an ASA on-device image path.

    The path must include a device filesystem prefix such as ``disk0:/`` or
    ``boot:/``.
    """
    if not image_path.strip():
        raise ValueError("ASA image path cannot be empty.")
    if not _ASA_IMAGE_PATH_RE.match(image_path):
        raise ValueError(
            "ASA image path must be a full device path such as 'disk0:/asa9xxx.bin' "
            "or 'boot:/asa9xxx.bin'."
        )
