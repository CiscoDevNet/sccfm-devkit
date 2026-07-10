# claude-inconsistencies

Repo-wide inconsistency report derived from the
`dev/consistency-checklists/claude-consistency.md` checklist plus a follow-up
audit inspired by the
`dev/inconsistency-findings/codex-inconsistencies.md` findings.

Date: 2026-04-21

Companion files:
- `dev/consistency-checklists/claude-consistency.md` — the checklist of
  mechanisms (what *should* be consistent).
- `dev/inconsistency-findings/codex-inconsistencies.md` — independent findings
  (16 items) used as inspiration.
- This file — current-state report of things that are already inconsistent in the repo.

Severities used below:
- **High** — bug, runtime crash, or user-visible/UX risk.
- **Medium** — drift / future trap / inconsistent caller contract.
- **Low** — cosmetic / style / metadata / nitpick.

Each finding includes the canonical mechanism (from
`dev/consistency-checklists/claude-consistency.md`),
the expected behavior, the offending site(s), and a one-line fix.

> Items already covered exhaustively by
> `dev/inconsistency-findings/codex-inconsistencies.md` (region split,
> README `manager`/`managers`, timeout 300/3600/900 split, `.vault_pass.example`
> typo, local-user feature naming, ASA execute-CLI test path, `with_spinner`
> import, missing same-name Ansible tests/examples, e2e parity, device-target
> helper triplication, raw-response helper duplication, query-to-uid duplication,
> serializer duplication) are NOT re-listed here. See
> `dev/inconsistency-findings/codex-inconsistencies.md`.

---

## Pass 1 — Audit against `dev/consistency-checklists/claude-consistency.md`

### H1. JSON output uses `console.print(json.dumps(...))` instead of bare `print(...)`

