# consolidated-inconsistencies

Validated, deduplicated inconsistency report consolidated from:
- `dev/inconsistency-findings/codex-inconsistencies.md`
- `dev/inconsistency-findings/claude-inconsistencies.md`
- `dev/inconsistency-findings/gemini-inconsistencies.md`

Cross-check reference checklists used during validation:
- `dev/consistency-checklists/codex-consistency.md`
- `dev/consistency-checklists/claude-consistency.md`

Date: 2026-04-21

## Scope and method

This file is intentionally not a raw merge of the model reports.

Validation standard used here:
- A finding is accepted only if it was re-verified directly in the repo.
- A finding is downgraded when the underlying drift is real but the original report overstated the impact.
- A finding is rejected when it is a false positive, an argument about preferred architecture rather than inconsistency, or too weakly evidenced.

Interpretation rules used here:
- "Confirmed mismatch" means the repo currently exposes different behavior, data, docs, or user-facing output across mirrored surfaces.
- "Structural inconsistency" means repeated logic exists in multiple places and is likely to drift further even if behavior is not yet broken.
- "Parity gap" means filename or surface parity is uneven. These are useful review signals, but they are not automatically proof of missing behavioral coverage.

Perspective lens used here:
- Code perspective: whether the inconsistency increases maintenance cost, refactor risk, drift risk, or review complexity.
- User perspective: whether the inconsistency changes what an operator, automation consumer, playbook author, or reader experiences at runtime or in docs.

## 1. Accepted findings

### 1. Region configuration is fragmented across surfaces

Status: Confirmed mismatch plus structural inconsistency

Validated facts:
- `sccfm_cli/commands/configure.py` defines `_REGIONS = ("in", "au", "uae", "us", "eu", "apj", "int")`.
- `sccfm-ansible/plugins/module_utils/config.py` defines `ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in", "ci")`.
- `sccfm_core/constants.py` has no shared region constant.
- Several Ansible module docs still advertise `(int, us, eu, apj, aus, uae, or in)` and omit `ci`.
- CLI configure uses `click.Choice(..., case_sensitive=False)` and stores `region.lower()`.
- Ansible `Config.__post_init__` validates `self.region` by exact membership with no lowercasing step.

Integrated conclusion:
- This is one root-cause family, not four separate disconnected issues.
- The repo currently has vocabulary drift (`au` vs `aus`), availability drift (`ci` only on some surfaces), presentation drift (different ordering), and behavior drift (CLI accepts uppercase values that Ansible rejects).

Code perspective:
- There is no canonical import target for region vocabulary, so future fixes can easily land in only one surface.

User perspective:
- Users can be told one region name in docs, enter another in the CLI, and then see Ansible reject the same value or casing.

Primary affected files:
- `sccfm_cli/commands/configure.py`
- `sccfm-ansible/plugins/module_utils/config.py`
- `.env.example`
- region text in multiple `sccfm-ansible/plugins/modules/*.py`
- `README.md`

Recommended fix path:
- Introduce one shared region constant in `sccfm_core/constants.py`.
- Normalize region values to lowercase before validation everywhere.
- Regenerate or centralize region help/doc strings from the shared source.

Sources integrated:
- Codex items 1, 2, 27, 28
- Claude N2, N3, N4

### 2. Ansible module contract is inconsistent across the collection

Status: Confirmed mismatch

Validated facts:
- `sccfm-ansible/meta/runtime.yml` action group `cisco.sccfm.all` is missing 10 shipped modules:
  `add_network_group_members`,
  `onboard_cdfmc_ftd_ztp`,
  `remove_network_group_members`.
- 10 modules do not use `base_argument_spec()`:
  `change_asa_local_password.py`,
  `execute_asa_cli.py`,
  `execute_ftd_cli.py`,
  `list_asa_boot_registry.py`,
  `list_asa_compatible_versions.py`,
  `list_asa_disk_files.py`,
  `list_asa_local_users.py`,
  `list_ftd_compatible_versions.py`,
  `onboard_asa.py`,
  `trigger_ftd_upgrade.py`.
