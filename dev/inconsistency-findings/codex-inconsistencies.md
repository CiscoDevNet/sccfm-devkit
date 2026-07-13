# codex-inconsistencies

Repo-wide inconsistency report derived from the
`dev/consistency-checklists/codex-consistency.md` audit.

Date: 2026-04-21

This file is intentionally different from
`dev/consistency-checklists/codex-consistency.md`:
- `dev/consistency-checklists/codex-consistency.md` is the checklist for future
  PR review.
- `dev/inconsistency-findings/codex-inconsistencies.md` is the current-state
  report of things that are already inconsistent.

Confidence levels used below:
- Confirmed mismatch: directly verified in current repo files.
- Coverage mismatch: mirrored surfaces are uneven or missing by naming/parity check.
- Structural inconsistency: repeated logic exists in more than one place with divergent shapes or defaults.

## 1. Confirmed mismatches

### 1. Region vocabulary is split across CLI, docs, and Ansible

Status: Confirmed mismatch

Evidence:
- CLI configure accepts `_REGIONS = ("in", "au", "uae", "us", "eu", "apj", "int")`
  in `cisco_sccfm_cli/commands/configure.py`.
- `README.md` command docs also advertise `au`.
- Ansible shared config uses
  `ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in", "ci")`
  in `sccfm-ansible/plugins/module_utils/config.py`.
- `.env.example` also documents `aus` and `ci`.

Impact:
- A region value can be presented as valid in one surface and invalid in another.
- The repo currently has no single canonical public region list.

Recommendation:
- Define one canonical region list and reuse it everywhere.
- Decide explicitly whether the canonical spellings are `au` or `aus`, and whether `ci`
  should be CLI-visible.
- Move that list into a shared constant instead of keeping separate CLI and Ansible tuples.

### 2. Several Ansible module docs omit `ci` even though shared config allows it

Status: Confirmed mismatch

Affected modules:
- `sccfm-ansible/plugins/modules/add_asa_shun.py`
- `sccfm-ansible/plugins/modules/asa_ha_check.py`
- `sccfm-ansible/plugins/modules/clear_asa_shun.py`
- `sccfm-ansible/plugins/modules/list_asa_not_on_version.py`
- `sccfm-ansible/plugins/modules/list_ftd_not_on_version.py`
- `sccfm-ansible/plugins/modules/remove_asa_shun.py`
- `sccfm-ansible/plugins/modules/show_asa_shun.py`

Evidence:
- These modules document the region as `(int, us, eu, apj, aus, uae, or in)`.
- Shared validation in `sccfm-ansible/plugins/module_utils/config.py` allows `ci`.

Impact:
- Module docs are not aligned with actual validation behavior.

Recommendation:
- Replace per-module hard-coded region strings with one shared doc fragment or regenerate them
  from the shared config source.

### 3. README uses `managers` while the CLI group name is `manager`

Status: Confirmed mismatch

Evidence:
- `README.md` documents `sccfm-cli inventory managers list`.
- `cisco_sccfm_cli/commands/inventory/manager/command.py` defines the group name as `manager`.

Impact:
- The README command string is wrong for the current CLI.

Recommendation:
- Update README to use `inventory manager list`, or rename the CLI group to `managers`
  if that is the desired public surface.

### 4. Async timeout defaults are not aligned

Status: Confirmed mismatch

Evidence:
- `cisco_sccfm_core/services/transaction_service.py` uses `timeout_sec: int = 300`.
- CLI transaction polling surfaces default to `3600`:
  `cisco_sccfm_cli/commands/transaction.py`,
  `cisco_sccfm_cli/commands/inventory/devices/asa/upgrade/trigger/command.py`,
  `cisco_sccfm_cli/commands/inventory/devices/ftd/upgrade/trigger/command.py`.
- Ansible FTD trigger also defaults to `3600`:
  `sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py`.
- Ansible ASA trigger defaults to `300` in code:
  `sccfm-ansible/plugins/modules/trigger_asa_upgrade.py`.
