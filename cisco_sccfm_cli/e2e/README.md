<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [sccfm-cli E2E Integration Tests](#sccfm-cli-e2e-integration-tests)
  - [Structure](#structure)
  - [Why This Shape](#why-this-shape)
  - [Prerequisites](#prerequisites)
  - [Running](#running)
  - [FTD configure-manager registration suite](#ftd-configure-manager-registration-suite)
  - [Opt-in upgrade phases](#opt-in-upgrade-phases)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# sccfm-cli E2E Integration Tests

Tenant-backed integration tests for the `sccfm-cli` binary.  The suite mirrors `sccfm-ansible/e2e/` 1:1 so the same scenarios are exercised through both surfaces.

## Structure

- `run_e2e.sh`: installs the package (so `sccfm-cli` is on `$PATH`) and runs pytest with JUnit output for Jenkins.  When `ASA_HOST` and `VASA_PASSWORD` are set, also onboards a CLI-dedicated vASA via `playbooks/onboard_vasa.yml` before pytest and removes it afterward via `playbooks/remove_vasa.yml`.
- `playbooks/onboard_vasa.yml` / `playbooks/remove_vasa.yml`: Ansible playbooks that mirror their `sccfm-ansible/e2e/asa/` counterparts but use the `ci-e2e-cli-asa-` name prefix so the CLI suite owns its own device.  The shared-device approach (a single `ci-e2e-asa-*` vASA) leaves the device NOT_SYNCED after the Ansible suite mutates it, which then blocks ASA CLI script pushes from this suite.
- `conftest.py`: top-level suite ordering (`objects` → `asa` → `access_rules` → `ftd`) plus the session-scoped `e2e_profile` fixture that decodes the Ansible vault and writes a temp `sccfm-cli` profile.
- `_runner.py`: `run_cli(...)` subprocess wrapper — the analog of Ansible's `run_playbook()`.  Asserts on rc, parses `--format json` stdout, and supports `expect_failure` / `tolerate_any_rc` for idempotency and cleanup paths.
- `_profile.py`: bootstraps credentials by shelling out to `ansible-vault view` and writing a temp profile via `ConfigService.save()`.  Reuses `examples/group_vars/all/vault.yml` from the Ansible suite — one source of truth.
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

   This creates `sccfm-ansible/examples/.vault_pass` and an encrypted `vault.yml`.

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

## FTD configure-manager registration suite

`ftd/test_ftd_registration.py` exercises the full onboarding path against one
dedicated persistent FTD (CI: `10.10.1.231`):

1. `onboard` — create the SCCFM record, capture the one-time CLI key (kept only
   in process state and passed to the CLI via `SCCFM_FTD_CLI_KEY`, never argv)
   and the pre-registration `NOT_SYNCED` config state.
2. `configure_manager` — `cdfmc-managed-ftd configure-manager` SSHes in and pastes the key.
3. `verify_registration` — polls until the device is `ONLINE` **and** its config
   state has moved off `NOT_SYNCED`.

The suite's `lifecycle_cleanup` fixture deletes the reserved `ci-e2e-cli-ftd-*`
record and clears the manager off the appliance over SSH (`configure manager
delete`) before and after the run — so with the Ansible suite it runs four times
per pipeline.  Cleanup refuses to run unless `SCCFM_E2E_FTD_MANAGER_DELETE_HOST`
matches `FTD_HOST` exactly, guarding against wiping an arbitrary appliance.

It is skipped unless these are set (Jenkins injects them):

```
FTD_HOST=10.10.1.231            # management IP of the persistent FTD
FTD_PERFORMANCE_TIER=FTDv5      # virtual FTD tier
SCCFM_FTD_PASSWORD=<ssh pw>     # FTD SSH password (also used by cleanup)
SCCFM_E2E_FTD_MANAGER_DELETE_HOST=10.10.1.231   # must equal FTD_HOST
# The access policy is resolved from the tenant's cdFMC automatically. Override
# with FMC_ACCESS_POLICY_UID=<uuid>, or FMC_ACCESS_POLICY_NAME=<name> to pick one
# by name when the cdFMC has several (default requires exactly one).
# optional: FTD_PORT, FTD_USER, FTD_JUMP_HOST, FTD_SSH_TIMEOUT, SCCFM_E2E_CDFMC_QUERY,
#           FTD_REGISTRATION_RETRIES, FTD_REGISTRATION_DELAY, FTD_CLEANUP_RETRIES
# set SCCFM_E2E_REQUIRE_FTD_REGISTRATION=1 to fail (not skip) on missing inputs
```

## Opt-in upgrade phases

The ASA and FTD upgrade-staging phases are skipped unless an explicit version is provided.  Mirrors the Ansible suite's vASA-disabled comments — vASA cannot fetch upgrade images from CDO CloudFront.  To enable:

```
SCCFM_E2E_ASA_UPGRADE_SOFTWARE_VERSION=9.6.4 SCCFM_E2E_ASA_UPGRADE_ASDM_VERSION=7.9.1 ./cisco_sccfm_cli/e2e/run_e2e.sh
SCCFM_E2E_FTD_UPGRADE_SOFTWARE_VERSION=7.4.2 ./cisco_sccfm_cli/e2e/run_e2e.sh
```
