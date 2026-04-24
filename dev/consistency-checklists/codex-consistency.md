# codex-consistency

Repo-wide repeated mechanism inventory for future PR consistency review.

This file is meant to be used as an AI review checklist. If a PR touches one
instance of a repeated mechanism, review the sibling instances listed here
before approving the change.

Survey basis:
- Date: 2026-04-21
- CLI command files: 69 `command.py` files under `sccfm_cli/commands/`
- CLI command tests: 53 tests under `sccfm_cli/commands/tests/`
- Core service/helper files: 28 files under `sccfm_core/services/`
- Core tests: 20 tests under `sccfm_core/tests/`
- Ansible modules: 47 files under `sccfm-ansible/plugins/modules/`
- Ansible module tests: 34 tests under `sccfm-ansible/plugins/modules/tests/`
- Example playbooks: 32 playbooks under `sccfm-ansible/examples/` excluding inventory

How to use:
1. Find the mechanism family your PR touches.
2. Review every sibling surface named in that family.
3. Treat each checkbox as "did this PR preserve this contract everywhere it exists?"
4. If the answer is "no", either fix the sibling surfaces in the same PR or leave an explicit follow-up.

## 1. Cross-surface feature parity

- [ ] Inventory/device features are reviewed across all three layers:
  `sccfm_core/services/inventory/*`, `sccfm_cli/commands/inventory/devices/**`,
  and `sccfm-ansible/plugins/modules/*`.
- [ ] Object-management features are reviewed across all three layers:
  `sccfm_core/services/object_management/*`, `sccfm_cli/commands/objects/**`,
  and matching Ansible modules.
- [ ] Policy features are reviewed across all three layers:
  `sccfm_core/services/policy/*`, `sccfm_cli/commands/policies/**`,
  and matching Ansible modules.
- [ ] User-facing feature changes also review the mirror surfaces:
  tests, example playbooks, e2e playbooks, `README.md`, `INSTALL.md`,
  `sccfm-ansible/README.md`, and devkit discoverability.
- [ ] When a feature is parser-backed, parser, model, service, CLI rendering,
  and tests move together.

High-value repeated families:
- ASA read/inspection: boot registry, local users, disk files, CLI execution,
  HA check, shun display, not-on-version.
- ASA mutation/async: change boot image, shun add/remove/clear, password change,
  onboard, upgrade trigger.
- FTD read/inspection: list, list-not-on-version, compatible versions, CLI execution.
- FTD mutation/async: upgrade trigger, deploy, onboard, ZTP onboard.
- Objects: network object CRUD, network group CRUD, member add/remove,
  object override add/edit/delete/show/apply/update-default.
- Policies: access group list/get, access rule create/get/list/update/delete.

## 2. CLI command skeletons

- [ ] New or edited CLI commands still follow the `BaseCommand` contract:
  `name`, `help_text`, `build_params()`, `handle()`, `register()` or `build()`.
- [ ] Command groups still register subcommands explicitly and fail with a
  clear "Specify a subcommand" message.
- [ ] New leaf commands live in their own small file and do not accumulate
  unrelated behavior.
- [ ] CLI commands preserve strict typing and `cast(...)` usage patterns
  instead of relying on untyped `kwargs`.

Primary locations:
- `sccfm_cli/commands/base.py`
- `sccfm_cli/cli.py`
- Group commands such as `inventory/command.py`, `objects/command.py`,
  `policies/command.py`, `inventory/devices/asa/command.py`,
  `inventory/devices/ftd/command.py`,
  `inventory/devices/cdfmc_managed_ftd/command.py`

## 3. Shared Click option factories

- [ ] Reusable CLI options are sourced from the shared option factories before
  introducing new ad hoc `click.Option(...)` definitions.
- [ ] Pagination options stay aligned everywhere:
  `--limit`, `--offset`, defaults, ranges, help text.
- [ ] Formatting options stay aligned everywhere:
  `--format` choices, default, JSON/table semantics.
