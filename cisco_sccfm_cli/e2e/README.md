# sccfm-cli E2E Integration Tests

Tenant-backed integration tests for the `sccfm-cli` binary.  The suite mirrors `sccfm-ansible/e2e/` 1:1 so the same scenarios are exercised through both surfaces.

## Structure

- `run_e2e.sh`: installs the package (so `sccfm-cli` is on `$PATH`) and runs pytest with JUnit output for Jenkins.  When `ASA_HOST` and `VASA_PASSWORD` are set, also onboards a CLI-dedicated vASA via `playbooks/onboard_vasa.yml` before pytest and removes it afterward via `playbooks/remove_vasa.yml`.
- `playbooks/onboard_vasa.yml` / `playbooks/remove_vasa.yml`: Ansible playbooks that mirror their `sccfm-ansible/e2e/asa/` counterparts but use the `ci-e2e-cli-asa-` name prefix so the CLI suite owns its own device.  The shared-device approach (a single `ci-e2e-asa-*` vASA) leaves the device NOT_SYNCED after the Ansible suite mutates it, which then blocks ASA CLI script pushes from this suite.
- `conftest.py`: top-level suite ordering (`objects` → `asa` → `access_rules` → `ftd`) plus the session-scoped `e2e_profile` fixture that decodes the Ansible vault and writes a temp `sccfm-cli` profile.
- `_runner.py`: `run_cli(...)` subprocess wrapper — the analog of Ansible's `run_playbook()`.  Asserts on rc, parses `--format json` stdout, and supports `expect_failure` / `tolerate_any_rc` for idempotency and cleanup paths.
- `_profile.py`: bootstraps credentials by shelling out to `ansible-vault view` and writing a temp profile via `ConfigService.save()`. Reuses `examples/group_vars/all/vault.yml` from the Ansible suite — one source of truth.
- `_phases.py`: `PhaseCase` dataclass + `PhaseTracker` (skip-on-failed-deps, identical semantics to the Ansible suite).
- `_state.py`: in-process cross-phase data store (replaces the `/tmp/ci_*_uid` files used by the Ansible suite).
- Per-suite directories (`objects/`, `access_rules/`, `asa/`, `ftd/`):
  - `conftest.py`: declares the suite's `lifecycle_cleanup` (autouse, session-scoped).
  - `test_*.py`: pytest test files; each collected test case maps to one lifecycle phase.
  - `phases/*.py`: one Python module per phase, each exposing a single `run(ctx)`.  The 1:1 naming with the Ansible playbooks makes the layout review side-by-side.
  - `phases/test_data.py`: shared test data (single source of truth across all phases in the suite).

## Why This Shape

- Jenkins gets one test case per lifecycle phase instead of one large pass/fail result.
- Phases shell out to the installed `sccfm-cli` entrypoint, so the suite exercises argv parsing, exit codes, and stdout/stderr the way real users see them — exactly the contract that unit tests with `CliRunner` skip.
- Test data per suite lives in one file (`phases/test_data.py`), reducing drift between create / verify / update / delete phases.
- Credentials reuse the Ansible suite's vault (`cisco_sccfm_scripts/setup_tokens.py`).  One CI bootstrap, two test surfaces.

## Prerequisites

1. Run the credential bootstrap once:

   ```
   poetry run change-tokens
   ```

   This creates `sccfm-ansible/examples/.vault_pass` and an encrypted `vault.yml`. Both files are
   Git-ignored and excluded from collection artifacts.

2. Install dev dependencies so `ansible-vault` is available for the runner to decode the vault:

   ```
   poetry install --with dev
   ```

3. (CI only) Provision a CLI-dedicated vASA and export `ASA_HOST` + `VASA_PASSWORD`.  `run_e2e.sh` will onboard it as `ci-e2e-cli-asa-<host>` and remove it on exit.  When these vars are unset the script skips onboarding and tests run against any existing `ci-e2e-cli-asa-*` device.

## Running

Full suite (no onboarding — uses an existing `ci-e2e-cli-asa-*` device):

```
./cisco_sccfm_cli/e2e/run_e2e.sh
```

Full suite with onboarding (CI flow):

```
ASA_HOST=10.0.0.42 VASA_PASSWORD=<pw> ./cisco_sccfm_cli/e2e/run_e2e.sh
```

A single suite:

```
poetry run pytest cisco_sccfm_cli/e2e/objects -v
poetry run pytest cisco_sccfm_cli/e2e/access_rules -v
poetry run pytest cisco_sccfm_cli/e2e/asa -v
poetry run pytest cisco_sccfm_cli/e2e/ftd -v
```

A single phase (parametrize id matches the phase name):

```
poetry run pytest "cisco_sccfm_cli/e2e/objects/test_network_object_lifecycle.py::TestNetworkObjectLifecycle::test_object_phase[create]" -v
poetry run pytest cisco_sccfm_cli/e2e/access_rules -v -k verify_create
```

JUnit output is written to `results/ci-cli-tests.xml` for Jenkins to ingest.  The default `poetry run pytest` lane (no path) skips this directory via `norecursedirs` in `pyproject.toml`.

## Opt-in upgrade phases

The ASA and FTD upgrade-staging phases are skipped unless an explicit version is provided.  Mirrors the Ansible suite's vASA-disabled comments — vASA cannot fetch upgrade images from CDO CloudFront.  To enable:

```
SCCFM_E2E_ASA_UPGRADE_SOFTWARE_VERSION=9.6.4 SCCFM_E2E_ASA_UPGRADE_ASDM_VERSION=7.9.1 ./cisco_sccfm_cli/e2e/run_e2e.sh
SCCFM_E2E_FTD_UPGRADE_SOFTWARE_VERSION=7.4.2 ./cisco_sccfm_cli/e2e/run_e2e.sh
```