- The ASA trigger module example shows `timeout: 900`, which adds a third value.

Impact:
- Identical operations behave differently depending on whether they are called
  from core, CLI, ASA Ansible, or FTD Ansible.

Recommendation:
- Pick one canonical timeout default for transaction waits.
- Use it in core, CLI, and Ansible.
- Update all docs/examples to match the implementation.

### 5. Local-user feature naming is split across command path, tests, and Ansible module

Status: Confirmed mismatch

Evidence:
- CLI command directory is `cisco_sccfm_cli/commands/inventory/devices/asa/list_asa_local_users/`.
- CLI command name is `list-local-users` in
  `cisco_sccfm_cli/commands/inventory/devices/asa/list_asa_local_users/command.py`.
- Ansible module is `list_asa_local_users.py`.
- CLI tests are split across two naming schemes:
  `cisco_sccfm_cli/commands/tests/inventory/devices/asa/list_asa_local_users/test_list_asa_local_users.py`
  and
  `cisco_sccfm_cli/commands/tests/inventory/devices/asa/list_local_users/test_list_local_users.py`.

Impact:
- The same feature is described with three different names:
  `list_asa_local_users`, `list-local-users`, and `list_local_users`.

Recommendation:
- Choose one canonical feature name and normalize command directories, tests,
  and docs around it.

### 6. ASA execute-CLI test path does not mirror the command path

Status: Confirmed mismatch

Evidence:
- Source command path:
  `cisco_sccfm_cli/commands/inventory/devices/asa/cli/execute/command.py`
- Test path:
  `cisco_sccfm_cli/commands/tests/inventory/devices/asas/cli/executions/test_asa_execute_cli.py`

Impact:
- Test layout is inconsistent with source layout.
- The mismatch makes grep-based parity checks noisier and easier to miss.

Recommendation:
- Rename the test path to mirror the command path:
  `inventory/devices/asa/cli/execute/...`

### 7. `with_spinner` import style is inconsistent

Status: Confirmed mismatch

Evidence:
- Most commands import `with_spinner` via `from cisco_sccfm_cli.utils import with_spinner`.
- `cisco_sccfm_cli/commands/inventory/devices/asa/list_asa_local_users/command.py`
  imports `from cisco_sccfm_cli.utils.spinner import with_spinner`.

Impact:
- Minor, but it breaks a repo-wide import convention used almost everywhere else.

Recommendation:
- Normalize on the package export import style.

### 8. Vault password example filename is wrong in one doc comment

Status: Confirmed mismatch

Evidence:
- Actual example file present in repo:
  `sccfm-ansible/examples/.vault_pass.example`
- `sccfm-ansible/examples/group_vars/all/vault.yml.example` says:
  `cp ../../.vault_pass_example ../../.vault_pass`

Impact:
- The documented filename does not match the actual file name.

Recommendation:
- Fix the comment to use `.vault_pass.example`.

### 9. The Ansible action group is incomplete, so `module_defaults` is not repo-wide

Status: Confirmed mismatch

Evidence:
- `sccfm-ansible/meta/runtime.yml` defines the collection action group
  `cisco.sccfm.all`.
- The following shipped modules are missing from that action group:
  `add_network_group_members`,
  `create_access_rule`,
  `delete_access_rule`,
  `get_access_group`,
  `get_access_rule`,
  `list_access_groups`,
  `list_access_rules`,
  `onboard_cdfmc_ftd_ztp`,
  `remove_network_group_members`,
  `update_access_rule`.
- Some omitted modules still document `module_defaults: group/cisco.sccfm.all`
  in their examples:
  `create_access_rule.py`,
  `delete_access_rule.py`,
  `get_access_rule.py`,
  `list_access_rules.py`,
  `update_access_rule.py`.

Impact:
- `module_defaults` does not actually apply to every collection module.
- Some published examples describe a pattern that will not work for those modules
  until runtime metadata is fixed.

