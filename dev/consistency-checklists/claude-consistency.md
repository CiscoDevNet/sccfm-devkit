# Consistency Review Checklist — SCCFM Devkit

**Survey date:** 2026-04-21
**Scope:** `cisco_sccfm_cli/`, `cisco_sccfm_core/`, `sccfm-ansible/`, `cisco_sccfm_scripts/`, `pyproject.toml`, build configs
**Purpose:** Catalog every recurring mechanism in the repo so future PRs can be reviewed for consistency. When a PR modifies one instance of a mechanism listed below, the reviewer should audit all other instances and either move them together or explicitly justify the divergence.

> Convention used in this doc:
> - **Canonical**: where the mechanism is defined / the reference implementation.
> - **Appears in**: known sites that follow (or must follow) the same pattern.
> - **Invariants**: the rules a PR must preserve.
> - **Drift risks**: what tends to go wrong if instances diverge.

---

## 1. CLI Command Pattern

### 1.1 `BaseCommand` lifecycle
- **Canonical:** [cisco_sccfm_cli/commands/base.py](cisco_sccfm_cli/commands/base.py)
- **Appears in:** every leaf command (e.g. [status.py](cisco_sccfm_cli/commands/status.py), [transaction.py](cisco_sccfm_cli/commands/transaction.py), [configure.py](cisco_sccfm_cli/commands/configure.py)) and every group command (e.g. `inventory/command.py`, `objects/command.py`, `policies/command.py`, `inventory/devices/asa/command.py`, `inventory/devices/ftd/command.py`, `inventory/devices/cdfmc_managed_ftd/command.py`).
- **Invariants:**
  - Subclass `BaseCommand`; implement `name`, `help_text`, `handle(ctx, **kwargs)`, and `build_params()`.
  - `handle()` always receives a `click.Context` and `**kwargs`.
  - All CLI errors funnel through `_dispatch()`; never catch `ApiException` ad-hoc in `handle()`.
  - Exit codes: `-1` unhandled exception, `130` KeyboardInterrupt, `1` failed transaction with `--wait`, `0` success.
  - Group commands fail with `ctx.fail("Specify a subcommand: ...")` when invoked without one.
- **Drift risks:** ad-hoc try/except in handlers, inconsistent exit codes, missing subcommand-fail-through.

### 1.2 Command registration
- **Canonical:** [cisco_sccfm_cli/cli.py](cisco_sccfm_cli/cli.py) `_build_commands()`; group commands store children in `_subcommands` and wire them in `build()`.
- **Invariants:**
  - Top-level commands are explicit (no auto-discovery).
  - Each group command exposes the same `register(group)` / `build()` shape.
  - Sub-trees mirror the directory layout (one `command.py` per group).

### 1.3 `_dispatch()` error funnel
- **Canonical:** `BaseCommand._dispatch` in [base.py](cisco_sccfm_cli/commands/base.py).
- **Invariants:**
  - `ApiException` → `SccApiError.from_exception()` → JSON or table format honoring `--format`.
  - `click.ClickException`, `click.Abort`, `click.exceptions.Exit` re-raised untouched.
  - `KeyboardInterrupt` → `sys.exit(130)`.
  - Generic `Exception` → red `[red]Error: ...[/red]` then `sys.exit(-1)`.
  - JSON error payloads use `print_json(...)` and include the original API error body when available.

---

## 2. Click Options & Shared Option Factories

### 2.1 Global shared options
- **Canonical:** [cisco_sccfm_cli/commands/shared_options.py](cisco_sccfm_cli/commands/shared_options.py)
- **Functions and contracts:**
  - `format_option()` → `--format`, `Choice(["table","json"])`, default `"table"`, case-insensitive.
  - `config_path_option()` → `--config-path`, envvar `SCCFM_CONFIG`, resolved `Path`.
  - `wait_option()` → `--wait/--no-wait`, default `False`, `show_default=True`.
  - `timeout_option(default=3600)` → `--timeout`, `IntRange(min=1)`, seconds.
  - `limit_option()` → `--limit/-l`, `IntRange(1, 200)`, default `50`.
  - `offset_option()` → `--offset/-o`, `IntRange(min=0)`, default `0`.
