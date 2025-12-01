from enum import Enum


class CdoTransactionStatus(str, Enum):
    """
    ConnectivityState
    """

    """
    allowed enum values
    """
    PENDING = ("PENDING",)
    IN_PROGRESS = ("IN_PROGRESS",)
    CANCELLED = ("CANCELLED",)
    DONE = ("DONE",)
    ERROR = "ERROR"
