import uuid
from typing import List


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