- **Invariants:**
  - Never re-declare these options inline; always call the factory.
  - JSON/table choice is the **only** value accepted for `--format`, repo-wide.
  - Pagination ranges (`1–200` / `0+`) are uniform across every list command.

### 2.2 Inventory option group
- **Canonical:** `cisco_sccfm_cli/commands/inventory/options.py` — `query_option(help_text=None)` and `inventory_list_params()`.
- **Invariants:**
  - All inventory `list` commands compose from `inventory_list_params()`; never hand-roll.
  - `--query` help text always references "Lucene Query Syntax".

### 2.3 Device filter options (ASA / FTD / cdFMC)
- **Canonical:** `cisco_sccfm_cli/commands/inventory/devices/asa/shared.py` and `.../ftd/shared.py`.
- **Appears in:** every ASA and FTD subcommand that targets devices (upgrade, CLI execution, shun, password, deploy, etc.).
- **Invariants:**
  - Mutually exclusive: exactly one of `--device-name`, `--query`, `--device-uids`.
  - `--device-uids` is `multiple=True`.
  - `--device-name` supports wildcards (`branch-*`).
  - Default help text strings come from the `_DEFAULT_DEVICE_*_HELP` constants in each `shared.py`; do not duplicate strings inline.
  - ASA and FTD filters use the canonical device-type constants from `cisco_sccfm_core/constants.py`.
- **Drift risks:** mutual-exclusion checks getting out of sync between ASA and FTD families.

### 2.4 Boolean / confirmation flags
- **Invariants:**
  - Boolean flags use `is_flag=True`, `default=False`, `show_default=True`.
  - Destructive commands gate on `--yes` / `--force` and/or a Questionary confirm prompt.
  - `--silent` (when present) flows through `ctx.obj["silent"]` and is honored by `with_spinner`.

---

## 3. Console / Output Rendering

### 3.1 Table vs JSON branching
- **Canonical examples:**
  - [cisco_sccfm_cli/commands/inventory/devices/rendering.py](cisco_sccfm_cli/commands/inventory/devices/rendering.py)
  - `cisco_sccfm_cli/commands/inventory/devices/asa/cli_result_renderer.py`
  - [cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py](cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py)
  - All `objects/` and `policies/` list/get commands.
- **Invariants:**
  - JSON branch uses `print_json(payload)` from `cisco_sccfm_cli/utils/json_output.py` — **not** `console.print` (Rich would re-process escapes).
  - Table branch uses `rich.table.Table(title=..., show_lines=True)` with explicit column styles (`cyan` for identifiers, `magenta`/`green` for state, `dim` for muted).
  - List renderers always emit `Number of entries:` and `Page: X / Y` before the table.
- **Drift risks:** `console.print(json.dumps(...))` corrupting JSON for downstream tooling.

### 3.2 Spinner usage
- **Canonical:** [cisco_sccfm_cli/utils/spinner.py](cisco_sccfm_cli/utils/spinner.py) — `@with_spinner("...")`.
- **Invariants:**
  - Decorator respects `ctx.obj.get("silent", False)`.
  - Spinner text must be operation-specific (`"Fetching ASA devices..."`, not `"Working..."`).
  - For long-running polls (transactions), use `Live(spinner, console=stderr_console, refresh_per_second=10, transient=True)`.

### 3.3 Stderr vs stdout discipline
- **Invariants:**
  - Status/spinner/progress chatter goes to **stderr** (`stderr_console`), keeping stdout machine-parseable.
  - JSON output goes to stdout via `print_json(...)`.
- **Drift risks:** one command leaking spinner text to stdout corrupts downstream pipes.