- 12 modules do not use `create_config(module)`:
  `change_asa_local_password.py`,
  `deploy_cdfmc_ftd.py`,
  `execute_asa_cli.py`,
  `execute_ftd_cli.py`,
  `list_asa_boot_registry.py`,
  `list_asa_compatible_versions.py`,
  `list_asa_disk_files.py`,
  `list_asa_local_users.py`,
  `onboard_asa.py`,
  `onboard_cdfmc_ftd.py`,
  `onboard_cdfmc_ftd_ztp.py`,
  `trigger_asa_upgrade.py`.
- 14 modules do not declare `supports_check_mode=True`:
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
- 23 modules catch generic `Exception` and do not convert SDK failures through `ApiException` -> `SccApiError`.
- 15 modules omit a `module_defaults` example block.

Integrated conclusion:
- This is the most important collection-level inconsistency family after regions.
- The collection currently does not expose one uniform contract for defaults inheritance, config/env fallback, check mode, or failure payload shape.
- Some documentation still promises `module_defaults: group/cisco.sccfm.all` behavior more broadly than runtime metadata actually provides.
- The newly added FTD CLI module family improved parity in some places, but it also joined the existing shared-helper adoption drift.

Code perspective:
- The collection is harder to maintain because module authors are not building on one predictable skeleton.

User perspective:
- Playbook authors cannot rely on one consistent behavior for defaults, errors, or check mode across modules in the same collection.

Primary affected files:
- `sccfm-ansible/meta/runtime.yml`
- `sccfm-ansible/plugins/module_utils/config.py`
- many files under `sccfm-ansible/plugins/modules/`

Recommended fix path:
- Fix `runtime.yml` first.
- Standardize all modules on `base_argument_spec()` + `create_config(module)`.
- Standardize SDK failure handling on `SccApiError.from_exception(e).to_dict()`.
- Normalize `supports_check_mode=True`, then implement meaningful check-mode behavior where needed.
- Backfill `module_defaults` examples only after action-group membership is correct.

Sources integrated:
- Codex items 9, 10, 11, 12, 13
- Claude H.1, H.2, H.3, H.4, H.5

### 3. CLI JSON output does not follow one consistent contract

Status: Confirmed mismatch

Validated facts:
- The CLI mixes bare `print(json.dumps(...))` and `self.console.print(json.dumps(...))` / `console.print(json.dumps(...))`.
- `json.dumps(...)` kwargs also drift by command: some use `ensure_ascii=False`, some use `default=str`, some use neither.
- Confirmed `console.print(json.dumps(...))` examples include:
  `sccfm_cli/commands/base.py`,
  `sccfm_cli/commands/inventory/devices/rendering.py`,
  `sccfm_cli/commands/inventory/manager/list/command.py`,
  `sccfm_cli/commands/policies/access_group/list/command.py`,
  `sccfm_cli/commands/policies/access_rule/list/command.py`,
  many `objects/*` commands.
- Confirmed bare `print(json.dumps(...))` examples include:
  `sccfm_cli/commands/transaction.py`,
  `sccfm_cli/commands/inventory/devices/asa/shun/show/command.py`,
  `sccfm_cli/commands/inventory/devices/asa/disk/list_files/command.py`,
  `sccfm_cli/commands/inventory/devices/asa/list_boot_registry/command.py`,
  `sccfm_cli/commands/inventory/devices/ftd/upgrade/trigger/command.py`.

Integrated conclusion:
- This is a real contract split, not just a formatting preference.
- The repo currently teaches two incompatible implementations for JSON output.

Code perspective:
- JSON rendering changes currently require sweeping many command files with no shared helper enforcing one contract.

User perspective:
- Automation and piping are less trustworthy because JSON-mode behavior differs by command and can be sensitive to the rendering path.

Recommended fix path:
- Introduce one small CLI JSON helper and normalize on:
  `print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))`.

Sources integrated:
- Claude H1 plus later qualification
- Codex item 22

### 4. Async transaction behavior drifts in both timeout and polling cadence

Status: Confirmed mismatch plus structural inconsistency

Validated facts:
- `sccfm_core/services/transaction_service.py` defaults to `timeout_sec=300` and `polling_interval_sec=10`.
- CLI transaction-facing commands default to `timeout=3600`.
- `sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py` defaults to `timeout=3600`.
- `sccfm-ansible/plugins/modules/trigger_asa_upgrade.py` defaults to `timeout=300`, while its examples show `timeout: 900`.
- Polling interval overrides exist in:
  `sccfm_core/services/inventory/asa_cli_service.py` with `3`,
  `sccfm_core/services/inventory/asa_onboard_service.py` with `5`,
  `sccfm_core/services/inventory/ftd_onboard_service.py` with `5`,
  `sccfm_core/services/inventory/ftd_ztp_onboard_service.py` with `5`.