Recommendation:
- Add every module to `cisco.sccfm.all`, or narrow the documented guarantee and
  remove broken `module_defaults` examples from omitted modules.

### 10. `module_defaults` example coverage is uneven across Ansible modules

Status: Confirmed mismatch

Evidence:
- These modules do not include a `module_defaults` example in `EXAMPLES`,
  even though many sibling modules do:
  `add_network_group_members.py`,
  `change_asa_boot_image.py`,
  `deploy_cdfmc_ftd.py`,
  `get_access_group.py`,
  `list_access_groups.py`,
  `list_asa_compatible_versions.py`,
  `list_asa_local_users.py`,
  `list_cdfmc_access_policies.py`,
  `list_ftd_compatible_versions.py`,
  `list_managers.py`,
  `onboard_cdfmc_ftd.py`,
  `onboard_cdfmc_ftd_ztp.py`,
  `remove_network_group_members.py`,
  `trigger_asa_upgrade.py`,
  `trigger_ftd_upgrade.py`.

Impact:
- The collection teaches two different documentation patterns for credential/config reuse.
- Reviewers cannot assume a new module will document the same collection-level usage
  style as its siblings.

Recommendation:
- Decide whether every module should show a `module_defaults` example.
- If yes, backfill the missing example blocks and keep them aligned with the
  runtime action group.

### 11. Shared Ansible config helpers are only used by part of the module set

Status: Confirmed mismatch

Evidence:
- These modules do not use `base_argument_spec()`:
  `change_asa_local_password.py`,
  `execute_asa_cli.py`,
  `list_asa_boot_registry.py`,
  `list_asa_compatible_versions.py`,
  `list_asa_disk_files.py`,
  `list_asa_local_users.py`,
  `list_ftd_compatible_versions.py`,
  `onboard_asa.py`,
  `trigger_ftd_upgrade.py`.
- These modules do not use `create_config(module)`:
  `change_asa_local_password.py`,
  `deploy_cdfmc_ftd.py`,
  `execute_asa_cli.py`,
  `list_asa_boot_registry.py`,
  `list_asa_compatible_versions.py`,
  `list_asa_disk_files.py`,
  `list_asa_local_users.py`,
  `onboard_asa.py`,
  `onboard_cdfmc_ftd.py`,
  `onboard_cdfmc_ftd_ztp.py`,
  `trigger_asa_upgrade.py`.
- Example outlier:
  `sccfm-ansible/plugins/modules/list_asa_local_users.py` hand-defines
  `region` and `api_token` in `build_argument_spec()` and manually constructs
  `Config(...)` inside `run_module()`.

Impact:
- Shared auth/config validation behavior can drift between module families.
- Fixes to env fallback, validation, or `no_log` handling are not guaranteed to
  propagate to every module.

Recommendation:
- Standardize on `base_argument_spec()` + `create_config(module)` for every module.
- Treat manual config parsing as an explicit exception only if it is justified
  in code comments.

### 12. `supports_check_mode` support is uneven across Ansible modules

Status: Confirmed mismatch

Evidence:
- These modules do not set `supports_check_mode=True` on `AnsibleModule`:
  `add_asa_shun.py`,
  `asa_ha_check.py`,
  `change_asa_local_password.py`,
  `clear_asa_shun.py`,
  `execute_asa_cli.py`,
  `list_asa_boot_registry.py`,
  `list_asa_compatible_versions.py`,
  `list_asa_disk_files.py`,
  `list_asa_local_users.py`,
  `list_asa_not_on_version.py`,
  `list_ftd_compatible_versions.py`,
  `list_ftd_not_on_version.py`,
  `remove_asa_shun.py`,
  `show_asa_shun.py`.

Impact:
- Similar read or device-operation modules expose different Ansible behavior in
  check mode.
- A repo-wide reviewer cannot assume collection modules respond consistently to
  `--check`.

Recommendation:
- Decide whether every module should support check mode.
- At minimum, normalize all read-only modules and non-mutating device queries
  to the same behavior.