### 3.4 Success / warning / error coloring
- **Invariants:**
  - Success: `[green]✓[/green] ...`.
  - Warning: `[yellow]...[/yellow]`.
  - Error: `[red]Error: ...[/red]`.
  - Identifiers (UID, name) shown in `[bold]` or `[cyan]`; muted hints in `[dim]`.

---

## 4. Service Layer (`cisco_sccfm_core`)

### 4.1 Service constructor signature
- **Canonical:** `cisco_sccfm_core/services/**/*_service.py`.
- **Invariants:**
  - `def __init__(self, config: ConfigLike) -> None:`
  - Build the SDK API client once via `ApiClientFactory().build(config)`; store as `self.api`.
  - No logging in services — visibility is the caller's job.
  - Compose helper services through the constructor; **never** module-level singletons.
  - Exceptions propagate; do not swallow `ApiException`.

### 4.2 `ApiClientFactory`
- **Canonical:** [cisco_sccfm_core/factories/api_client_factory.py](cisco_sccfm_core/factories/api_client_factory.py)
- **Invariants:**
  - Sole producer of SDK `ApiClient` instances; nothing instantiates `ApiClient` directly.
  - Region/token resolution lives only here (and in the parallel Ansible `Config`).

### 4.3 API helpers (raw response handling)
- **Canonical:** `cisco_sccfm_core/services/object_management/object_api_helper.py`, `cisco_sccfm_core/services/policy/policy_api_helper.py`.
- **Invariants:**
  - One helper per API surface.
  - `read_raw_response(response)` → decode → `raise_for_status(status, body)` → `json.loads`.
  - `check_raw_response(response)` for empty bodies.
  - All raw-HTTP usage flows through these helpers; never decode bodies inline in services.

### 4.4 `ConfigLike` Protocol
- **Invariants:** Service constructors accept the Protocol, never the concrete `Config` class. New services must accept `ConfigLike`.

---

## 5. Models & Dataclasses

### 5.1 Frozen dataclass + `from_dict` / `to_dict`
- **Canonical:** `cisco_sccfm_core/models/*.py`, `cisco_sccfm_cli/models/config.py`, `sccfm-ansible/plugins/module_utils/config.py`.
- **Invariants:**
  - `@dataclass(frozen=True)` for immutable payloads/configs.
  - Type hints on every field; mutable defaults via `field(default_factory=...)`.
  - Validation in `__post_init__` only.
  - `from_dict()` defends against missing keys with sensible defaults (`""`, `None`, `[]`).
  - `to_dict()` serializes every field used by JSON output / Ansible result.

### 5.2 List-response wrapper shape
- **Invariants:** `count`, `items`, `limit`, `offset` — same field names everywhere (network objects, network groups, access rules, devices…).

---

## 6. Parsers (ASA CLI text → models)

### 6.1 Parser function signature
- **Canonical:** `cisco_sccfm_core/parsers/asa_*_parser.py`.
- **Invariants:**
  - `parse_<entity>(raw_text: str, ...) -> <Model>` returns a typed dataclass, never a dict.
  - Regexes compiled at module level with `re.compile(..., re.IGNORECASE | re.MULTILINE)` as appropriate.
  - Robust to missing fields — return defaults, do not raise.
  - Docstring describes the expected `show ...` command output.
  - Helper `_extract(pattern, text, default)` (or equivalent) for safe group access.

### 6.2 Parser ↔ model ↔ test triple
- **Invariants:** every parser has (1) a model in `cisco_sccfm_core/models/`, (2) a test in `cisco_sccfm_core/tests/test_<parser>.py` with realistic CLI fixtures.

---

## 7. Transactions & Long-Running Operations