Integrated conclusion:
- Timeout defaults are a confirmed external inconsistency.
- Polling interval drift is a structural policy gap: the overrides may be intentional, but they are not named or documented as a shared policy.

Code perspective:
- There is no single timing policy for long-running operations, so maintenance changes can drift between services and interfaces.

User perspective:
- The same kind of operation can wait different lengths or appear to progress differently depending on whether it is run via core, CLI, or Ansible.

Recommended fix path:
- Introduce named timeout and polling constants.
- Align code, examples, and CLI/Ansible defaults around the same constants.

Sources integrated:
- Codex item 4
- Claude M4 and N1

### 5. Naming, path mirroring, and docs drift across mirrored features

Status: Confirmed mismatch

Validated facts:
- `README.md` documents `sccfm-cli inventory managers list` while the CLI group is `manager`.
- The ASA local-user feature is split across:
  command directory `list_asa_local_users`,
  CLI command name `list-local-users`,
  Ansible module `list_asa_local_users.py`,
  and two separate CLI test naming schemes.
- ASA execute-CLI source path is `inventory/devices/asa/cli/execute/...` while the test path is `inventory/devices/asas/cli/executions/...`.
- `sccfm-ansible/examples/group_vars/all/vault.yml.example` references `.vault_pass_example` while the actual file is `.vault_pass.example`.
- `with_spinner` import style is mostly `from sccfm_cli.utils import with_spinner`, but one ASA local-user command imports from `sccfm_cli.utils.spinner`.

Integrated conclusion:
- These are not deep behavioral bugs, but they do materially degrade grep-based review, test mirroring, and documentation trustworthiness.

Code perspective:
- Mirrored feature work is harder to audit because names and paths stop lining up cleanly across source, tests, and docs.

User perspective:
- Users and contributors see inconsistent command names, examples, and filenames, which makes the project feel less predictable.

Recommended fix path:
- Normalize the public CLI/doc names first.
- Then normalize path/layout naming and import style.

Sources integrated:
- Codex items 3, 5, 6, 7, 8

### 6. Policy list commands bypass shared pagination option factories

Status: Confirmed mismatch

Validated facts:
- `sccfm_cli/commands/policies/access_rule/list/command.py` declares inline `click.Option(["--limit"], ...)` and `click.Option(["--offset"], ...)`.
- `sccfm_cli/commands/policies/access_group/list/command.py` does the same.
- Other list surfaces generally use shared `limit_option()` / `offset_option()` factories, which provide the repo-wide `-l` / `-o` short flags and shared behavior.

Integrated conclusion:
- This is a clean CLI-surface inconsistency, not just style noise.

Code perspective:
- These commands sidestep the shared option layer, so pagination fixes and conventions will not propagate automatically.

User perspective:
- Users do not get the same short flags and pagination ergonomics on policy list commands that they get elsewhere in the CLI.

Recommended fix path:
- Replace the inline policy-list pagination options with the shared factories.

Sources integrated:
- Claude L2
- Codex item 23

### 7. Coverage parity is uneven, but should be treated as a parity audit signal

Status: Parity gap

Validated facts:
- 47 Ansible modules exist at `sccfm-ansible/plugins/modules/*.py` excluding `__init__.py`.
- 13 modules have no same-name unit test file:
  `add_asa_shun`,
  `add_object_override`,
  `apply_object_override_as_default`,
  `clear_asa_shun`,
  `delete_object_override`,
  `edit_object_override`,
  `get_object`,
  `list_asa_disk_files`,
  `list_cdfmc_access_policies`,
  `list_managers`,
  `remove_asa_shun`,
  `show_asa_shun`,
  `update_object_default`.
- 27 modules have no same-name example playbook.
- 28 core service/helper files exist under `sccfm_core/services` excluding `__init__.py`.
- 15 service/helper names have no direct same-name core test file:
  `asa_cli_service`,
  `asa_disk_file_service`,
  `asa_onboard_service`,
  `asa_user_password_service`,
  `cdfmc_access_policy_service`,
  `ftd_onboard_service`,
  `ftd_ztp_onboard_service`,
  `health_service`,
  `inventory_service`,
  `network_object_service`,
  `object_api_helper`,
  `object_override_service`,
  `policy_api_helper`,
  `transaction_service`,
  `utils`.