### 13. Ansible error handling is split between module families

Status: Confirmed mismatch

Evidence:
- Device-operation modules such as
  `sccfm-ansible/plugins/modules/execute_asa_cli.py` and
  `sccfm-ansible/plugins/modules/trigger_asa_upgrade.py`
  translate SDK failures through `ApiException` and `SccApiError`.
- Object and policy modules such as
  `sccfm-ansible/plugins/modules/create_network_object.py`,
  `sccfm-ansible/plugins/modules/list_access_groups.py`,
  and many sibling CRUD/list modules only catch generic `Exception`
  and return ad-hoc `module.fail_json(msg=...)` strings.
- Confirmed module set without `ApiException` / `SccApiError` handling:
  `add_network_group_members.py`,
  `add_object_override.py`,
  `apply_object_override_as_default.py`,
  `create_access_rule.py`,
  `create_network_group.py`,
  `create_network_object.py`,
  `delete_access_rule.py`,
  `delete_network_group.py`,
  `delete_network_object.py`,
  `delete_object_override.py`,
  `edit_object_override.py`,
  `get_access_group.py`,
  `get_access_rule.py`,
  `get_object.py`,
  `list_access_groups.py`,
  `list_access_rules.py`,
  `list_network_groups.py`,
  `list_network_objects.py`,
  `remove_network_group_members.py`,
  `update_access_rule.py`,
  `update_network_group.py`,
  `update_network_object.py`,
  `update_object_default.py`.

Impact:
- Equivalent API failures surface with different payload shapes and different
  detail levels depending on module family.
- Collection consumers cannot rely on one uniform failure contract.

Recommendation:
- Standardize on `ApiException` -> `SccApiError.from_exception(e).to_dict()`
  everywhere Ansible modules talk to the SDK.
- Reserve generic `Exception` wrapping for truly non-SDK failures.

## 2. Coverage-parity mismatches

These are not necessarily broken behaviors, but they are current consistency gaps
 between mirrored repo surfaces.

### 14. Ansible module unit-test coverage is uneven by module name parity

Status: Coverage mismatch

Modules without a same-name unit test file:
- `add_asa_shun`
- `add_object_override`
- `apply_object_override_as_default`
- `clear_asa_shun`
- `delete_object_override`
- `edit_object_override`
- `get_object`
- `list_asa_disk_files`
- `list_cdfmc_access_policies`
- `list_managers`
- `remove_asa_shun`
- `show_asa_shun`
- `update_object_default`

Impact:
- Cross-surface feature families do not have even test coverage.

Recommendation:
- Backfill module tests for missing same-name surfaces, starting with the
  mutating modules and the user-facing read modules.

### 15. Ansible example-playbook coverage is uneven by module name parity

Status: Coverage mismatch

Modules without a same-name example playbook:
- `add_asa_shun`
- `add_network_group_members`
- `apply_object_override_as_default`
- `clear_asa_shun`
- `create_access_rule`
- `create_network_group`
- `create_network_object`
- `delete_access_rule`
- `delete_network_group`
- `delete_network_object`
- `delete_object_override`
- `edit_object_override`
- `get_access_group`
- `get_access_rule`
- `get_object`
- `list_access_groups`
- `list_access_rules`
- `list_cdfmc_access_policies`
- `list_managers`
- `onboard_asa`
- `remove_asa_shun`
- `remove_network_group_members`
- `show_asa_shun`
- `update_access_rule`
- `update_network_group`
- `update_network_object`
- `update_object_default`

Impact:
- Similar features have different levels of example/discoverability support.

Recommendation:
- Either add example playbooks or explicitly define which modules are intentionally
  example-backed only through umbrella workflows.

### 16. e2e coverage is concentrated in ASA and object-management flows

Status: Coverage mismatch

Observed e2e families:
- ASA:
  `test_asa_ha_check.py`,
  `test_asa_read_operations.py`,
  `test_asa_shun_lifecycle.py`,
  `test_asa_upgrade_workflow.py`