### 7.1 `TransactionService.wait_for_transaction_to_finish`
- **Canonical:** [cisco_sccfm_core/services/transaction_service.py](cisco_sccfm_core/services/transaction_service.py)
- **Invariants:**
  - Default `polling_interval_sec=10`, `timeout_sec=3600` from `cisco_sccfm_core/constants.py`.
  - Terminal states: `DONE`, `ERROR`, `CANCELLED`.
  - Optional `on_poll(transaction)` callback before/after each poll.
  - Raises `TimeoutError` on timeout.

### 7.2 CLI `wait_for_transaction` helper on `BaseCommand`
- **Canonical:** `BaseCommand.wait_for_transaction` in [base.py](cisco_sccfm_cli/commands/base.py).
- **Invariants:**
  - Honors `--wait`; returns immediately when `False`.
  - Spinner text via `Live(..., console=stderr_console, transient=True)`.
  - Updates spinner text from `on_poll` callback (`f"Status: {t.cdo_transaction_status}"`).
  - Calls `is_failed_transaction()` and `print_failed_transaction_details()` / `print_submitted_transaction()` for the user-facing report.
  - Mutation commands exit `1` if `wait=True` and transaction failed.

### 7.3 Submitted-transaction summary
- **Invariants:** Always print transaction UID + polling URL when a mutation enqueues work, even without `--wait`.

---

## 8. Device Target Selection

### 8.1 Filter dataclass
- **Canonical:** `AsaDeviceFilters`, `FtdDeviceFilters` in `inventory/devices/{asa,ftd}/shared.py`.
- **Invariants:** frozen dataclass with `device_name | query | device_uids | limit | offset` mirrored across families.

### 8.2 `resolve_<family>_targets_from_kwargs`
- **Invariants:**
  - Returns `<Family>DeviceTargets(devices, uid_to_device, device_uids)`.
  - UID lookup uses `uid:{uid}` Lucene syntax; name uses `name:{name}` with wildcards.
  - Always validates mutual exclusivity via `_validate_<family>_device_filters` and `ctx.fail(...)`.

### 8.3 `report_check_targets`
- **Canonical:** `inventory/devices/{asa,ftd}/shared.py`.
- **Invariants:**
  - JSON payload: `{ "operation": ..., "can_proceed": bool, "reason": ..., "matched_devices": int, "devices": [{"name","uid","device_type"}] }`.
  - Table: identical columns across families.
  - Used by every `--check` / dry-run target preview.

---

## 9. Configuration & Authentication

### 9.1 CLI profile loading
- **Canonical:** `BaseCommand.get_profile`, [cisco_sccfm_cli/services/config_service.py](cisco_sccfm_cli/services/config_service.py), [cisco_sccfm_cli/models/config.py](cisco_sccfm_cli/models/config.py).
- **Invariants:**
  - Global `--profile` (default `"default"`).
  - `--config-path` env var `SCCFM_CONFIG`; default `~/.sccfm-cli/config.json`.
  - Missing-profile error always references `sccfm-cli --profile {profile} configure`.
  - Region stored lowercase.

### 9.2 Ansible `Config`
- **Canonical:** [sccfm-ansible/plugins/module_utils/config.py](sccfm-ansible/plugins/module_utils/config.py).
- **Invariants:**
  - Frozen dataclass validates values resolved from the canonical profile store.
  - Allowed regions: `int, us, eu, apj, au, uae, in, ci` (`aus` is a legacy alias normalized to `au`).
  - `base_argument_spec()` returns `profile` + `config_path`.
  - `create_config(module)` wraps validation in try/except → `module.fail_json(msg=...)`.

### 9.3 Configuration path override
- **Canonical override:** `SCCFM_CONFIG`.
- **Invariants:** SCCFM region and token values come only from named profiles.

---

## 10. Errors

### 10.1 `SccApiError`
- **Canonical:** [cisco_sccfm_core/errors.py](cisco_sccfm_core/errors.py).
- **Invariants:**
  - `from_exception(ApiException)` parses `errorMsg`, `errorCode`, `details`, `status_code` out of JSON body; falls back to `str(exc)`.
  - `to_dict()` returns the exact keys Ansible expects: `msg`, `error_code`, `error_details`, `status_code`.
  - Used by both CLI `_dispatch` and Ansible modules.