- E2E coverage is concentrated in ASA, access-rule lifecycle, and network-object lifecycle flows.

Qualified conclusion:
- These findings are valid as parity gaps.
- They are not proof that behavior is untested, because one test or playbook can legitimately cover multiple adjacent surfaces.
- They should be used as a review checklist and follow-up backlog, not as a claim that each listed surface is functionally untested.

Code perspective:
- Uneven parity increases review uncertainty because it is harder to tell which sibling surfaces were intentionally covered together.

User perspective:
- Users may see uneven discoverability and more uneven regression risk across features, especially where examples or direct tests are sparse.

Recommended fix path:
- Reframe these as parity audits.
- Backfill only where behavioral risk is high or public discoverability is poor.

Sources integrated:
- Codex items 14, 15, 16, 17
- Claude mild disagreement on filename-parity overcounting

### 8. Repeated helper logic is duplicated across several feature families

Status: Structural inconsistency

Validated facts:
- Device-target helper logic exists in parallel but not identical forms in:
  `sccfm_cli/commands/inventory/devices/asa/shared.py`,
  `sccfm_cli/commands/inventory/devices/ftd/shared.py`,
  `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/shared.py`.
- Raw-response helpers are duplicated in:
  `sccfm_core/services/object_management/object_api_helper.py`,
  `sccfm_core/services/policy/policy_api_helper.py`.
- `resolve_device_uids_from_query(...)` is duplicated across 9 Ansible modules.
- Serializer helpers such as `_serialize_results(...)`, `_version_to_dict(...)`,
  `_serialize_result(...)`, `_serialize_device(...)`, `_serialize_entries(...)`,
  and `_serialize_statistics(...)` are repeated across multiple Ansible modules.
- FTD entity-type handling is centralized in `FTD_ENTITY_TYPES`, while ASA entity-type handling is still inlined across multiple CLI surfaces.

Integrated conclusion:
- These are all real drift multipliers.
- They are not equally urgent, but they are the main reason small behavioral changes are easy to apply to one family and forget elsewhere.

Code perspective:
- This is classic maintenance drag: duplicated helpers multiply bug-fix effort and increase the odds of partial refactors.

User perspective:
- Users eventually feel this as inconsistent feature behavior when one family gets a fix or enhancement and another similar family does not.

Recommended fix path:
- Consolidate one family at a time, starting with the highest-churn helpers:
  action-target selection, Ansible query-to-UID resolution, serializer helpers,
  then raw-response helpers and entity-type constants.

Sources integrated:
- Codex items 18, 19, 20, 21, 26
- Claude M8, M9

### 9. User-facing "not found" messages drift across surfaces

Status: Confirmed mismatch

Validated facts:
- Examples currently in the repo include:
  `Profile '{profile}' not found.`
  `Network object '{name}' not found.`
  `Network group with UID '{uid}' not found.`
  `{entity_name} with name '{name}' not found.`
  `Referenced object '{ref}' not found`
  with and without periods, and with different identifier styles.

Integrated conclusion:
- This is a real UX inconsistency.
- It is lower priority than the contract issues above, but it is visible and widespread.

Code perspective:
- Inconsistent wording makes tests weaker and reduces the value of shared helpers or reusable error handling patterns.

User perspective:
- Similar failures read differently depending on where they occur, which makes troubleshooting less clear and less polished.

Recommended fix path:
- Choose one message template family and centralize it in helpers where possible.

Sources integrated:
- Claude M7
- Codex item 25

### 10. Low-priority but valid convention drift

Status: Low-signal drift

Validated facts:
- Legacy typing syntax is mixed with newer style:
  `List[...]`, `Dict[...]`, and `Optional[...]` still appear in multiple core and CLI files.
- Frozen dataclass usage is mixed:
  many payload models are frozen, while several response/helper dataclasses and `sccfm_core/errors.py::SccApiError` are not.
- `from __future__ import annotations` is present in much of the repo but missing from several scripts, package files, and command/service files.
- Developer-facing scripts such as `scripts/build_ansible_collection.py` and `scripts/validate_regex.py` use bare `print()` and emoji/status text rather than the richer CLI output conventions used elsewhere.