- Objects:
  `test_network_object_lifecycle.py`

Notably absent as dedicated e2e families:
- FTD onboard/deploy/upgrade flows
- Policy flows
- Object override flows
- Manager/access-policy flows

Impact:
- Workflow-level validation is uneven across major feature families.

Recommendation:
- Decide which product surfaces require e2e parity and build that intentionally.

### 17. Core service/helper direct test coverage is uneven by same-name parity

Status: Coverage mismatch

Core services/helpers without a direct same-name test file:
- `asa_cli_service`
- `asa_disk_file_service`
- `asa_onboard_service`
- `asa_user_password_service`
- `cdfmc_access_policy_service`
- `ftd_onboard_service`
- `ftd_ztp_onboard_service`
- `health_service`
- `inventory_service`
- `network_object_service`
- `object_api_helper`
- `object_override_service`
- `policy_api_helper`
- `transaction_service`
- `utils`

Impact:
- Some core abstractions are only covered indirectly or not at the same granularity
  as sibling services.

Recommendation:
- Add direct tests for the helpers that define shared behavior or shared defaults.

## 3. Structural inconsistencies and duplication risks

These items are not always wrong today, but they are current sources of drift.

### 18. Device-target helper logic exists in three similar but not identical forms

Status: Structural inconsistency

Locations:
- `cisco_sccfm_cli/commands/inventory/devices/asa/shared.py`
- `cisco_sccfm_cli/commands/inventory/devices/ftd/shared.py`
- `cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/shared.py`

Observed divergence:
- Different support for `allow_no_filters`
- Different support for `require_exactly_one_filter`
- Different entity-type query building
- Similar `report_check_targets(...)` implementations repeated three times

Impact:
- Small behavior changes are easy to apply to only one family.

Recommendation:
- Pull shared selector mechanics into one lower-level helper with feature flags.

### 19. Raw-response helpers are duplicated by domain

Status: Structural inconsistency

Locations:
- `cisco_sccfm_core/services/object_management/object_api_helper.py`
- `cisco_sccfm_core/services/policy/policy_api_helper.py`

Observed duplication:
- Very similar `read_raw_response(...)`
- Very similar `check_raw_response(...)`
- Very similar status-handling helpers

Impact:
- HTTP-response parsing fixes can drift between object and policy surfaces.

Recommendation:
- Extract a common raw-response helper or shared mixin.

### 20. Ansible query-to-UID helpers are duplicated across multiple modules

Status: Structural inconsistency

Modules with local `resolve_device_uids_from_query(...)` helpers:
- `deploy_cdfmc_ftd.py`
- `execute_asa_cli.py`
- `change_asa_local_password.py`
- `list_asa_boot_registry.py`
- `list_asa_compatible_versions.py`
- `list_asa_disk_files.py`
- `list_ftd_compatible_versions.py`
- `trigger_asa_upgrade.py`
- `trigger_ftd_upgrade.py`

Impact:
- Query semantics can drift subtly between modules.

Recommendation:
- Centralize this in `sccfm-ansible/plugins/module_utils/`.

### 21. Ansible serializer helpers are duplicated across read/list modules

Status: Structural inconsistency

Observed duplicates:
- `_serialize_results(...)` in several ASA read/list modules
- `_version_to_dict(...)` in both ASA and FTD compatible-version modules

Impact:
- Payload-shape changes need to be applied in several places.

Recommendation:
- Move family-level serializers into shared module utils.

## 4. Priority order

### P1: Fix now

- Region vocabulary split
- Ansible region-doc drift
- README `manager` vs `managers`
- Timeout default mismatch
- CLI JSON output contract split (`print(...)` vs `console.print(...)`, mixed `json.dumps(...)` kwargs)
- Incomplete `cisco.sccfm.all` action group / broken `module_defaults` examples
- `.vault_pass.example` typo in docs

### P2: Normalize naming/layout next