### 10.2 `NotFoundError`
- **Invariants:** raised by services when an identifier resolves to nothing; CLI converts to readable message; Ansible converts via `module.fail_json(msg=str(e))`.

### 10.3 Error message tone
- **Invariants:** include the affected identifier (`"Network object 'foo' not found."`), include a remediation hint when reasonable, never leak raw stack traces in user-facing output.

---

## 11. Idempotency & Mutation Semantics

### 11.1 Delete idempotency
- **Canonical:** `run_delete_with_idempotency` in [sccfm-ansible/plugins/module_utils/operations.py](sccfm-ansible/plugins/module_utils/operations.py).
- **Invariants:**
  - Missing object → `changed=False`, no error.
  - `check_mode` verifies existence without mutating.
  - Successful delete → `changed=True` and the deleted UID in result.

### 11.2 Update detection
- **Canonical:** `fields_need_update` in `operations.py`; mirrored field-comparison helpers in services.
- **Invariants:**
  - Compare desired vs current field-by-field (with list sorting where order is irrelevant).
  - No-op updates skip the API call and report `changed=False`.

### 11.3 Identifier resolution (`uid` vs `name`)
- **Canonical:** `cisco_sccfm_core/services/object_management/utils.py::resolve_uid` and the `identifier_argument_spec()` helper on the Ansible side.
- **Invariants:**
  - Exactly one of `uid` or `name` (mutually exclusive, one required).
  - Name resolves via `get_by_name_fn`; UID optionally verified via `get_by_uid_fn`.
  - Raises `NotFoundError` when not found.

### 11.4 UUID-vs-name detection
- **Pattern:** `try: uuid.UUID(s)` → treat as UID; on `ValueError` treat as name. Used by lookup helpers in object/policy services.

---

## 12. Pagination

- **Canonical:** [cisco_sccfm_cli/commands/inventory/devices/rendering.py](cisco_sccfm_cli/commands/inventory/devices/rendering.py).
- **Invariants:**
  - List responses expose `count`, `items`, `limit`, `offset`.
  - Renderers compute `current_page = (offset // limit) + 1`, `total_pages = max(1, ceil(count/limit))`.
  - CLI emits `Number of entries: N` then `Page: X / Y` before the table.
  - Default `limit=50`, `offset=0`; max `limit=200`.

---

## 13. Tests

### 13.1 CLI test layout
- **Canonical:** `cisco_sccfm_cli/commands/tests/`, `cisco_sccfm_cli/services/tests/`.
- **Invariants:**
  - `cli_runner` (`click.testing.CliRunner`) fixture.
  - `config_path` + `default_config` fixtures for profile setup; uses `tmp_path` and `monkeypatch` for `SCCFM_CONFIG`.
  - Service stubs via `monkeypatch` against `__init__` to avoid real SDK calls.
  - Assertions on `result.exit_code` and `result.output`.

### 13.2 Core test layout
- **Canonical:** `cisco_sccfm_core/tests/`.
- **Invariants:** mock SDK API client, parametrize edge cases, parser tests use realistic CLI fixture strings.

### 13.3 Ansible E2E phase pattern
- **Canonical:** `sccfm-ansible/e2e/asa/test_asa_shun_lifecycle.py`, runner `sccfm-ansible/e2e/run_e2e.sh`.
- **Invariants:**
  - `PhaseCase(name, playbook, depends_on)` frozen dataclass.
  - Phases ordered: create → idempotency → verify → update → delete.
  - Later phases skip if dependencies failed (`_skip_if_dependencies_incomplete`).
  - Each phase parameterized with `pytest.mark.parametrize(... ids=lambda c: c.name)`.

### 13.4 Pytest markers
- **Invariants:** `@pytest.mark.ci` for CI-runnable tests; phase name surfaces via `ids=`. Don't add new markers without registering them in `pyproject.toml`.

