import json
from pathlib import Path
from typing import Any, Dict, Final, List, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device, DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.utils import with_spinner
from sccfm_core import AsaCommandLineService, InventoryService
from sccfm_core.types import ConfigLike


class SmartlicenseCommand(BaseCommand):
    _ASAV_SMART_LICENSE_SCRIPT: Final[str] = (
        "license smart\n"
        "feature tier {feature_tier}\n"
        "throughput level {throughput_level}\n"
        "license smart register idtoken {token}\n"
        "write memory"
    )
    _HARDWARE_ASA_SMART_LICENSE_SCRIPT: Final[str] = (
        "license smart\n"
        "feature tier {feature_tier}\n"
        "license smart register idtoken {token}\n"
        "write memory"
    )

    @property
    def name(self) -> str:
        return "smartlicense"

    @property
    def help_text(self) -> str:
        return (
            "Apply Smart License using a Smart license token on ASA devices (the token must be"
            " valid and must have at least as many uses as there are devices)."
        )

    @with_spinner("Applying Smart Licenses...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        query = cast(str | None, kwargs.get("query"))
        device_uids_param = cast(tuple[str, ...] | None, kwargs.get("device_uids"))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        token = cast(str, kwargs.get("token"))
        feature_tier = cast(str, kwargs.get("feature_tier"))
        throughput_level = cast(str | None, kwargs.get("throughput_level"))
        response_format = cast(str, kwargs.get("format"))

        self._validate_filters(ctx, query=query, device_uids=device_uids_param)

        config = self.get_profile(ctx=ctx, **kwargs)
        devices = self._get_devices(
            ctx=ctx,
            config=config,
            query=query,
            device_uids=device_uids_param,
            limit=limit,
            offset=offset,
            must_be_virtual=throughput_level is not None,
        )

        devices = self.filter_online_devices(devices)
        script_commands = self._build_script(feature_tier, throughput_level, token)
        uid_to_device: Dict[str, Device] = {device.uid: device for device in devices}
        device_uids: List[str] = [device.uid for device in devices]

        asa_cli_service = AsaCommandLineService(config=config)
        results = asa_cli_service.execute_cli(device_uids=device_uids, asa_commands=script_commands)

        self._render_results(
            results=results,
            uid_to_device=uid_to_device,
            script_text="\n".join(script_commands),
            format=response_format,
        )

    def _build_script(
        self, feature_tier: str, throughput_level: str | None, token: str
    ) -> list[str]:
        if throughput_level is not None:
            script = self._ASAV_SMART_LICENSE_SCRIPT.format(
                feature_tier=feature_tier, throughput_level=throughput_level, token=token
            )
        else:
            script = self._HARDWARE_ASA_SMART_LICENSE_SCRIPT.format(
                feature_tier=feature_tier, token=token
            )
        return script.split("\n")

    def _render_results(
        self,
        results: list[CdoCliResult] | CdoTransaction,
        uid_to_device: dict[str, Device],
        script_text: str,
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        if format == "json":
            self._render_json(results=results)
        else:
            self._render_table(results=results, uid_to_device=uid_to_device, script=script_text)

    def _render_json(self, results: list[CdoCliResult]) -> None:
        results_data = [item.model_dump(mode="json") for item in results]
        json_output = json.dumps(results_data, indent=2, ensure_ascii=False)
        # Use print() instead of console.print() to avoid Rich processing escape sequences
        print(json_output)

    def _render_table(
        self, results: list[CdoCliResult], uid_to_device: dict[str, Device], script: str
    ) -> None:
        self.console.print(f"Executed script: {script}")
        table = Table(show_lines=True)
        table.add_column("Name")
        table.add_column("UID")
        table.add_column("Result")
        table.add_column("Error Message")
        for item in results:
            table.add_row(
                uid_to_device[item.device_uid].name,
                item.device_uid,
                item.result,
                item.error_msg or "-",
            )

        self.console.print(table)

    def _get_devices(
        self,
        ctx: click.Context,
        config: ConfigLike,
        query: str | None,
        device_uids: tuple[str, ...] | None,
        limit: int,
        offset: int,
        must_be_virtual: bool = False,
    ) -> list[Device]:
        inventory_service = InventoryService(config=config)
        if query:
            page: DevicePage = inventory_service.get_devices(
                limit=limit, offset=offset, query=f"{query} AND deviceType:ASA"
            )
            devices = cast(list[Device], page.items)
        else:
            query = " OR ".join([f"uid:{uid}" for uid in cast(tuple[str, ...], device_uids)])
            page = inventory_service.get_devices(limit=limit, offset=offset, query=query)
            devices = cast(list[Device], page.items)

        if must_be_virtual:
            non_virtual = [
                device
                for device in devices
                if not device.hardware_model or "ASAv" not in device.hardware_model
            ]
            if non_virtual:
                device_names = ", ".join([d.name for d in non_virtual])
                ctx.fail(
                    f"The following devices are not virtual ASAs: {device_names}. "
                    "If throughput level is specified, all of the ASAs selected have to be virtual"
                    " ASA devices."
                )

        return devices

    def _validate_filters(
        self,
        ctx: click.Context,
        *,
        query: str | None,
        device_uids: tuple[str, ...] | None,
    ) -> None:
        has_query = bool(query)
        has_uids = bool(device_uids)
        if has_query == has_uids:
            ctx.fail("Provide exactly one of --query or --device-uids.")

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["-q", "--query"],
                help="Filter devices to smart license  by a Lucene query.",
            ),
            click.Option(
                ["-l", "--limit"],
                default=50,
                show_default=True,
                type=click.IntRange(min=1, max=200),
                help="Maximum records to return (ignored if --query is not used)",
            ),
            click.Option(
                ["-o", "--offset"],
                default=0,
                show_default=True,
                type=click.IntRange(min=0),
                help="Pagination offset (ignored if --query is not used)",
            ),
            click.Option(
                ["-u", "--device-uids"],
                help="List of device UIDs to apply smart license to.",
                multiple=True,
                type=str,
            ),
            click.Option(
                ["--format"],
                type=click.Choice(["table", "json"], case_sensitive=False),
                default="table",
                show_default=True,
                help="Output format",
            ),
            click.Option(
                ["--config-path"],
                type=click.Path(path_type=Path, resolve_path=True),
                default=None,
                envvar="SCCFM_CONFIG",
                show_default=False,
                help="Path to the configuration file (defaults to ~/.sccfm-cli/config.json).",
            ),
            click.Option(
                ["--token", "-t"],
                type=str,
                required=True,
                help="The smart license token for your virtual account, generated on "
                "https://software.cisco.com/clc",
            ),
            click.Option(
                ["--throughput-level"],
                type=click.Choice(["100M", "1G"], case_sensitive=True),
                required=False,
                help="The throughput level of your ASA (required only for virtual ASAs)",
            ),
            click.Option(
                ["--feature-tier"],
                type=click.Choice(["standard"], case_sensitive=True),
                required=True,
                help="The feature tier of your ASA",
            ),
        ]