- Local-user feature naming split
- ASA execute-CLI test path mismatch
- One-off `with_spinner` import style
- Policy list commands bypassing shared pagination option factories
- Shared Ansible config helper reuse
- Uneven `supports_check_mode`
- Split Ansible error handling
- Service-layer polling interval drift

### P3: Tackle as refactor/parity work

- "Not found" message wording drift
- ASA entity-type canonicalization asymmetry
- Low-signal typing/dataclass/`__future__` convention drift
- Missing `module_defaults` example parity
- Ansible same-name test/example gaps
- e2e parity gaps
- Core same-name test gaps
- Device-target helper consolidation
- Raw-response helper consolidation
- Ansible query/serializer helper consolidation

## 5. Suggested next-step sequence

1. Canonicalize region vocabulary in one source of truth.
2. Fix the incomplete `cisco.sccfm.all` action group so documented `module_defaults`
   behavior is actually true.
3. Normalize the CLI JSON rendering contract so every JSON branch is machine-safe
   and implemented the same way.
4. Align all timeout defaults and service-layer polling intervals, then update docs/examples.
5. Standardize Ansible modules on shared config helpers and one error-handling path.
6. Fix the README command name, the vault filename typo, the pagination option drift,
   and the naming/layout drift.
7. Decide which coverage gaps are required parity and backfill them deliberately.

## 6. Cross-model adjudication against
`dev/inconsistency-findings/claude-inconsistencies.md`

This section records the direct comparison against Claude's findings file.
Items below are intentionally split into:
- accepted and promoted into this report
- accepted but kept as low-signal convention drift
- rejected or not carried forward

### 22. CLI JSON output handling is inconsistent across commands

Status: Confirmed mismatch

Why this survived review:
- Claude was directionally right, but the stronger issue is broader than
  `console.print(...)` alone.
- The CLI currently mixes both `print(json.dumps(...))` and
  `self.console.print(json.dumps(...))` / `console.print(json.dumps(...))`.
- The `json.dumps(...)` kwargs also drift by command: some include
  `ensure_ascii=False`, some include `default=str`, some include neither.

Evidence:
- Bare `print(...)` examples:
  `cisco_sccfm_cli/commands/transaction.py`,
  `cisco_sccfm_cli/commands/inventory/devices/asa/shun/show/command.py`,
  `cisco_sccfm_cli/commands/inventory/devices/asa/disk/list_files/command.py`,
  `cisco_sccfm_cli/commands/inventory/devices/asa/list_boot_registry/command.py`,
  `cisco_sccfm_cli/commands/inventory/devices/ftd/upgrade/trigger/command.py`.
- `self.console.print(...)` / `console.print(...)` examples:
  `cisco_sccfm_cli/commands/base.py`,
  `cisco_sccfm_cli/commands/inventory/devices/rendering.py`,
  `cisco_sccfm_cli/commands/inventory/manager/list/command.py`,
  `cisco_sccfm_cli/commands/policies/access_group/list/command.py`,
  `cisco_sccfm_cli/commands/policies/access_rule/list/command.py`,
  many `objects/*` commands.

Impact:
- JSON mode is not implemented as one consistent contract.
- Rich rendering can interfere with machine-oriented output, and even where it does not,
  the repo still teaches two different JSON-output patterns.

Recommendation:
- Centralize JSON rendering in one helper and normalize on one contract:
  bare `print(json.dumps(..., indent=2, ensure_ascii=False, default=str))`.

### 23. Policy list commands bypass shared pagination option factories

Status: Confirmed mismatch

Why this survived review:
- Claude identified this as an access-rule issue; the same drift exists in
  access-group list as well.

Evidence:
- `cisco_sccfm_cli/commands/policies/access_rule/list/command.py`
  declares `click.Option(["--limit"], ...)` and `click.Option(["--offset"], ...)`
  directly.
- `cisco_sccfm_cli/commands/policies/access_group/list/command.py`
  does the same.
- Most other list commands use `limit_option()` and `offset_option()` from
  shared option helpers.