- [ ] Transaction options stay aligned everywhere:
  `--wait`, `--timeout`, help text, defaults.
- [ ] Config path behavior stays aligned everywhere:
  `--config-path`, `SCCFM_CONFIG`, default path wording.
- [ ] Inventory filter semantics stay aligned:
  `--query`, `--device-name`, `--device-uids`.
- [ ] Object option semantics stay aligned:
  `--uid`, `--name`, `--new-name`, `--tags`, `--labels`, `--check`,
  referenced-object and literal options.

Primary locations:
- `sccfm_cli/commands/shared_options.py`
- `sccfm_cli/commands/inventory/options.py`
- `sccfm_cli/commands/objects/options.py`

## 4. CLI progress, spinner, and silent-mode behavior

- [ ] Commands that show progress use `@with_spinner(...)` or
  `BaseCommand.wait_for_transaction(...)` rather than inventing a new pattern.
- [ ] `--silent` suppresses spinners and progress indicators consistently.
- [ ] Spinner text remains specific to the operation and does not drift from
  the command/action name.
- [ ] Long-running transaction polling still writes progress to stderr and
  leaves stdout clean for machine-readable output.

Primary locations:
- `sccfm_cli/utils/spinner.py`
- `sccfm_cli/commands/base.py`
- Many CLI handlers under `sccfm_cli/commands/**/command.py`

## 5. JSON vs table rendering contracts

- [ ] Every command that offers `--format json` returns stable machine-readable
  output that does not depend on Rich rendering.
- [ ] Commands that print raw JSON containing escape sequences use `print(...)`
  when needed instead of Rich console rendering.
- [ ] Table mode preserves the same underlying data as JSON mode.
- [ ] Success/failure messaging stays consistent between JSON and table modes.
- [ ] Pagination summaries are present where the surrounding command family
  already expects them.

Repeated renderer locations:
- `sccfm_cli/commands/inventory/devices/rendering.py`
- `sccfm_cli/commands/inventory/devices/asa/cli_result_renderer.py`
- Per-command `_render_*` methods in object, policy, inventory, and upgrade commands

## 6. Device-target selection helpers

- [ ] ASA device-targeted commands continue to use `AsaDeviceTargetCommand`
  and `asa_device_filter_params(...)`.
- [ ] General FTD commands continue to use `FtdDeviceTargetCommand`
  and the canonical FTD device-type constants.
- [ ] cdFMC-managed FTD commands continue to use
  `CdfmcFtdDeviceTargetCommand` and the stricter single-entity filter.
- [ ] Validation semantics are preserved for each family:
  `require_exactly_one_filter`, `allow_no_filters`, `wrap_query_with_parentheses`.
- [ ] `--check` target reporting stays aligned across ASA and FTD families.

Primary locations:
- `sccfm_cli/commands/inventory/devices/asa/shared.py`
- `sccfm_cli/commands/inventory/devices/ftd/shared.py`
- `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/shared.py`

## 7. CLI preflight and check-mode semantics

- [ ] `--check` remains non-mutating everywhere it exists.
- [ ] `--check` returns structured JSON when JSON mode is requested.
- [ ] `--check` emits clear "can proceed" / "would fail" messaging in table mode.
- [ ] Create vs update vs delete preflight logic keeps the same meaning of
  `exists`, `can_proceed`, and `reason`.
- [ ] Referenced-object validation stays aligned for network groups,
  access rules, ASA image validation, and device-target checks.

Primary locations:
- `sccfm_cli/commands/objects/utils.py`
- `sccfm_cli/commands/objects/**/command.py`
- `sccfm_cli/commands/policies/access_rule/create/command.py`
- `sccfm_cli/commands/inventory/devices/asa/change_boot_image/command.py`
- `sccfm_cli/commands/inventory/devices/asa/shared.py`
- `sccfm_cli/commands/inventory/devices/ftd/shared.py`

## 8. Async transaction handling

- [ ] Commands/modules that trigger async operations still return or poll a
  `CdoTransaction` instead of mixing transport and final state objects.