- **Mechanism:** §3.1 — JSON branch must use bare `print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))`. `console.print` re-processes Rich escapes and corrupts machine-readable output.
- **Offending sites:**
  - [cisco_sccfm_cli/commands/base.py L72](cisco_sccfm_cli/commands/base.py#L72)
  - [cisco_sccfm_cli/commands/base.py L208](cisco_sccfm_cli/commands/base.py#L208)
  - [cisco_sccfm_cli/commands/policies/access_rule/create/command.py L208](cisco_sccfm_cli/commands/policies/access_rule/create/command.py#L208)
  - [cisco_sccfm_cli/commands/policies/access_rule/list/command.py L70](cisco_sccfm_cli/commands/policies/access_rule/list/command.py#L70)
  - [cisco_sccfm_cli/commands/inventory/devices/rendering.py L31](cisco_sccfm_cli/commands/inventory/devices/rendering.py#L31)
  - …~15 additional command files follow the same anti-pattern.
- **Severity:** **High**
- **Fix:** Replace every `self.console.print(json.dumps(...))` / `console.print(json.dumps(...))` in a JSON branch with bare `print(json.dumps(..., indent=2, ensure_ascii=False, default=str))`.

### M1. `List[X]` / `Dict[X, Y]` left over instead of PEP 585 lowercase generics

- **Mechanism:** §15.1 — use `list[X]`, `dict[K, V]`; never `typing.List` / `typing.Dict`.
- **Offending sites:**
  - [cisco_sccfm_core/utils/validation.py L3, L8](cisco_sccfm_core/utils/validation.py#L3)
  - [cisco_sccfm_cli/commands/base.py L7](cisco_sccfm_cli/commands/base.py#L7) and [L104, L111-112](cisco_sccfm_cli/commands/base.py#L104)
- **Severity:** **Medium**
- **Fix:** Migrate `List[X]` → `list[X]`, drop the `typing.List` import.

### M2. `Optional[...]` left over instead of `... | None`

- **Mechanism:** §15.1 — PEP 604 unions only.
- **Offending sites:**
  - [cisco_sccfm_core/services/transaction_service.py L2, L24](cisco_sccfm_core/services/transaction_service.py#L2)
- **Severity:** **Medium**
- **Fix:** Replace `Optional[Callable[[CdoTransaction], None]]` with `Callable[[CdoTransaction], None] | None`; remove `Optional` import.

### M3. Response dataclasses not `frozen=True`

- **Mechanism:** §5.1 — immutable payload/response dataclasses use `@dataclass(frozen=True)`.
- **Offending sites:**
  - [cisco_sccfm_core/errors.py L13](cisco_sccfm_core/errors.py#L13) — `SccApiError`
  - [cisco_sccfm_core/services/object_management/network_object_service.py L18, L63](cisco_sccfm_core/services/object_management/network_object_service.py#L18) — `NetworkObjectResponse`, `NetworkObjectListResponse`
  - [cisco_sccfm_core/services/object_management/object_override_service.py L22, L42, L67, L97, L126](cisco_sccfm_core/services/object_management/object_override_service.py#L22) — `ObjectTargetItem`, `ObjectTargetsResponse`, `ObjectOverridesResponse`, `ObjectRawOverride`, `ObjectOverride`
- **Severity:** **Medium**
- **Fix:** Add `frozen=True` to every payload/response dataclass.

### L1. Missing `from __future__ import annotations`

- **Mechanism:** §15.1 — every `.py` file starts with `from __future__ import annotations`.
- **Offending sites:**
  - [cisco_sccfm_scripts/build_ansible_collection.py](cisco_sccfm_scripts/build_ansible_collection.py)
  - [cisco_sccfm_scripts/validate_regex.py](cisco_sccfm_scripts/validate_regex.py)
  - [cisco_sccfm_scripts/_test_setup_tokens.py](cisco_sccfm_scripts/_test_setup_tokens.py)
  - [cisco_sccfm_core/__init__.py](cisco_sccfm_core/__init__.py)
- **Severity:** **Low**
- **Fix:** Add the import line directly after each shebang / at the top.

---

## Pass 2 — Findings inspired by
`dev/inconsistency-findings/codex-inconsistencies.md` (categories codex hinted
at, expanded)

### H2. **Live `NameError` typo** in FTD CLI result renderer

- **Mechanism:** §3.1 — every render call must reference an in-scope `console` parameter.
- **Offending site:** [cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py L21](cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py#L21)
  ```python
  _render_table(console=consoe, result=result)   # ← `consoe` is undefined
  ```
- **Impact:** Every non-JSON FTD bulk CLI render raises `NameError` at runtime. The JSON branch hides it; tests likely only cover JSON.
- **Severity:** **High**
- **Fix:** Rename `consoe` → `console`. Add a table-format test for FTD bulk CLI to prevent recurrence.

### H3. Services mix `raise NotFoundError` with `return None` for the same operation class

- **Mechanism:** §10 / §11.3 — getter methods use one contract; mutate/delete methods use another. Same-class methods inside one file should not mix.
- **Offending sites:**
  - [cisco_sccfm_core/services/policy/access_rule_service.py L273](cisco_sccfm_core/services/policy/access_rule_service.py#L273) raises
  - [cisco_sccfm_core/services/object_management/network_object_service.py L157, L161, L186](cisco_sccfm_core/services/object_management/network_object_service.py#L157) returns `None`
  - [cisco_sccfm_core/services/object_management/network_group_service.py L151](cisco_sccfm_core/services/object_management/network_group_service.py#L151) returns `None`, [L181](cisco_sccfm_core/services/object_management/network_group_service.py#L181) raises, [L593, L598](cisco_sccfm_core/services/object_management/network_group_service.py#L593) raises — all in one file
- **Severity:** **High** (callers can't write a single try/except contract)
- **Fix:** Establish: `get_*` returns `Optional[T]`; `delete_*`, `update_*`,
  identifier-resolution helpers raise `NotFoundError`. Refactor outliers and
  add a note in `dev/consistency-checklists/claude-consistency.md` §10.

### M4. Polling intervals diverge across long-running operations

- **Mechanism:** §7.1 — canonical `polling_interval_sec=10` in `TransactionService`; per-operation overrides should be justified.
- **Offending sites:**
  - Canonical: [cisco_sccfm_core/services/transaction_service.py L20](cisco_sccfm_core/services/transaction_service.py#L20) — `10`
  - [cisco_sccfm_core/services/inventory/asa_cli_service.py L42](cisco_sccfm_core/services/inventory/asa_cli_service.py#L42) — hardcoded `3`
  - [cisco_sccfm_core/services/inventory/asa_onboard_service.py L20](cisco_sccfm_core/services/inventory/asa_onboard_service.py#L20) — hardcoded `5`
  - [cisco_sccfm_core/services/inventory/ftd_onboard_service.py L20](cisco_sccfm_core/services/inventory/ftd_onboard_service.py#L20) — hardcoded `5`
  - [cisco_sccfm_core/services/inventory/ftd_ztp_onboard_service.py L20](cisco_sccfm_core/services/inventory/ftd_ztp_onboard_service.py#L20) — hardcoded `5`
- **Severity:** **Medium**
- **Fix:** Add named constants in `cisco_sccfm_core/constants.py` (`SHORT_POLL_INTERVAL_SEC`, `STANDARD_POLL_INTERVAL_SEC`) and use them; document the rationale per call site.

### M5. Renderer signatures diverge between ASA and FTD CLI families

- **Mechanism:** §3.1 / §18 — same operation should expose the same callable shape across families.
- **Offending sites:**
  - ASA: `render_cli_results(*, console, results: Sequence[CdoCliResult], uid_to_device, script, output_format)` — [cisco_sccfm_cli/commands/inventory/devices/asa/cli_result_renderer.py](cisco_sccfm_cli/commands/inventory/devices/asa/cli_result_renderer.py)
  - FTD: `render_ftd_cli_results(*, console, result: FtdBulkCliResult, output_format)` — [cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py L13](cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py#L13)
- **Impact:** Different parameter names, different result types, no shared protocol — refactors and shared logic are blocked.
- **Severity:** **Medium**
- **Fix:** Define a `CliResultRenderer` Protocol and adapt both families to it (e.g. `render(*, console, payload, output_format)`); push family-specific shaping into adapters.

### M6. Mixed package-level vs deep imports inside the same file

- **Mechanism:** §15.3 / §18 — pick one strategy per repo.
- **Offending site:**
  - [cisco_sccfm_cli/commands/base.py L16-L18](cisco_sccfm_cli/commands/base.py#L16) — `from cisco_sccfm_core import SccApiError` next to `from cisco_sccfm_core.models.cdo_transaction_status import CdoTransactionStatus` and `from cisco_sccfm_core.services.transaction_service import TransactionService`.
- **Severity:** **Medium**
- **Fix:** Decide policy. Recommendation: re-export commonly used symbols
  (`SccApiError`, `NotFoundError`, `CdoTransactionStatus`, key services) from
  `cisco_sccfm_core/__init__.py`; require deep imports only for rare types. Codify in
  `dev/consistency-checklists/claude-consistency.md` §15.3.

### M7. "Not found" message wording drift

- **Mechanism:** §10.3 — uniform tone and structure for user-facing errors.
- **Offending sites (sample):**
  - [cisco_sccfm_cli/commands/base.py L55](cisco_sccfm_cli/commands/base.py#L55) — `"Profile '{profile}' not found."`
  - [cisco_sccfm_core/services/policy/access_rule_service.py L273](cisco_sccfm_core/services/policy/access_rule_service.py#L273) — `"Network object '{name}' not found."`
  - [cisco_sccfm_core/services/object_management/network_group_service.py L181](cisco_sccfm_core/services/object_management/network_group_service.py#L181) — `"Network group with UID '{uid}' not found."`
  - [cisco_sccfm_core/services/object_management/network_group_service.py L593, L598](cisco_sccfm_core/services/object_management/network_group_service.py#L593) — `"Network object with UID '{ref}' not found."` / `"Network object with name '{ref}' not found."`
  - [cisco_sccfm_cli/commands/objects/utils.py L233](cisco_sccfm_cli/commands/objects/utils.py#L233) — `"Referenced object '{ref}' not found"` (no period)
- **Severity:** **Medium**
- **Fix:** Adopt one template: `"<Entity> with <id-kind> '<value>' not found."` with a trailing period. Centralize in a small helper (`format_not_found(entity, id_kind, value)`).

### M8. Per-module Ansible serializer helpers (in addition to codex-15/16)

- **Mechanism:** §14.2 — module-local helpers should live in `module_utils/` once they appear twice.
- **Offending sites (new beyond codex):**
  - [sccfm-ansible/plugins/modules/change_asa_boot_image.py L219](sccfm-ansible/plugins/modules/change_asa_boot_image.py#L219) — `_serialize_result`
  - [sccfm-ansible/plugins/modules/list_asa_disk_files.py L161](sccfm-ansible/plugins/modules/list_asa_disk_files.py#L161) — `_serialize_results`
  - [sccfm-ansible/plugins/modules/list_ftd_not_on_version.py L249](sccfm-ansible/plugins/modules/list_ftd_not_on_version.py#L249) — `_serialize_device`
  - [sccfm-ansible/plugins/modules/show_asa_shun.py L173](sccfm-ansible/plugins/modules/show_asa_shun.py#L173) — `_serialize_entries`, `_serialize_statistics`
- **Severity:** **Medium**
- **Fix:** Pull family-level serializers into `module_utils/asa_serializers.py` and `module_utils/ftd_serializers.py`. (Folds into codex item #16.)

### M9. Inline entity-type lists instead of `cisco_sccfm_core/constants.py`

- **Mechanism:** §20 — no magic strings/lists; family lists live in `constants.py`.
- **Offending sites:**
  - [cisco_sccfm_cli/commands/inventory/devices/rendering.py L74](cisco_sccfm_cli/commands/inventory/devices/rendering.py#L74) — inlines `[EntityType.ASA]`.
  - ASA / FTD `shared.py` files build entity-type filters inline rather than importing canonical lists.
- **Severity:** **Medium**
- **Fix:** Add `ASA_ENTITY_TYPES = [EntityType.ASA]` to `cisco_sccfm_core/constants.py` (alongside `FTD_ENTITY_TYPES`) and import everywhere.

### L2. `--limit` / `--offset` re-declared without `-l` / `-o` short flags

- **Mechanism:** §2.1 — always compose from `limit_option()` / `offset_option()` factories so short flags stay uniform.
- **Offending sites:**
  - [cisco_sccfm_cli/commands/policies/access_rule/list/command.py L18, L25](cisco_sccfm_cli/commands/policies/access_rule/list/command.py#L18) — declares `["--limit"]` / `["--offset"]` directly.
- **Severity:** **Low**
- **Fix:** Replace inline `click.Option(["--limit"], ...)` with `limit_option()` (and same for offset). Add a grep guard to pre-commit.

### L3. Service / helper file-naming convention drift

- **Mechanism:** §15.2 — file roles map to suffixes (`*_service.py`, `*_helper.py`, `shared.py`).
- **Offending sites:**
  - `cisco_sccfm_core/services/object_management/object_api_helper.py` and `cisco_sccfm_core/services/policy/policy_api_helper.py` use `_helper.py` while sibling files use `_service.py`.
  - `cisco_sccfm_cli/commands/inventory/devices/asa/shared.py` (per-family helpers) vs `cisco_sccfm_cli/commands/objects/utils.py` (per-domain helpers) — same role, different name.
- **Severity:** **Low**
- **Fix:** Pick one bucket per role and document in
  `dev/consistency-checklists/claude-consistency.md` §15.2 (`_service.py` for
  service classes, `_helper.py` for SDK/HTTP helpers, `shared.py` for
  per-feature shared CLI plumbing, `utils.py` reserved for stateless
  functions).

### L4. Ansible module metadata drift (`notes:` / `seealso:` / `short_description` style)

- **Mechanism:** §14.1 — uniform `DOCUMENTATION` shape per module.
- **Offending sites:** mixed presence/absence of `notes:` and `seealso:` blocks; mixed sentence-case vs verb-phrase `short_description` with/without trailing period (sample: [delete_network_group.py L47](sccfm-ansible/plugins/modules/delete_network_group.py#L47) has `notes:`; [create_network_group.py](sccfm-ansible/plugins/modules/create_network_group.py) does not).
- **Severity:** **Low**
- **Fix:** Define a doc fragment template; either add `notes:`/`seealso:` everywhere or drop everywhere; standardize `short_description` to "Verb [a/the] <thing> in SCC Firewall Manager" (no trailing period).

### L5. Ansible parameter-fetch style drift

- **Mechanism:** §14.2 — uniform `module.params` access pattern.
- **Offending sites:** some modules assign all params to typed locals at the top of `main()` (e.g. [trigger_ftd_upgrade.py L219](sccfm-ansible/plugins/modules/trigger_ftd_upgrade.py#L219)); others reach into `module.params.get(...)` inline throughout the body.
- **Severity:** **Low**
- **Fix:** Adopt: typed locals at the top of `main()` (cheap to type-check, easier to read).

### L6. Test assertion style drift (parsed-JSON vs `result.output` substring)

- **Mechanism:** §13.1 — same-class tests should assert the same way.
- **Offending sites (sample):**
  - parsed JSON: [cisco_sccfm_cli/commands/tests/inventory/devices/asa/smartlicense/test_smartlicense.py L478](cisco_sccfm_cli/commands/tests/inventory/devices/asa/smartlicense/test_smartlicense.py#L478)
  - substring: [cisco_sccfm_cli/commands/tests/objects/test_update_default.py L146](cisco_sccfm_cli/commands/tests/objects/test_update_default.py#L146), [cisco_sccfm_cli/commands/tests/policies/access_rule/test_access_rule.py L243-L244](cisco_sccfm_cli/commands/tests/policies/access_rule/test_access_rule.py#L243)
- **Severity:** **Low**
- **Fix:** Convention: success/payload assertions use parsed JSON via `--format json`; error-path assertions can use substring matches but should match against a known canonical phrase (ties into M7).

### L7. Conftest fixture organization

- **Mechanism:** §13.1 — root conftest exposes shared fixtures; nested conftests should extend, not shadow.
- **Offending sites (probable):** [cisco_sccfm_cli/commands/tests/conftest.py L50-L100](cisco_sccfm_cli/commands/tests/conftest.py#L50) defines `sample_devices`, `sample_managers`, `mock_inventory_service`, `default_config`, `config_path`. Need to confirm no nested conftest re-defines these with different return shapes.
- **Severity:** **Low** (verify before fixing)
- **Fix:** `find cisco_sccfm_cli cisco_sccfm_core -name conftest.py` and diff fixture surfaces; consolidate.

---

## Summary by category

| # | Category | Severity | Count |
|---|----------|----------|-------|
| H1 | JSON output via `console.print` | High | 1 (≥15 sites) |
| H2 | `NameError` in FTD renderer | High | 1 |
| H3 | NotFoundError vs `None` contract drift | High | 1 (3+ files) |
| M1 | `List[]` / `Dict[]` PEP 585 leftovers | Medium | 2 files |
| M2 | `Optional[]` PEP 604 leftover | Medium | 1 |
| M3 | Non-frozen response dataclasses | Medium | 7 |
| M4 | Polling-interval drift (3/5/10s) | Medium | 4 services |
| M5 | ASA/FTD renderer signature drift | Medium | 1 |
| M6 | Package vs deep import mixed in one file | Medium | 1 (representative) |
| M7 | "Not found" wording drift | Medium | 5+ sites |
| M8 | Ansible serializer helper duplication (new) | Medium | 4+ |
| M9 | Inline entity-type lists | Medium | 2+ |
| L1 | Missing `from __future__ import annotations` | Low | 4 |
| L2 | `--limit`/`--offset` short-flag drift | Low | 1+ |
| L3 | Service/helper file-naming drift | Low | repo-wide |
| L4 | Ansible doc metadata drift | Low | repo-wide |
| L5 | Ansible param-fetch style drift | Low | repo-wide |
| L6 | Test assertion style drift | Low | repo-wide |
| L7 | Conftest fixture organization | Low | needs verify |
| — | **Totals** | **High 3 / Medium 9 / Low 7** | 19 distinct findings |

---

## Recommended fix order

1. **H2** — fix `consoe` typo and add a table-format FTD CLI test.
2. **H1** — sweep the JSON branches; bare `print` everywhere.
3. **H3** — codify the get-vs-mutate exception contract; refactor the three offending services.
4. **M4** — name the polling intervals in `constants.py`; align onboard/CLI overrides.
5. **M1 / M2 / M3 / L1** — mechanical sweeps; can be one PR each or bundled.
6. **M5** — extract `CliResultRenderer` Protocol.
7. **M6 / M9** — re-export from `cisco_sccfm_core/__init__.py`, add `ASA_ENTITY_TYPES`.
8. **M7 / L2 / L3 / L4 / L5 / L6 / L7** — style / metadata sweeps with grep guards in pre-commit where possible.

---

## Pass 3 — Self-critique vs
`dev/inconsistency-findings/codex-inconsistencies.md` and new findings

This section reconciles my findings with codex's, argues the validity of each
of my own items, and adds new items surfaced by the comparison.

### A. Where codex was right and I was silent

I should have caught these in Pass 1/2; codex did. Verified independently:

- **Region vocabulary split** — confirmed:
  `_REGIONS = ("in", "au", "uae", "us", "eu", "apj", "int")` in
  [cisco_sccfm_cli/commands/configure.py L14](cisco_sccfm_cli/commands/configure.py#L14)
  vs `ALLOWED_REGIONS = ("int", "us", "eu", "apj", "aus", "uae", "in", "ci")`
  in [sccfm-ansible/plugins/module_utils/config.py L10](sccfm-ansible/plugins/module_utils/config.py#L10).
  Two real divergences: `au` (CLI) vs `aus` (Ansible), and `ci` is Ansible-only.
  See `dev/inconsistency-findings/codex-inconsistencies.md` §1.
- **README `managers` vs CLI `manager`** — confirmed at
  [README.md L35](README.md#L35) (`sccfm-cli inventory managers list`); CLI group
  is `manager`. See `dev/inconsistency-findings/codex-inconsistencies.md` §3.
- **Timeout default split (300 / 3600 / 900)** — distinct from my **M4**
  (polling interval). This is the *total* `--timeout` default, not the poll
  cadence. See `dev/inconsistency-findings/codex-inconsistencies.md` §4.
  **Adding as N1 below.**
- Coverage parity gaps (codex §9–§12), `with_spinner` import style (§7),
  `.vault_pass.example` typo (§8), local-user feature naming (§5), ASA
  execute-CLI test path (§6), device-target/raw-response/query-uid duplication
  (§13–§16) — I deferred to codex; still deferring.

### B. Where I should downgrade or qualify my own findings

- **H1 — JSON via `console.print`**: still real, but the practical impact
  depends on Rich's highlighter. With the default `Console()` settings Rich
  applies syntax highlighting to JSON-looking strings on a TTY and emits ANSI;
  on non-TTY pipes the ANSI is suppressed but markup-like substrings (`[bold]`)
  are still parsed. **Downgrade to Medium** in cases where the payload cannot
  contain `[…]`-like substrings; **keep High** for [base.py L72](cisco_sccfm_cli/commands/base.py#L72)
  (error JSON — error bodies can contain anything).
- **M5 — ASA vs FTD renderer signatures**: partially explained by the SDK
  (FTD bulk endpoint returns one aggregated object; ASA returns per-device
  results). The *signature* divergence is real, but the divergence has a
  domain reason. **Downgrade to Low** unless we extract a unifying Protocol;
  document the rationale in §3.1.
- **M6 — mixed package-level vs deep imports in one file**: this is endemic
  in modern Python; only worth fixing once `cisco_sccfm_core/__init__.py` formally
  re-exports. **Downgrade to Low** until that policy lands.
- **L7 — conftest fixture organization**: still unverified.
  **Demoting to "open question"** until confirmed (see N5).

### C. Where I disagree with codex (mild)

- Codex §9–§12 (same-name coverage parity) uses filename parity as the
  signal. That heuristic over-counts: a single test file can legitimately
  cover several modules (e.g. `test_network_object_lifecycle.py` covers
  `create_/update_/delete_/list_network_object`). The real question is
  **behavioral coverage**, not filename parity. Suggest reframing codex
  §9–§12 as "coverage audit needed" rather than 40+ discrete items.
- Codex §4 example mentions ASA module *example* shows `timeout: 900` as a
  third value — that's a documentation example value, not a default. It
  illustrates inconsistency in *docs*, not code; flagging is correct, but
  the severity is documentation-level (Low), not contract-level.

### D. New findings surfaced by the comparison

#### N1. `--timeout` default split (300 / 3600) — distinct from M4

- **Mechanism:** §2.1 (shared `timeout_option(default=3600)`) / §7.1
  (service default `timeout_sec=300`).
- **Sites:**
  - Service default: [cisco_sccfm_core/services/transaction_service.py](cisco_sccfm_core/services/transaction_service.py) — `timeout_sec=300`.
  - CLI factory: [cisco_sccfm_cli/commands/shared_options.py](cisco_sccfm_cli/commands/shared_options.py) `timeout_option(default=3600)`.
  - Ansible ASA trigger: `timeout=300` in code, `timeout: 900` in EXAMPLES
    (see codex §4).
  - Ansible FTD trigger: `timeout=3600`.
- **Severity:** **Medium**
- **Fix:** Promote to a single named constant
  (`DEFAULT_TRANSACTION_TIMEOUT_SEC`) in `cisco_sccfm_core/constants.py`; reference
  from CLI factory, services, and Ansible modules. Distinct from M4 (poll
  cadence).

#### N2. `_REGIONS` is a CLI-local tuple, not imported from `cisco_sccfm_core/constants.py`

- **Mechanism:** §20 — no magic strings/lists outside `constants.py`.
- **Site:** [cisco_sccfm_cli/commands/configure.py L14](cisco_sccfm_cli/commands/configure.py#L14)
  defines `_REGIONS` directly.
- **Severity:** **Medium** (root cause of codex §1: there is no shared list).
- **Fix:** Move the canonical region tuple into `cisco_sccfm_core/constants.py`
  (`SCCFM_REGIONS`); import from CLI, Ansible `Config`, README generator.
  This single change collapses codex §1 + codex §2 + my N2.

#### N3. `_REGIONS` ordering and casing inconsistent with Ansible `ALLOWED_REGIONS`

- **Mechanism:** §10.3 / §22 — surfaces should advertise the same vocabulary
  in the same order so `--help` and Ansible error messages line up.
- **Sites:** ordering differs (`("in","au","uae","us","eu","apj","int")` vs
  `("int","us","eu","apj","aus","uae","in","ci")`) and the spellings differ
  (`au` vs `aus`).
- **Severity:** **Low** (cosmetic on top of N2, but worth fixing in the same
  PR).
- **Fix:** When introducing the shared tuple in N2, pick one canonical order
  and one canonical spelling per region. Recommend `aus` (matches `apj`,
  `uae`, `int` length convention).

#### N4. Region `Choice` is `case_sensitive=False` in CLI but Ansible compares case-sensitively

- **Mechanism:** §9.1 / §9.2 — config validation parity.
- **Sites:**
  - CLI: [cisco_sccfm_cli/commands/configure.py L52](cisco_sccfm_cli/commands/configure.py#L52)
    uses `click.Choice(_REGIONS, case_sensitive=False)`.
  - Ansible: [sccfm-ansible/plugins/module_utils/config.py L48](sccfm-ansible/plugins/module_utils/config.py#L48)
    uses `if self.region not in ALLOWED_REGIONS:` — exact-match only.
- **Severity:** **Medium** (`SCCFM_REGION=US` works for the CLI, fails in
  Ansible).
- **Fix:** Lowercase the region in `Config.__post_init__` before validation;
  document on `dev/consistency-checklists/claude-consistency.md` §9.

#### N5. `conftest.py` audit (L7 follow-up)

- Action item, not a finding yet: run
  `find cisco_sccfm_cli cisco_sccfm_core sccfm-ansible -name conftest.py` and diff
  `@pytest.fixture` names. Carry over from L7.

#### N6. `print(json.dumps(...))` is used in service code, not just CLI

- **Mechanism:** §4.1 — services do not perform IO; only CLI/Ansible render.
- **Sites:** verified in
  [cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py L38](cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py#L38)
  the renderer prints directly via `print(json.dumps(...))` (correct per H1)
  but renderers live in the CLI tree, so this is fine. **Spot-check core
  services for any stray `print(...)` calls** as part of the H1 sweep.
- **Severity:** **Low** (audit task, may yield zero or many).

### E. Severity adjustments after critique

| ID | Old | New | Reason |
|----|-----|-----|--------|
| H1 | High | High (error path) / Medium (success path) | Rich highlighter risk varies by payload contents |
| M5 | Medium | Low | Divergence has a domain reason; document instead of refactor |
| M6 | Medium | Low | Endemic; pending re-export policy |
| L7 | Low | Open | Unverified; tracked as N5 |
| **N1** | — | Medium | New: `--timeout` default split distinct from M4 |
| **N2** | — | Medium | New: `_REGIONS` not in `constants.py` (root cause of codex §1) |
| **N3** | — | Low | New: region ordering/spelling drift |
| **N4** | — | Medium | New: case-sensitivity mismatch CLI vs Ansible |
| **N5** | — | Open | New: conftest audit task |
| **N6** | — | Low | New: spot-check `print(...)` in services |

### F. Updated total

- Original Pass 1 + 2: **19** findings (3 H / 9 M / 7 L).
- After Pass 3 critique: **3 H / 7 M / 9 L / 2 Open** = **21** findings.
- Plus codex's 16 = **37** distinct repo-wide consistency items tracked
  across both reports (with overlaps explicitly noted).

---

## Pass 4 — Re-comparison after codex updated their report

`codex-inconsistencies` was substantially expanded (from 16 to 26 items) and
now includes a "Cross-model adjudication against
`dev/inconsistency-findings/claude-inconsistencies.md`"
section that critiques my findings. This pass:

1. Pushes back where codex got my findings wrong.
2. Concedes where codex's critique is fair.
3. Imports codex's newly added findings (§9–§13) that I missed in Pass 1/2.

### G. Pushback on codex's critique of my findings

#### G.1 Codex's "H2 (`consoe` typo) is a false positive" — **WRONG**

Codex claims: *"I could not find that typo in the repo; it appears only inside
`dev/inconsistency-findings/claude-inconsistencies.md`."*

This is incorrect. Re-verified at
[cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py L21](cisco_sccfm_cli/commands/inventory/devices/cdfmc_managed_ftd/cli_result_renderer.py#L21):

```python
def render_ftd_cli_results(
    *,
    console: Console,
    result: FtdBulkCliResult,
    output_format: str,
) -> None:
    if output_format == "json":
        _render_json(result=result)
        return
    _render_table(console=consoe, result=result)   # ← line 21
```

The function parameter is `console`; the call passes `consoe`. This is a live
`NameError` on every non-JSON FTD bulk CLI render. **H2 stands at High
severity.** Codex appears to have grepped only their own report file or to
have queried a stale snapshot.

#### G.2 Codex's "H3 (NotFoundError vs None drift) is overstated" — **partial concession**

Codex's critique: *"The cited examples mix public getters, identifier
resolvers, and raw helper methods. There may still be design cleanup to do,
but I do not consider the cited set a clean confirmed inconsistency."*

Fair point. My H3 conflated three different method classes. Reframing:

- **Real drift inside one file**:
  [cisco_sccfm_core/services/object_management/network_group_service.py](cisco_sccfm_core/services/object_management/network_group_service.py)
  uses `return None` at L151 (getter) and `raise NotFoundError` at L181
  (delete) — that's the documented pattern (getters return `None`, mutators
  raise) and is **fine**.
- **What I should have flagged**: the absence of any documented contract.
  Today it's accidental that the right pattern obtains in most places.
  **Downgrade H3 to Medium**: the action item is "document the contract in
  `dev/consistency-checklists/claude-consistency.md` §10 and audit
  identifier-resolver helpers", not
  "refactor everything".

#### G.3 Codex's "M5 (renderer signature divergence) not promoted" — **conceded**

Already self-downgraded to Low in Pass 3 §B. No change.

#### G.4 Codex's "low-signal style drift (typing/dataclass/__future__)" — **partial pushback**

Codex bundles M1, M2, M3, L1 into "low-signal convention drift". I disagree
on **M3 (non-frozen response dataclasses)**: `SccApiError` and the response
models are passed across thread/module boundaries and are documented as
immutable in `dev/consistency-checklists/claude-consistency.md` §5.1. A
non-frozen `SccApiError` is one
`object.__setattr__` away from breaking the contract. **Keep M3 at Medium.**

The other three (M1/M2/L1) are cosmetic — concede they're Low.

### H. Codex's new findings (§9–§13, §22–§26) — adopted

These are valid and I missed them in Pass 1/2. Verified each one independently:

#### H.1 Action group `cisco.sccfm.all` is incomplete (codex §9) — **VERIFIED**

`sccfm-ansible/meta/runtime.yml` lists **36** modules in
`action_groups.cisco.sccfm.all`; the modules directory contains **46** module
`.py` files. The missing 10 (verified):
`add_network_group_members`, `create_access_rule`, `delete_access_rule`,
`get_access_group`, `get_access_rule`, `list_access_groups`,
`list_access_rules`, `onboard_cdfmc_ftd_ztp`,
`remove_network_group_members`, `update_access_rule`.

Several of those omitted modules document `module_defaults: group/cisco.sccfm.all`
in their EXAMPLES — the example will not work as advertised.

- **Mechanism:** §14.3 (every new module joins `cisco.sccfm.all`).
- **Severity:** **High** (documented behavior is silently false).
- **Fix:** Add the 10 missing modules to `runtime.yml`, or remove the broken
  `module_defaults` example blocks. Add a CI check that lists `plugins/modules/*.py`
  and diffs against the action group.
- **Adopted as N7.**

#### H.2 `module_defaults` example coverage is uneven (codex §10) — **VERIFIED**

15 modules omit a `module_defaults` example block. Already implied by my §14.1
checklist; codex enumerated the offenders.

- **Severity:** **Low** (documentation parity).
- **Fix:** Backfill once the action group is fixed (N7).
- **Adopted as N8.**

#### H.3 `base_argument_spec()` / `create_config(module)` not used by all modules (codex §11) — **VERIFIED**

`grep -L "base_argument_spec" plugins/modules/*.py` returns 9 modules
(plus `__init__`):
`change_asa_local_password.py`, `execute_asa_cli.py`, `list_asa_boot_registry.py`,
`list_asa_compatible_versions.py`, `list_asa_disk_files.py`,
`list_asa_local_users.py`, `list_ftd_compatible_versions.py`, `onboard_asa.py`,
`trigger_ftd_upgrade.py`.

Several of these hand-roll `region` / `api_token` and call `Config(...)`
directly, bypassing the env-fallback contract documented in §9.2.

- **Mechanism:** §14.2 (every module uses `base_argument_spec()` + `create_config(module)`).
- **Severity:** **High** (env fallback and `no_log` discipline can drift per
  module; `SCCFM_REGION` / `SCCFM_API_TOKEN` semantics are not guaranteed).
- **Fix:** Migrate all 9 modules to the shared helpers; add a pre-commit check.
- **Adopted as N9.**

#### H.4 `supports_check_mode` not declared on 14 modules (codex §12) — **VERIFIED**

`grep -L "supports_check_mode" plugins/modules/*.py` returns 14 modules.
Notably, **all of the omitting modules are read-only or shun operations**
(`add_asa_shun`, `asa_ha_check`, `clear_asa_shun`, `execute_asa_cli`, every
`list_*`, `remove_asa_shun`, `show_asa_shun`, `change_asa_local_password`).

This **directly contradicts** my Pass 1 statement that "All sampled modules
have `supports_check_mode=True`" — that was a sampling error.

- **Mechanism:** §14.2 (every module sets `supports_check_mode=True`).
- **Severity:** **Medium** (read-only modules don't mutate, but `--check` still
  surfaces inconsistent behavior; mutating `add_asa_shun`/`remove_asa_shun`/
  `clear_asa_shun` are the real risk).
- **Fix:** Add `supports_check_mode=True` to all 14; for the three shun
  mutators implement a real check-mode path.
- **Adopted as N10.**

#### H.5 Ansible error handling split (codex §13) — **VERIFIED**

23 modules catch only generic `Exception` and call
`module.fail_json(msg=str(e))`, bypassing
`SccApiError.from_exception(e).to_dict()`. Affected: every `*_network_*`
CRUD, every `*_access_*` and `*_object_override_*` module.

This means `error_code`, `error_details`, and `status_code` keys promised by
`dev/consistency-checklists/claude-consistency.md` §10.1 are missing from those
modules' failure payloads.

- **Mechanism:** §10.3 (`module.fail_json(**SccApiError.from_exception(e).to_dict())`).
- **Severity:** **High** (broken failure contract for ~half the modules).
- **Fix:** Replace generic try/except with the canonical pattern; reserve
  generic `Exception` for non-SDK failures only.
- **Adopted as N11.**

#### H.6 Codex §22 strengthens my H1

Codex reframed my H1 to also include **drift in `json.dumps` kwargs** (some
sites pass `ensure_ascii=False`, some pass `default=str`, some neither).
Adopting this expansion under H1.

- **Action item added to H1**: standardize on
  `print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))` and
  factor it into a tiny `print_json(payload)` helper in `cisco_sccfm_cli/utils/`.

#### H.7 Codex §23 strengthens my L2

Codex confirmed the same drift in
[cisco_sccfm_cli/commands/policies/access_group/list/command.py](cisco_sccfm_cli/commands/policies/access_group/list/command.py)
not just access_rule. Updating L2's site list.

#### H.8 Codex §25 finds an additional "not found" wording site I missed

Codex pointed at
[cisco_sccfm_core/services/object_management/utils.py](cisco_sccfm_core/services/object_management/utils.py)
template `"{entity_name} with name '{name}' not found."`. Adding to M7.

### I. Updated counts

| Pass | High | Medium | Low | Open | New total |
|------|------|--------|-----|------|-----------|
| Pass 1+2 | 3 | 9 | 7 | 0 | 19 |
| Pass 3 (after self-critique) | 3 | 7 | 9 | 2 | 21 |
| Pass 4 (after codex re-comparison) | **5** | **9** | **9** | **2** | **25** |

Pass 4 net change:
- **+3 High**: N7 (action group), N9 (base_argument_spec adoption), N11 (Ansible error handling).
- **+1 Medium**: N10 (supports_check_mode parity).
- **+1 Low**: N8 (module_defaults example parity).
- H3 downgraded High → Medium (codex's critique conceded).
- M3 retained at Medium (pushback on codex's "low-signal" framing).
- H2 retained at High (pushback on codex's false-positive claim — verified twice).

Combined with codex's 26 items, the joint backlog is now ~45 distinct
consistency findings (overlaps deduplicated where both reports cite the
same site).
