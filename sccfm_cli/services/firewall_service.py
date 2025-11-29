from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FirewallRecord:
    name: str
    status: str
    rules: int


class FirewallService:
    def list_firewalls(self) -> List[FirewallRecord]:
        return [
            FirewallRecord(name="perimeter-fw", status="active", rules=128),
            FirewallRecord(name="edge-nva", status="active", rules=74),
            FirewallRecord(name="lab-fw", status="maintenance", rules=12),
        ]