---

## 14. Ansible Modules

### 14.1 Module skeleton
- **Canonical:** [sccfm-ansible/plugins/modules/execute_asa_cli.py](sccfm-ansible/plugins/modules/execute_asa_cli.py), [sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py](sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py), and the rest of `plugins/modules/`.
- **Invariants:**
  - `DOCUMENTATION` lists every option with `description`, `type`, `required`, and default; shared auth options are `profile` and `config_path`.
  - `EXAMPLES` includes a direct call **and** a `module_defaults` (`group/cisco.sccfm.all`) example.
  - `RETURN` documents `changed`, `result`, and (on failure) `msg`/`error_code`/`error_details`/`status_code`.
  - `author: Cisco SCCFM Team`.
  - `main()` builds `argument_spec={**base_argument_spec(), ...}`, sets `supports_check_mode=True`.
  - On exception: `error = SccApiError.from_exception(e); module.fail_json(**error.to_dict())`.
  - Result dict always includes `changed: bool`.

### 14.2 `module_utils` helpers
- **Canonical:** [sccfm-ansible/plugins/module_utils/config.py](sccfm-ansible/plugins/module_utils/config.py), `operations.py`.
- **Invariants:**
  - `base_argument_spec()`, `identifier_argument_spec()`, `create_config(module)` reused by every module — no inline duplicates.
  - `fetch_object_by_identifier`, `run_delete_with_idempotency`, `fields_need_update` reused for object/group CRUD.

### 14.3 Action group
- **Canonical:** `cisco.sccfm.all` group declared in `meta/runtime.yml`.
- **Invariants:** every new module is added to this action group so `module_defaults` works repo-wide.

### 14.4 Inventory plugin
- **Canonical:** `sccfm-ansible/plugins/inventory/sccfm.py`.
- **Invariants:**
  - Host vars: `sccfm_uid`, `sccfm_name`, `sccfm_region`, `sccfm_device_type`, `connectivity_state`, `config_state`, `software_version`.
  - Devices grouped by type (`ASA`, `CDFMC_MANAGED_FTD`, …).
  - Uses the same `Config`/env fallback as modules.

---

## 15. Code Style

### 15.1 Type hints
- **Invariants:**
  - `from __future__ import annotations` at top of every file.
  - Every parameter and return type annotated.
  - Use `X | None` (PEP 604), not `Optional[X]`; use `|` unions, not `Union[...]`.
  - Protocols (`ConfigLike`) for duck typing.
  - mypy strict for both `cisco_sccfm_cli` and `cisco_sccfm_core`; `py.typed` ships in both.

### 15.2 File / symbol naming
- **Invariants:**
  - Files: `snake_case.py`. CLI command files use `command.py` for groups, leaf-name files for leaves (`create.py`, `update.py`, `list.py`, `delete.py`, `trigger.py`).
  - Helper files: `shared.py`, `utils.py`, `*_renderer.py`, `*_parser.py`, `*_service.py`, `*_helper.py`.
  - Classes `PascalCase`, functions/vars `snake_case`, constants `UPPER_SNAKE`, private with leading `_`.

### 15.3 Imports & formatting
- **Invariants:**
  - Black, line length 100, target Python 3.12.
  - isort profile `black`; order: future, stdlib, third-party, local (`sccfm_*`).
  - Pre-commit enforces black, isort, flake8, mypy, commitizen, doctoc.

### 15.4 Docstrings
- **Invariants:** one-line summary, blank line, optional Args/Returns/Raises; backticks for code references; no Sphinx-only directives.

### 15.5 No long methods / no AI slop (per `AGENTS.md`)
- **Invariants:** keep methods short, factor helpers liberally, no speculative abstractions, every line typed.

---

## 16. Tooling, Build, CI

