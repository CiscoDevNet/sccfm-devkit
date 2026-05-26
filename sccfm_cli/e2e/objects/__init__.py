"""Shared phase tracker for the objects/ suite.

The network object and network group lifecycles span two test files but
share dependencies — `delete_group` depends on `create`, which is part
of the object lifecycle.  Keeping the tracker on the suite package
keeps both test files reading from the same state without cross-test
imports.
"""

from __future__ import annotations

from sccfm_cli.e2e._phases import PhaseTracker

TRACKER = PhaseTracker()
