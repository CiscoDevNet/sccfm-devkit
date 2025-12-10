import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, cast

import click
from rich.console import Console
from rich.table import Table
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device, DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.utils import with_spinner
from sccfm_core import AsaCommandLineService, InventoryService
from sccfm_core.types import ConfigLike


class AsaExecuteCliCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "execute"

    @property
    def help_text(self) -> str:
        return "Execute CLI commands on ASA devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["-q", "--query"],
                help="Filter devices to execute the CLI on by a Lucene query.",
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
                help="List of device UIDs to execute the CLI on.",
                multiple=True,
                type=str,
            ),
            click.Option(
                ["-s", "--script"],
                help="ASA commands to execute, with each command separated by \\n.",
            ),
            click.Option(
                ["-f", "--script-file"],
                type=click.Path(path_type=Path, resolve_path=True),
                help=(
                    "Path to a file containing ASA commands to execute, with each command "
                    "separated by a newline."
                ),
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
        ]

    @with_spinner("Executing CLI commands...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        query = cast(str | None, kwargs.get("query"))
        device_uids_param = cast(tuple[str, ...] | None, kwargs.get("device_uids"))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        script = cast(str | None, kwargs.get("script"))
        script_file = cast(Path | None, kwargs.get("script_file"))
        response_format = cast(str, kwargs.get("format"))

        self._validate_filters(
            ctx,
            query=query,
            device_uids=device_uids_param,
            script=script,
            script_file=script_file,
        )
        if script_file is not None:
            script = script_file.read_text()
        config = self.get_profile(ctx=ctx, **kwargs)
        if not config:
            warning = "[yellow]Profile not found. Run 'sccfm-cli --profile " "configure'.[/yellow]"
            self.console.print(warning)
            return
        config_like = cast(ConfigLike, cast(object, config))
        devices: List[Device] = self._get_devices(
            config=config_like,
            query=query,
            device_uids=device_uids_param,
            limit=limit,
            offset=offset,
        )
        uid_to_device: Dict[str, Device] = {device.uid: device for device in devices}
        device_uids: List[str] = [device.uid for device in devices]
        asa_cli_service = AsaCommandLineService(config=config_like)
        results: CdoTransaction | List[CdoCliResult] = asa_cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=script.split("\n"),  # type: ignore[union-attr]
        )
        self._render_results(
            results=results,
            uid_to_device=uid_to_device,
            script=script,
            format=response_format,
        )

    def _render_results(
        self,
        results: List[CdoCliResult] | CdoTransaction,
        uid_to_device: Dict[str, Device],
        script: str,
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        if format == "json":
            self._render_json(results=results)
        else:
            self._render_table(results=results, uid_to_device=uid_to_device, script=script)

    def _render_json(self, results: List[CdoCliResult]) -> None:
        results_data = [item.model_dump(mode="json") for item in results]
        json_output = json.dumps(results_data, indent=2, ensure_ascii=False)
        # Use print() instead of console.print() to avoid Rich processing escape sequences
        print(json_output)

    def _render_table(
        self, results: List[CdoCliResult], uid_to_device: Dict[str, Device], script: str
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
        config: ConfigLike,
        query: str | None,
        device_uids: tuple[str, ...] | None,
        limit: int,
        offset: int,
    ) -> List[Device]:
        inventory_service = InventoryService(config=config)
        if query:
            page: DevicePage = inventory_service.get_devices(
                limit=limit,
                offset=offset,
                query=f"{query} AND deviceType:ASA",
            )
            return cast(List[Device], page.items)

        query = " OR ".join([f"uid:{uid}" for uid in cast(tuple[str, ...], device_uids)])
        page = inventory_service.get_devices(limit=limit, offset=offset, query=query)
        return cast(List[Device], page.items)

    def _validate_filters(
        self,
        ctx: click.Context,
        *,
        query: str | None,
        device_uids: tuple[str, ...] | None,
        script: str | None,
        script_file: Path | None,
    ) -> None:
        has_query = bool(query)
        has_uids = bool(device_uids)
        if has_query == has_uids:
            ctx.fail("Provide exactly one of --query or --device-uids.")

        has_script = bool(script)
        has_script_file = bool(script_file)
        if has_script == has_script_file:
            ctx.fail("Provide exactly one of --script or --script-file.")