- [ ] CLI uses `wait_for_transaction(...)`, `print_submitted_transaction(...)`,
  `print_failed_transaction_details(...)`, and `is_failed_transaction(...)`.
- [ ] Ansible modules expose stable transaction payload keys when changed=True.
- [ ] Timeout defaults stay aligned between CLI and Ansible surfaces.
- [ ] Failure states remain `DONE` vs `ERROR` vs `CANCELLED` consistently.

Primary locations:
- `sccfm_cli/commands/base.py`
- `sccfm_core/services/transaction_service.py`
- `sccfm_core/models/cdo_transaction_status.py`
- Upgrade, deploy, onboard, shun, HA-check, disk, CLI execution commands/modules

## 9. Config, auth, region, and environment handling

- [ ] CLI profile loading and saving stays aligned with `ConfigService`
  and the global `--profile` behavior.
- [ ] Ansible modules use `base_argument_spec()` and `create_config(module)`
  before adding custom auth handling.
- [ ] Inventory plugin auth/env fallback stays aligned with module behavior.
- [ ] Region vocabulary stays aligned across CLI, Ansible, `.env.example`,
  README, install docs, and examples.
- [ ] Token/env variable names stay aligned:
  `SCCFM_API_TOKEN`, `SCCFM_REGION`, `SCCFM_CONFIG`.

Primary locations:
- `sccfm_cli/services/config_service.py`
- `sccfm_cli/commands/configure.py`
- `sccfm-ansible/plugins/module_utils/config.py`
- `sccfm-ansible/plugins/inventory/sccfm.py`
- `.env.example`
- `README.md`
- `INSTALL.md`

## 10. Core service wrapper pattern

- [ ] SDK integrations still build clients through `ApiClientFactory().build(config)`.
- [ ] Service constructors remain thin and side-effect free.
- [ ] Public service methods stay small and typed.
- [ ] Cross-surface logic belongs in `sccfm_core`, not duplicated in CLI or Ansible.

Primary locations:
- `sccfm_core/factories/api_client_factory.py`
- `sccfm_core/services/inventory/*`
- `sccfm_core/services/object_management/*`
- `sccfm_core/services/policy/*`
- `sccfm_core/services/transaction_service.py`

## 11. Raw-response helpers and custom response dataclasses

- [ ] Object and policy API code keeps using the raw-response helpers instead
  of duplicating `response.read()`, `json.loads(...)`, and status checks.
- [ ] New helper logic is added once and reused compositionally.
- [ ] Service-layer `*Response` and `*ListResponse` dataclasses continue to
  provide `from_dict()` and `to_dict()` round-trips.
- [ ] Any new raw SDK workaround is centralized instead of repeated.

Primary locations:
- `sccfm_core/services/object_management/object_api_helper.py`
- `sccfm_core/services/policy/policy_api_helper.py`
- `sccfm_core/services/object_management/network_object_service.py`
- `sccfm_core/services/object_management/network_group_service.py`
- `sccfm_core/services/object_management/object_override_service.py`
- `sccfm_core/services/policy/access_group_service.py`
- `sccfm_core/services/policy/access_rule_service.py`

## 12. Identifier resolution and query-building utilities

- [ ] Name-vs-UID validation stays aligned between CLI and core layers.
- [ ] Object delete/update flows reuse `resolve_uid(...)` rather than
  re-implementing the same validation.
- [ ] Object list flows keep using `build_filtered_query(...)` so object-type
  filtering does not drift.
- [ ] UUID validation stays centralized via `validate_uids(...)`.
- [ ] ASA image path validation stays centralized via `validate_asa_image_path(...)`.

Primary locations:
- `sccfm_core/services/object_management/utils.py`
- `sccfm_core/utils/validation.py`
- `sccfm_cli/commands/objects/utils.py`

## 13. Parser/model/service/test clusters

- [ ] ASA parser changes update the corresponding frozen model dataclass,
  service adapter, and tests together.
