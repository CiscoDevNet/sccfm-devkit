from typing import List

from scc_firewall_manager_sdk import CliCommandInput, CommandLineInterfaceApi

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike


class AsaCommandLineService:
    def __init__(self, config: ConfigLike) -> None:
        self.command_line_interface_api = CommandLineInterfaceApi(
            ApiClientFactory().build(config=config)
        )

    def execute_cli(self, device_uids: List[str], asa_commands: List[str]) -> None:
        script = "\n".join(asa_commands)
        self.command_line_interface_api.execute_cli_command(
            cli_command_input=CliCommandInput(deviceUids=device_uids, script=script)
        )
