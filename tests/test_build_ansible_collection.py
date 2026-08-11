# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from cisco_sccfm_scripts.build_ansible_collection import (
    CollectionBuildError,
    _sync_paired_python_requirement,
)


def test_sync_paired_python_requirement_writes_canonical_pair_pin(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# Runtime installed from the matching public wheel\n"
        "cisco-sccfm-devkit == 0.37.0  # paired release\n",
        encoding="utf-8",
    )

    _sync_paired_python_requirement(requirements, "0.38.0")

    assert requirements.read_text(encoding="utf-8") == (
        "# Runtime installed from the matching public wheel\n" "cisco-sccfm-devkit==0.38.0\n"
    )


@pytest.mark.parametrize(
    "content",
    [
        "example-package==1.0.0\n",
        "cisco-sccfm-devkit==0.37.0\ncisco-sccfm-devkit==0.38.0\n",
        "cisco-sccfm-devkit>=0.37.0\n",
        "cisco-sccfm-devkit==0.37.0; python_version >= '3.12'\n",
        "cisco-sccfm-devkit==0.37.0\nexample-package==1.0.0\n",
    ],
)
def test_sync_paired_python_requirement_rejects_ambiguous_contract(
    tmp_path: Path,
    content: str,
) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(content, encoding="utf-8")

    with pytest.raises(CollectionBuildError):
        _sync_paired_python_requirement(requirements, "0.38.0")

    assert requirements.read_text(encoding="utf-8") == content