### 16.1 Poetry / `pyproject.toml`
- **Invariants:**
  - Dependencies added via `poetry add`; dev deps in `[tool.poetry.group.dev.dependencies]`.
  - Entry points: `sccfm-cli`, `sccfm-cli-interactive`, `build-ansible-collection`.
  - Tool configs (black, isort, mypy, pytest, coverage) all live in `pyproject.toml`.

### 16.2 Pre-commit
- **Invariants:** every contributor runs the same hooks; CI re-runs them. Don't disable hooks per-file without a comment justifying it.

### 16.3 PyInstaller spec
- **Canonical:** [sccfm-cli.spec](sccfm-cli.spec).
- **Invariants:** updated when adding new modules or data files needed by the bundled CLI.

### 16.4 Commitizen / CHANGELOG
- **Invariants:**
  - Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, …); breaking changes use `!`.
  - `cz` drives version bumps and `CHANGELOG.md` updates; do not edit version strings by hand.

### 16.5 Helper scripts
- **Canonical:** `cisco_sccfm_scripts/` (`interactive_cli.py`, `setup_environment.sh`, `setup_ci_environment.sh`, `import_legacy_vault.py`, `build_ansible_collection.py`, `cz.sh`).
- **Invariants:** any new repo-wide automation lives in `cisco_sccfm_scripts/` and is exposed via `pyproject.toml` entry points where it's user-facing.

---

## 17. Questionary Prompts

- **Canonical:** `cisco_sccfm_core/services/profile_service.py` and `cisco_sccfm_cli/commands/configure.py`.
- **Invariants:**
  - Use `.unsafe_ask()` (sync API) — never the async variant.
  - `confirm()` for yes/no with explicit `default`.
  - `select()` for fixed choices; `text()` for free input.
  - Print contextual explanation **before** the prompt.

---

## 18. Directory Structure & Cross-Layer Mirroring

### 18.1 Layer mirroring
- **Invariants:**
  - `cisco_sccfm_core/services/inventory/*` ↔ `cisco_sccfm_cli/commands/inventory/**` ↔ `sccfm-ansible/plugins/modules/*` (inventory & device ops).
  - `cisco_sccfm_core/services/object_management/*` ↔ `cisco_sccfm_cli/commands/objects/**` ↔ `sccfm-ansible/plugins/modules/*_network_*`.
  - `cisco_sccfm_core/services/policy/*` ↔ `cisco_sccfm_cli/commands/policies/**` ↔ (planned) Ansible policy modules.
  - New service ⇒ matching CLI command + Ansible module + e2e playbook + tests in all three layers.

### 18.2 Per-feature folder layout
- **Invariants:** each CLI feature folder contains `command.py` (group) + leaf command files + optional `shared.py`, `options.py`, `*_renderer.py`. Don't flatten into single files.

---

## 19. Special / Cross-Cutting Patterns

### 19.1 `warnings.catch_warnings` to silence Pydantic noise
- **Canonical:** `cisco_sccfm_core/services/object_management/network_group_service.py`.
- **Invariants:** scoped via context manager, with a comment explaining the SDK warning being suppressed.

### 19.2 `cast(...)` for kwargs unpacked from Click
- **Invariants:** every `kwargs.get("...")` retrieved inside `handle()` is `cast()`-ed to the expected type; mypy strict relies on this.

### 19.3 `Sequence[click.Parameter]` return for `build_params()`
- **Invariants:** never return `list[Option]` directly; preserve the `Sequence` protocol so subclasses stay covariant.

---

## 20. Constants & Enums

- **Canonical:** [cisco_sccfm_core/constants.py](cisco_sccfm_core/constants.py).
- **Invariants:**
  - `ASA_ENTITY_TYPES`, `FTD_ENTITY_TYPES`, `FTD_LICENSES`, `FTDV_PERFORMANCE_TIERS`, etc. defined once.
  - No magic strings/lists in command/service code — import from `constants.py`.
  - SDK enums (`EntityType`, `CdoTransactionStatus`, …) referenced by enum, not stringly.