Impact:
- These commands miss the repo-wide `-l` / `-o` short flags.
- Pagination behavior is no longer guaranteed to be uniform from grep-able composition.

Recommendation:
- Replace the inline options with `limit_option()` and `offset_option()`.

### 24. Service-layer polling intervals diverge without a named policy

Status: Structural inconsistency

Why this survived review:
- The divergence is real even if some of it may be intentional.
- Claude's framing was fair, but this belongs under drift risk, not as a hard bug.

Evidence:
- Canonical transaction wait default:
  `cisco_sccfm_core/services/transaction_service.py` uses `polling_interval_sec=10`.
- Faster/alternate overrides exist in:
  `cisco_sccfm_core/services/inventory/asa_cli_service.py` with `3`,
  `cisco_sccfm_core/services/inventory/asa_onboard_service.py` with `5`,
  `cisco_sccfm_core/services/inventory/ftd_onboard_service.py` with `5`,
  `cisco_sccfm_core/services/inventory/ftd_ztp_onboard_service.py` with `5`.

Impact:
- Similar long-running operations poll at different cadences with no obvious
  shared policy.
- Future changes to polling behavior are easy to apply unevenly.

Recommendation:
- Introduce named polling constants or document the intentional override classes.

### 25. "Not found" message templates drift across the CLI and services

Status: Confirmed mismatch

Why this survived review:
- This is a real user-facing inconsistency, not just a wording preference.
- The current messages vary by identifier kind, punctuation, and whether the entity
  type is included.

Evidence:
- `cisco_sccfm_cli/commands/base.py`:
  `Profile '{profile}' not found.`
- `cisco_sccfm_core/services/policy/access_rule_service.py`:
  `Network object '{name}' not found.`
- `cisco_sccfm_core/services/object_management/network_group_service.py`:
  `Network group with UID '{uid}' not found.`
- `cisco_sccfm_core/services/object_management/utils.py`:
  `{entity_name} with name '{name}' not found.`
- `cisco_sccfm_cli/commands/objects/utils.py`:
  `Referenced object '{ref}' not found`
  (no period).

Impact:
- User-facing errors read differently for closely related failures.
- Tests tend to assert generic substrings like `not found`, which hides message drift.

Recommendation:
- Standardize one template family for not-found errors and reuse it everywhere.

### 26. Entity-type canonicalization is asymmetric between ASA and FTD

Status: Structural inconsistency

Why this survived review:
- FTD already has a canonical shared constant.
- ASA selection logic still inlines `EntityType.ASA` in several places.
- This is not a bug today, but it is a clear asymmetry in how the two device families
  are maintained.

Evidence:
- `cisco_sccfm_core/constants.py` defines `FTD_ENTITY_TYPES`.
- `cisco_sccfm_cli/commands/inventory/devices/ftd/shared.py` and
  `cisco_sccfm_cli/commands/inventory/devices/ftd/command.py` consume that constant.
- ASA equivalents inline `EntityType.ASA.value` in:
  `cisco_sccfm_cli/commands/inventory/devices/asa/shared.py`,
  `cisco_sccfm_cli/commands/inventory/devices/asa/onboard/command.py`,
  `cisco_sccfm_cli/commands/inventory/devices/rendering.py`,
  `cisco_sccfm_cli/commands/inventory/devices/asa/command.py`.

Impact:
- One device family has a canonical source of truth for entity types and the other does not.
- Refactors and future family expansion are more likely to drift on the ASA side.

Recommendation:
- Add `ASA_ENTITY_TYPES` to `cisco_sccfm_core/constants.py` or explicitly document why
  ASA remains inline while FTD is centralized.

### 27. Region vocabulary has no shared source of truth constant

Status: Structural inconsistency

Why this survived review:
- This is the root-cause form of the broader region split, not just a restatement of it.
- The current repo keeps region vocabulary in at least two separate code-level definitions.

Evidence:
- `cisco_sccfm_cli/commands/configure.py` defines a CLI-local
  `_REGIONS = ("in", "au", "uae", "us", "eu", "apj", "int")`.