- [ ] Parser-backed services keep transport execution separate from parsing.
- [ ] Parser tests keep real-looking CLI samples, malformed-input coverage,
  empty-input coverage, and immutability assertions where relevant.

Primary parser/model clusters:
- Boot registry:
  `models/asa_boot_registry.py`,
  `parsers/asa_boot_registry_parser.py`,
  `services/inventory/asa_boot_registry_service.py`,
  `tests/test_asa_boot_registry_parser.py`,
  `tests/test_asa_boot_registry_service.py`
- Disk files:
  `models/asa_disk_file.py`,
  `parsers/asa_disk_file_parser.py`,
  `services/inventory/asa_disk_file_service.py`,
  `tests/test_asa_disk_file_parser.py`,
  CLI/Ansible disk-file consumers
- Local users:
  `models/asa_local_user.py`,
  `parsers/asa_local_user_parser.py`,
  CLI/Ansible local-user commands/modules,
  `tests/test_asa_local_user_parser.py`
- Failover:
  `models/asa_failover_status.py`,
  `parsers/asa_failover_parser.py`,
  `services/inventory/asa_ha_check_service.py`,
  `tests/test_asa_failover_parser.py`,
  `tests/test_asa_ha_check_service.py`
- Shun:
  `models/asa_shun_entry.py`,
  `parsers/asa_shun_parser.py`,
  `services/inventory/asa_shun_service.py`,
  `tests/test_asa_shun_parser.py`,
  `tests/test_asa_shun_service.py`

## 14. Inventory list and pagination family

- [ ] Device and manager list behavior keeps aligned query/pagination semantics.
- [ ] Device-type filters remain appended consistently for device-specific lists.
- [ ] Page-count and entry-count rendering stay aligned.
- [ ] Shared list families continue to reuse `DeviceListCommand` where appropriate.

Primary locations:
- `sccfm_core/services/inventory/inventory_service.py`
- `sccfm_cli/commands/inventory/devices/rendering.py`
- `sccfm_cli/commands/inventory/devices/list/command.py`
- `sccfm_cli/commands/inventory/manager/list/command.py`
- `sccfm_cli/commands/inventory/devices/asa/command.py`
- `sccfm_cli/commands/inventory/devices/ftd/command.py`
- `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/command.py`
- `sccfm-ansible/plugins/modules/list_managers.py`
- `sccfm-ansible/plugins/inventory/sccfm.py`

## 15. Upgrade families

- [ ] Compatible-version logic stays aligned between CLI and Ansible for both
  ASA and FTD.
- [ ] Trigger-upgrade logic stays aligned between CLI and Ansible for both
  ASA and FTD.
- [ ] UID validation, downgrade prevention, package resolution, and wait/timeout
  semantics stay consistent.
- [ ] Version-to-dict serialization stays aligned across CLI and Ansible.

Primary locations:
- ASA:
  `sccfm_core/services/inventory/asa_upgrade_service.py`,
  `sccfm_core/services/inventory/asa_upgrade_version_service.py`,
  `sccfm_cli/commands/inventory/devices/asa/upgrade/**`,
  `sccfm-ansible/plugins/modules/list_asa_compatible_versions.py`,
  `sccfm-ansible/plugins/modules/trigger_asa_upgrade.py`
- FTD:
  `sccfm_core/services/inventory/ftd_upgrade_service.py`,
  `sccfm_core/services/inventory/ftd_upgrade_version_service.py`,
  `sccfm_cli/commands/inventory/devices/ftd/upgrade/**`,
  `sccfm-ansible/plugins/modules/list_ftd_compatible_versions.py`,
  `sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py`

## 16. Onboard and deploy families

- [ ] Device onboarding logic stays aligned between CLI, core, and Ansible.
- [ ] Duplicate target validation, check-mode/preflight behavior, and conflict
  reporting stay aligned across ASA onboard, FTD onboard, FTD ZTP onboard,
  and cdFMC deploy.
- [ ] Post-submit transaction handling stays aligned with the rest of the async family.

