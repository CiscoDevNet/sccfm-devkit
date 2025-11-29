from scc_firewall_manager_sdk import ApiClient, Configuration

from sccfm_cli.models import Config


class ApiClientFactory:
    def build(self, config: Config) -> ApiClient:
        return ApiClient(
            Configuration(
                host=f"https://api.{config.region}.security.cisco.com/firewall",
                access_token=config.api_token,
            )
        )