- `sccfm-ansible/plugins/module_utils/config.py` defines a separate
  `ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in", "ci")`.
- `cisco_sccfm_core/constants.py` does not define any shared region constant today.

Impact:
- Region drift is structurally easy to reintroduce because there is no canonical import target.
- CLI, Ansible, and docs can keep diverging independently.

Recommendation:
- Introduce one shared constant in `cisco_sccfm_core/constants.py` and import it everywhere
  region vocabulary is validated or displayed.

### 28. CLI and Ansible handle region case normalization differently

Status: Confirmed mismatch

Why this survived review:
- This is a behavior mismatch, not just wording drift.
- It affects whether the same region value is accepted depending on entry point.

Evidence:
- CLI configure accepts a case-insensitive choice:
  `click.Choice(_REGIONS, case_sensitive=False)` in
  `cisco_sccfm_cli/commands/configure.py`.
- The CLI then normalizes the stored value via `region.lower()` in the same file.
- Ansible `Config.__post_init__` validates with an exact membership check:
  `if self.region not in ALLOWED_REGIONS:` in
  `sccfm-ansible/plugins/module_utils/config.py`.
- There is no lowercasing step in the Ansible config path before validation.

Impact:
- Equivalent values such as `US` or `Eu` are normalized in the CLI flow but rejected
  in the Ansible flow.
- Cross-surface behavior for `SCCFM_REGION` is inconsistent.

Recommendation:
- Normalize region values to lowercase in the Ansible config path before validation,
  then validate against the shared canonical region constant.

### Accepted but kept as low-signal convention drift

These claims from Claude are valid in a narrow sense, but I did not promote them
into the main priority stack because they are mostly mechanical style cleanup:

- Legacy typing syntax is mixed with newer style.
  Examples:
  `cisco_sccfm_core/services/inventory/asa_cli_service.py`,
  `cisco_sccfm_core/utils/validation.py`,
  `cisco_sccfm_cli/commands/base.py`
  still use `List[...]`, `Dict[...]`, and/or `Optional[...]` while many newer files use
  `list[...]`, `dict[...]`, and `... | None`.
- Frozen dataclass usage is mixed.
  Many models and CLI filter dataclasses are `@dataclass(frozen=True)`, while several
  service response/helper dataclasses and `cisco_sccfm_core/errors.py::SccApiError` are not.
- `from __future__ import annotations` usage is mixed.
  It is present in much of the repo, but missing from several scripts and service/package
  files, including `cisco_sccfm_scripts/build_ansible_collection.py`,
  `cisco_sccfm_scripts/validate_regex.py`,
  `cisco_sccfm_scripts/_test_setup_tokens.py`,
  `cisco_sccfm_core/__init__.py`,
  and a number of command group / service files.
- Region ordering/spelling presentation also drifts beyond the core value split.
  `_REGIONS` and `ALLOWED_REGIONS` do not just differ by `au` vs `aus` and `ci`;
  they also present the region list in a different order. I did not promote this
  separately because it is mostly a presentation-level consequence of item 27.

### Rejected or not carried forward from Claude's report

- The reported FTD `consoe` `NameError` is a false positive.
  I could not find that typo in the repo; it appears only inside
  `dev/inconsistency-findings/claude-inconsistencies.md`.
- The "`NotFoundError` vs `None` contract drift" claim is overstated as written.
  The cited examples mix public getters, identifier resolvers, and raw helper methods.
  There may still be design cleanup to do, but I do not consider the cited set a clean
  confirmed inconsistency.
- Renderer signature divergence between ASA and FTD was not promoted.
  The payloads and use cases differ enough that the API-shape difference may be justified.
- Mixed deep imports vs package exports, file naming preferences, doc metadata shape,
  parameter-fetch style, test assertion style, and conftest organization are either
  low-signal style issues or were not strong enough to treat as substantive inconsistency
  findings in the same class as the items above.