Qualified conclusion:
- These are real convention mismatches.
- They are low priority because they do not currently break a public runtime contract by themselves.

Code perspective:
- These drifts make the codebase feel less uniform to maintainers and reduce the leverage of shared linting and style expectations.

User perspective:
- Direct user impact is low, but developer-facing scripts and outputs feel less cohesive than the main CLI experience.

Recommended fix path:
- Address these as opportunistic cleanup or in dedicated convention sweeps, not mixed into higher-risk behavioral changes unless already touching the same files.

Sources integrated:
- Claude M1, M2, M3, L1
- Gemini item 1, qualified downward

## 2. Rejected or not promoted findings

These claims were reviewed and not accepted into the consolidated backlog as-is.

### A. False positive: FTD `consoe` `NameError`

Result:
- Rejected.

Reason:
- The typo appears in
  `dev/inconsistency-findings/claude-inconsistencies.md`, but not in the
  current repo.
- The file now exists at `sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py`,
  and it correctly calls `_render_table(console=console, result=result)`.

### B. `sys.exit()` in `BaseCommand` is an inconsistency

Result:
- Rejected as an inconsistency finding.

Reason:
- This is a design critique of the current CLI error funnel, not drift between two repo surfaces.
- The repo currently implements this pattern deliberately in `sccfm_cli/commands/base.py`.

Original source:
- Gemini item 2

### C. Service `ValueError` handling causes raw Python tracebacks to leak from the CLI

Result:
- Rejected.

Reason:
- `BaseCommand._dispatch()` catches generic `Exception` and prints `[red]Error: {e}[/red]`; it does not dump raw Python tracebacks by default.
- There may still be exception taxonomy cleanup worth doing, but the specific claim about traceback leakage was not validated.

Original source:
- Gemini item 3

### D. `**kwargs` plus `cast()` in handlers is an inconsistency

Result:
- Rejected as an inconsistency finding.

Reason:
- This is the prevailing command-pattern design in the repo, not drift between sibling implementations.
- It may be arguable as an architecture critique, but it is not a clean repo inconsistency under the scope of this report.

Original source:
- Gemini item 4

### E. `NotFoundError` vs `None` contract drift as originally framed

Result:
- Not promoted as a standalone confirmed inconsistency.

Reason:
- The original claim mixed public getters, identifier resolvers, and raw helper methods.
- The getter-return-`None` vs mutator-raise-`NotFoundError` split mostly holds and appears intentional in the strongest cited examples.
- The more defensible, accepted issue is message-template drift, not a proven broken service contract.

Original source:
- Claude H3

### F. ASA vs FTD renderer signature divergence

Result:
- Not promoted.

Reason:
- The payload shapes differ for domain reasons, so the API-shape difference is not by itself a strong inconsistency finding.

Original source:
- Claude M5

### G. Other low-signal style claims not promoted

Result:
- Not promoted beyond low-priority notes.

Examples:
- mixed deep imports vs package exports
- file naming preference drift
- Ansible `notes:` / `seealso:` metadata shape
- parameter-fetch style drift
- test assertion style drift
- conftest organization concerns

Reason:
- These may still be worth standardizing eventually, but they did not meet the bar for substantive validated inconsistency findings in this consolidated pass.

## 3. Recommended order

This order is based on combined maintenance risk and user-facing inconsistency,
not just on internal code neatness.

1. Fix the region source-of-truth problem first.
2. Fix the Ansible collection contract drift next:
   `runtime.yml`, shared config helpers, structured error handling, check mode.
3. Normalize the CLI JSON output contract.
4. Align async timeout and polling policy.
5. Clean up naming/docs/path drift.
6. Treat coverage parity and helper duplication as structured follow-up work.

## 4. Output of this consolidation pass

What this file is intended to replace:
- ad hoc merging of `dev/inconsistency-findings/codex-inconsistencies.md`,
  `dev/inconsistency-findings/claude-inconsistencies.md`, and
  `dev/inconsistency-findings/gemini-inconsistencies.md`

What it is intended to preserve:
- strong findings from Codex
- valid refinements from Claude
- the one meaningful low-priority Gemini addition after validation

What it intentionally does not do:
- treat every model claim as true by default
- confuse checklist philosophy debates with actual cross-surface inconsistency
- overstate filename-parity heuristics as proven behavior gaps