Primary locations:
- `sccfm_core/services/inventory/asa_onboard_service.py`
- `sccfm_core/services/inventory/ftd_onboard_service.py`
- `sccfm_core/services/inventory/ftd_ztp_onboard_service.py`
- `sccfm_core/services/inventory/ftd_deploy_service.py`
- `sccfm_cli/commands/inventory/devices/asa/onboard/command.py`
- `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/onboard/command.py`
- `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/onboard_ztp/command.py`
- `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/deploy/command.py`
- Matching Ansible modules and tests

## 17. Object CRUD and override families

- [ ] Network object and network group CRUD flows keep aligned semantics across
  core, CLI, and Ansible.
- [ ] Tag parsing and label handling stay aligned across create/update flows.
- [ ] Delete flows stay idempotent in both CLI and Ansible.
- [ ] Member add/remove semantics for network groups stay aligned.
- [ ] Override add/edit/delete/show/apply/update-default flows stay aligned.

Primary locations:
- `sccfm_core/services/object_management/network_object_service.py`
- `sccfm_core/services/object_management/network_group_service.py`
- `sccfm_core/services/object_management/object_override_service.py`
- `sccfm_cli/commands/objects/**`
- `sccfm-ansible/plugins/modules/*network_object*.py`
- `sccfm-ansible/plugins/modules/*network_group*.py`
- `sccfm-ansible/plugins/modules/*object_override*.py`
- `sccfm-ansible/plugins/modules/update_object_default.py`
- `sccfm-ansible/plugins/modules/get_object.py`

## 18. Policy families

- [ ] Access-group read semantics stay aligned across core, CLI, and Ansible.
- [ ] Access-rule CRUD semantics stay aligned across core, CLI, and Ansible.
- [ ] Network-object reference resolution for access rules stays aligned.
- [ ] Table/JSON renderers for access rules and access groups stay aligned with
  the underlying `to_dict()` payloads.

Primary locations:
- `sccfm_core/services/policy/access_group_service.py`
- `sccfm_core/services/policy/access_rule_service.py`
- `sccfm_cli/commands/policies/access_group/**`
- `sccfm_cli/commands/policies/access_rule/**`
- `sccfm-ansible/plugins/modules/list_access_groups.py`
- `sccfm-ansible/plugins/modules/get_access_group.py`
- `sccfm-ansible/plugins/modules/list_access_rules.py`
- `sccfm-ansible/plugins/modules/get_access_rule.py`
- `sccfm-ansible/plugins/modules/create_access_rule.py`
- `sccfm-ansible/plugins/modules/update_access_rule.py`
- `sccfm-ansible/plugins/modules/delete_access_rule.py`

## 19. Ansible module skeleton consistency

- [ ] Every module keeps the same high-level structure:
  `DOCUMENTATION`, `EXAMPLES`, `RETURN`, `build_argument_spec()`,
  `run_module()`, `main()`.
- [ ] Modules use `base_argument_spec()` and `identifier_argument_spec()`
  where applicable instead of duplicating base auth/identifier fields.
- [ ] Delete modules use `run_delete_with_idempotency(...)`.
- [ ] Update modules use `fields_need_update(...)` or equally explicit
  changed-detection logic.
- [ ] `supports_check_mode`, `required_one_of`, and `mutually_exclusive`
  settings match the command family semantics.
- [ ] `ApiException` handling prefers `SccApiError.from_exception(...).to_dict()`
  where possible.

Primary locations:
- `sccfm-ansible/plugins/module_utils/config.py`
- `sccfm-ansible/plugins/module_utils/operations.py`
- `sccfm-ansible/plugins/modules/*.py`

## 20. Inventory plugin, loader, and builder family

- [ ] Inventory-plugin behavior stays aligned with the rest of the repo's
  auth, region, and inventory semantics.
- [ ] Host building stays centralized rather than duplicated in modules.
- [ ] Query and grouping behavior stays aligned with example inventory files and docs.

