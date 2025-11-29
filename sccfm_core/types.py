from __future__ import annotations

from typing import Protocol


class ConfigLike(Protocol):
    @property
    def region(self) -> str: ...

    @property
    def api_token(self) -> str: ...