---

## 21. Versioning, Changelog, Docs

### 21.1 Version & changelog
- **Invariants:** managed by commitizen; never edit version manually; CHANGELOG groups Added/Changed/Fixed/Deprecated/Removed/Security.

### 21.2 README/INSTALL
- **Invariants:**
  - TOC maintained by doctoc.
  - Examples cover CLI, Ansible direct, Ansible `module_defaults`, and e2e.
  - Region vocabulary identical across docs.
  - `sccfm-ansible/README.md` mirrors collection-specific docs.

---

## 22. Local Development Files

- **Invariants:**
  - SCCFM credentials are not configured through project `.env` files.
  - Profile files are owner-only and never committed.
  - `dev-commands.local.txt` is a developer scratchpad; don't reference it from production code.

---

## 23. Licensing

- **Invariants:**
  - MIT license (root `LICENSE`, `pyproject.toml`, `sccfm-ansible/galaxy.yml`).
  - No per-file headers; the root LICENSE governs.

---

## 24. PR Reviewer Quick-Check (use as a literal checklist)

- [ ] **Command pattern:** new commands subclass `BaseCommand`, route errors through `_dispatch`, set the right exit codes.
- [ ] **Shared options:** uses factories from `shared_options.py` (and family `shared.py`) instead of inline `click.Option(...)`.
- [ ] **Output:** JSON via `print(json.dumps(..., indent=2, ensure_ascii=False, default=str))`; tables via Rich; status to stderr.
- [ ] **Spinner:** `with_spinner` for sync work; `Live(... transient=True, console=stderr_console)` for transaction polling.
- [ ] **Service constructor:** `(self, config: ConfigLike)`; uses `ApiClientFactory().build(config)`.
- [ ] **Error handling:** `ApiException` → `SccApiError.from_exception(e).to_dict()` for Ansible; `_dispatch` for CLI; `NotFoundError` for missing entities.
- [ ] **Idempotency:** delete/update/create paths use the canonical helpers and respect `check_mode` / `--check`.
- [ ] **Identifier resolution:** uid xor name enforced; resolved via `resolve_uid` / `identifier_argument_spec`.
- [ ] **Pagination:** `--limit` 1–200 (default 50), `--offset` ≥0 (default 0); response shape `count/items/limit/offset`.
- [ ] **Transactions:** poll via `TransactionService`; honor `--wait` / `--timeout`; print UID + URL even without `--wait`; exit `1` on failed wait.
- [ ] **Device targets:** ASA/FTD filters mutually exclusive; `report_check_targets` JSON shape unchanged.
- [ ] **Profiles:** uses the shared `ProfileService`; optional path override is `SCCFM_CONFIG`.
- [ ] **Models:** `@dataclass(frozen=True)`, full type hints, `from_dict`/`to_dict` defaults.
- [ ] **Parsers:** module-level compiled regexes, return typed model, defensive on missing fields, accompanied by tests with real CLI fixtures.
- [ ] **Ansible module:** `base_argument_spec()` merged, `supports_check_mode=True`, `module_defaults` example present, action group `cisco.sccfm.all`, full `RETURN` docs.
- [ ] **E2E:** new lifecycle phases follow create → idempotency → verify → update → delete, with `depends_on` skipping.
- [ ] **Tests:** CLI test uses `cli_runner` + monkeypatched services; core test mocks SDK; parser test has realistic fixture.
- [ ] **Style:** `from __future__ import annotations`, PEP 604 unions, no untyped code, files under `command.py` / `shared.py` / `*_renderer.py` / `*_parser.py` / `*_service.py` naming.
- [ ] **Cross-layer:** new capability lands in core service + CLI command + Ansible module + docs + examples + tests.
- [ ] **Constants:** no magic strings; new shared values added to `cisco_sccfm_core/constants.py`.
- [ ] **Commits:** conventional-commit prefixes; CHANGELOG handled by `cz`, not by hand.
