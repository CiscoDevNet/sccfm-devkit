from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scc_firewall_manager_sdk.models.access_rule_create_input import AccessRuleCreateInput
from scc_firewall_manager_sdk.models.destination_network_content import DestinationNetworkContent
from scc_firewall_manager_sdk.models.destination_port_content import DestinationPortContent
from scc_firewall_manager_sdk.models.log_settings import LogSettings
from scc_firewall_manager_sdk.models.protocol_content import ProtocolContent
from scc_firewall_manager_sdk.models.source_network_content import SourceNetworkContent
from scc_firewall_manager_sdk.models.source_port_content import SourcePortContent

from sccfm_core.errors import NotFoundError
from sccfm_core.services.object_management import NetworkObjectService
from sccfm_core.services.policy.policy_api_helper import PolicyApiHelper
from sccfm_core.types import ConfigLike


@dataclass
class AccessRuleResponse:
    """Simplified response for access rule operations."""

    uid: str
    access_group_uid: str
    entity_uid: str
    index: int
    is_active_rule: bool | None
    rule_action: str | None
    rule_type: str | None
    remark: str | None
    source_network: dict[str, Any] | None
    destination_network: dict[str, Any] | None
    protocol: dict[str, Any] | None
    source_port: dict[str, Any] | None
    destination_port: dict[str, Any] | None
    log_settings: dict[str, Any] | None
    rule_configuration_text: str | None
    created_date: str | None
    updated_date: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccessRuleResponse:
        return cls(
            uid=str(data.get("uid") or ""),
            access_group_uid=str(data.get("accessGroupUid") or ""),
            entity_uid=str(data.get("entityUid") or ""),
            index=int(data.get("index", 0)),
            is_active_rule=data.get("isActiveRule"),
            rule_action=data.get("ruleAction"),
            rule_type=data.get("ruleType"),
            remark=data.get("remark"),
            source_network=data.get("sourceNetwork"),
            destination_network=data.get("destinationNetwork"),
            protocol=data.get("protocol"),
            source_port=data.get("sourcePort"),
            destination_port=data.get("destinationPort"),
            log_settings=data.get("logSettings"),
            rule_configuration_text=data.get("ruleConfigurationText"),
            created_date=data.get("createdDate"),
            updated_date=data.get("updatedDate"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "access_group_uid": self.access_group_uid,
            "entity_uid": self.entity_uid,
            "index": self.index,
            "is_active_rule": self.is_active_rule,
            "rule_action": self.rule_action,
            "rule_type": self.rule_type,
            "remark": self.remark,
            "source_network": self.source_network,
            "destination_network": self.destination_network,
            "protocol": self.protocol,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "log_settings": self.log_settings,
            "rule_configuration_text": self.rule_configuration_text,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
        }


class AccessRuleService:
    """Service for managing ASA access rules via the SCC Firewall Manager API."""

    def __init__(self, config: ConfigLike) -> None:
        self._helper = PolicyApiHelper(config)
        self._rules_api = self._helper.rules_api
        self._network_object_service = NetworkObjectService(config)

    def create_access_rule(
        self,
        *,
        access_group_uid: str,
        entity_uid: str,
        index: int,
        rule_action: str = "PERMIT",
        remark: str | None = None,
        source_network: str | None = None,
        destination_network: str | None = None,
        protocol: str | None = None,
        source_port: str | None = None,
        destination_port: str | None = None,
        log_level: str | None = None,
        log_interval: int | None = None,
        active: bool | None = None,
    ) -> AccessRuleResponse:
        """Create an access rule.

        Args:
            access_group_uid: UID of the access group to add the rule to.
            entity_uid: UID of the device/manager.
            index: Position of the rule in the ordered list.
            rule_action: PERMIT or DENY.
            remark: Human-readable description of the rule.
            source_network: Network object name for the source.
            destination_network: Network object name for the destination.
            protocol: Protocol name (e.g. "tcp", "udp", "ip").
            source_port: Source port or port range (e.g. "80", "1024-65535").
            destination_port: Destination port or port range.
            log_level: Log level string.
            log_interval: Log interval in seconds.
            active: Whether the rule is active.
        """
        create_input = AccessRuleCreateInput(
            access_group_uid=access_group_uid,
            entity_uid=entity_uid,
            index=index,
            rule_action=rule_action,
            remark=remark,
            source_network=self._resolve_source_network(source_network),
            destination_network=self._resolve_destination_network(destination_network),
            protocol=self._build_protocol(protocol),
            source_port=self._build_source_port(source_port),
            destination_port=self._build_destination_port(destination_port),
            log_settings=self._build_log_settings(log_level, log_interval),
            active_rule=active,
        )
        response = self._rules_api.create_access_rule_without_preload_content(
            access_rule_create_input=create_input
        )
        data = self._helper.read_raw_response(response)
        return AccessRuleResponse.from_dict(data)

    # -- network name → SDK content builders --

    def _resolve_network_object(self, name: str) -> tuple[str, str]:
        """Resolve a network object name to (uid, name) tuple."""
        obj = self._network_object_service.get_network_object_by_name(name)
        if not obj:
            raise NotFoundError(f"Network object '{name}' not found.")
        return obj.uid, obj.name

    def _resolve_source_network(self, name: str | None) -> SourceNetworkContent | None:
        if not name:
            return None
        obj_uid, obj_name = self._resolve_network_object(name)
        return SourceNetworkContent(name=obj_name, uid=obj_uid, type="NETWORK_OBJECT")

    def _resolve_destination_network(self, name: str | None) -> DestinationNetworkContent | None:
        if not name:
            return None
        obj_uid, obj_name = self._resolve_network_object(name)
        return DestinationNetworkContent(name=obj_name, uid=obj_uid, type="NETWORK_OBJECT")

    @staticmethod
    def _build_protocol(protocol: str | None) -> ProtocolContent | None:
        if not protocol:
            return None
        return ProtocolContent(name=protocol)

    @staticmethod
    def _build_source_port(port: str | None) -> SourcePortContent | None:
        if not port:
            return None
        return SourcePortContent(name=port)

    @staticmethod
    def _build_destination_port(port: str | None) -> DestinationPortContent | None:
        if not port:
            return None
        return DestinationPortContent(name=port)

    @staticmethod
    def _build_log_settings(level: str | None, interval: int | None) -> LogSettings | None:
        if level is None and interval is None:
            return None
        return LogSettings(level=level, interval=interval)