Primary locations:
- `sccfm-ansible/plugins/inventory/sccfm.py`
- `sccfm-ansible/plugins/module_utils/loaders/inventory_loader.py`
- `sccfm-ansible/plugins/module_utils/builders/inventory_host_builder.py`
- `sccfm-ansible/examples/inventory.sccfm.yml`

## 21. Test mirroring and naming

- [ ] A new leaf CLI command should usually add or update a focused command test.
- [ ] A new core service/parser/helper should usually add or update a focused core test.
- [ ] A new Ansible module should usually add or update a focused module test.
- [ ] If behavior is demo-worthy, an example playbook should exist or be updated.
- [ ] If behavior is workflow-level, an e2e playbook/test should be considered.

Main test locations:
- CLI: `sccfm_cli/commands/tests/**`
- Core: `sccfm_core/tests/**`
- Ansible unit: `sccfm-ansible/plugins/modules/tests/**`
- Ansible e2e: `sccfm-ansible/e2e/**`

## 22. Devkit and discoverability

- [ ] New CLI commands remain discoverable through Click introspection, which
  powers the devkit interactive runner.
- [ ] New example playbooks remain runnable through the devkit example runner.
- [ ] Setup/lint/test/build workflows stay aligned between scripts and docs.

Primary locations:
- `scripts/devkit_cli.py`
- `scripts/cli_commands.py`
- `scripts/setup_environment.sh`
- `README.md`
- `CONTRIBUTING.md`
- `INSTALL.md`

## 23. Package export barrels and import surfaces

- [ ] Package `__init__.py` files continue to export the expected public symbols.
- [ ] Leaf command packages still re-export their `*Command` class so parent
  groups can keep importing package-level symbols cleanly.
- [ ] Core service packages keep `__all__` aligned with the supported public API.
- [ ] Utility and model barrels stay synchronized with the modules they expose.
- [ ] If a symbol is intentionally internal-only, it should not leak through a
  barrel file by accident.

Primary locations:
- `sccfm_cli/**/__init__.py`
- `sccfm_core/__init__.py`
- `sccfm_core/factories/__init__.py`
- `sccfm_core/parsers/__init__.py`
- `sccfm_core/services/inventory/__init__.py`
- `sccfm_core/services/object_management/__init__.py`
- `sccfm_core/services/policy/__init__.py`
- `sccfm_core/utils/__init__.py`

## 24. Repeated Ansible helper shapes and e2e workflow families

- [ ] Module-local `resolve_device_uids_from_query(...)` helpers stay aligned
  wherever query-to-UID expansion exists.
- [ ] Module-local `_serialize_results(...)` helpers stay aligned with the
  corresponding CLI JSON payloads and service-layer models.
- [ ] Module-local `_version_to_dict(...)` helpers stay aligned between ASA and FTD
  compatible-version modules and their CLI equivalents.
- [ ] e2e workflow playbooks stay aligned with the module semantics they exercise:
  create/update/delete idempotency, read-vs-mutate separation, and cleanup flow.
- [ ] When a feature family gains a new module but no e2e story, call that out
  explicitly instead of assuming unit coverage is enough.

Primary locations:
- `sccfm-ansible/plugins/modules/list_asa_compatible_versions.py`
- `sccfm-ansible/plugins/modules/list_ftd_compatible_versions.py`
- `sccfm-ansible/plugins/modules/list_asa_boot_registry.py`
- `sccfm-ansible/plugins/modules/list_asa_disk_files.py`
- `sccfm-ansible/plugins/modules/change_asa_local_password.py`
- `sccfm-ansible/plugins/modules/execute_asa_cli.py`
- `sccfm-ansible/plugins/modules/deploy_cdfmc_ftd.py`
- `sccfm-ansible/plugins/modules/trigger_asa_upgrade.py`
- `sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py`
- `sccfm-ansible/e2e/**`

## 25. Historical drift guards

These are drift patterns that have already appeared in the repo. Review new PRs
against them so fixed consistency issues do not reappear.

