# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

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
