from typing import List

from scc_firewall_manager_sdk import (
    CdoCliResult,
    CdoTransaction,
    CliCommandInput,
    CommandLineInterfaceApi,
)

from sccfm_core.factories import ApiClientFactory
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.services.transaction_service import TransactionService
from sccfm_core.types import ConfigLike
from sccfm_core.utils import validate_uids


class AsaCommandLineService:
    def __init__(self, config: ConfigLike) -> None:
        self.command_line_interface_api = CommandLineInterfaceApi(
            ApiClientFactory().build(config=config)
        )
        self.transaction_service = TransactionService(config=config)

    def execute_cli(
        self,
        device_uids: List[str],
        asa_commands: List[str],
        *,
        wait: bool = True,
    ) -> CdoTransaction | List[CdoCliResult]:
        validate_uids(device_uids)
        script = "\n".join(asa_commands)
        transaction: CdoTransaction = self.command_line_interface_api.execute_cli_command(
            cli_command_input=CliCommandInput(deviceUids=device_uids, script=script)
        )
        if transaction.transaction_uid is None:
            raise ValueError("Transaction UID missing from response.")
        if not wait:
            return transaction
        completed_transaction: CdoTransaction = (
            self.transaction_service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid, polling_interval_sec=3
            )
        )
        if completed_transaction.cdo_transaction_status != CdoTransactionStatus.DONE:
            # Return the failed transaction instead of raising an exception
            # This allows the caller to inspect the error details
            return completed_transaction
        if completed_transaction.entity_uid is None:
            raise ValueError("Execution UID missing from completed transaction.")
        return self.get_cli_results(completed_transaction.entity_uid)

    def get_cli_result(self, cli_result_uid: str) -> CdoCliResult:
        return self.command_line_interface_api.get_cli_result(cli_result_uid=cli_result_uid)

    def get_cli_results(self, execution_uid: str) -> List[CdoCliResult]:
        q = f"executionUid:{execution_uid}"
        results = self.command_line_interface_api.get_cli_results(q=q).items or []
        return list(results)