- [ ] Region vocabulary must stay centralized in `sccfm_core/constants.py`.
  Public surfaces should advertise canonical `int, us, eu, apj, au, uae, in, ci`
  values; legacy `aus` may be accepted only as an alias normalized to `au`.
- [ ] README command names must match the live CLI tree.
  For example, the inventory manager command is singular:
  `inventory manager list`.
- [ ] The device-target helper pattern exists in three near-duplicate forms:
  ASA, FTD, and cdFMC-managed FTD shared command helpers. Any logic change here
  is easy to apply to only one family.
- [ ] Raw-response helper logic exists in two near-duplicate forms:
  `ObjectApiHelper` and `PolicyApiHelper`.
- [ ] Module-local query-to-UID helpers are duplicated across several Ansible
  modules instead of being centralized:
  `deploy_cdfmc_ftd`, `execute_asa_cli`, `change_asa_local_password`,
  `list_asa_boot_registry`, `list_asa_disk_files`,
  `list_asa_compatible_versions`, `list_ftd_compatible_versions`,
  `trigger_asa_upgrade`, `trigger_ftd_upgrade`.
- [ ] Module-local result/version serializer helpers are also duplicated across
  several Ansible modules:
  `_serialize_results(...)` and `_version_to_dict(...)` appear in multiple
  compatible-version and ASA read-operation modules.
- [ ] The package export/barrel pattern is widespread. Missing a single
  `__init__.py` re-export is an easy way to break parent imports or command wiring.
- [ ] Ansible modules currently without a matching unit test file:
  `add_asa_shun`, `add_object_override`, `apply_object_override_as_default`,
  `clear_asa_shun`, `delete_object_override`, `edit_object_override`,
  `get_object`, `list_asa_disk_files`, `list_cdfmc_access_policies`,
  `list_managers`, `remove_asa_shun`, `show_asa_shun`, `update_object_default`.
- [ ] Ansible modules currently without a same-name example playbook:
  `add_asa_shun`, `add_network_group_members`, `apply_object_override_as_default`,
  `clear_asa_shun`, `create_access_rule`, `create_network_group`,
  `create_network_object`, `delete_access_rule`, `delete_network_group`,
  `delete_network_object`, `delete_object_override`, `edit_object_override`,
  `get_access_group`, `get_access_rule`, `get_object`, `list_access_groups`,
  `list_access_rules`, `list_cdfmc_access_policies`, `list_managers`,
  `onboard_asa`, `remove_asa_shun`, `remove_network_group_members`,
  `show_asa_shun`, `update_access_rule`, `update_network_group`,
  `update_network_object`, `update_object_default`.
- [ ] Several core services/helpers do not have a direct same-name core test
  file and instead rely on higher-level coverage or no direct coverage:
  `asa_cli_service`, `asa_disk_file_service`, `asa_onboard_service`,
  `asa_user_password_service`, `cdfmc_access_policy_service`,
  `ftd_onboard_service`, `ftd_ztp_onboard_service`, `health_service`,
  `inventory_service`, `network_object_service`, `object_api_helper`,
  `object_override_service`, `policy_api_helper`, `transaction_service`, `utils`.
- [ ] e2e coverage is concentrated in ASA and object-management families.
  There is no comparable e2e footprint yet for FTD upgrade/deploy/onboard,
  policy management, object override flows, or manager/access-policy flows.
- [ ] CLI group commands and helper-only modules have less direct coverage than
  leaf commands. Any changes to group wiring should trigger an explicit review
  of command registration and devkit introspection.

## 26. Default AI review prompt fragment

Use this when reviewing a PR against this file:

"Check the PR against `dev/consistency-checklists/codex-consistency.md`.
Identify every repeated mechanism
family it touches. For each family, verify sibling surfaces in core, CLI,
Ansible, tests, examples, docs, and scripts. Call out any drift, missing mirror
updates, missing tests, naming inconsistencies, config/region mismatches, JSON
vs table output mismatches, check-mode mismatches, and async transaction
handling mismatches."
