<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Ansible E2E Integration Tests](#ansible-e2e-integration-tests)
  - [Structure](#structure)
  - [Why This Shape](#why-this-shape)
  - [Running](#running)
  - [FTD registration inputs](#ftd-registration-inputs)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Ansible E2E Integration Tests

This directory contains the tenant-backed integration tests for the Ansible collection.

## Structure

- `run_e2e.sh`: installs the local `cisco.sccfm` collection and runs pytest with JUnit output for Jenkins.
- `objects/test_network_object_lifecycle.py`: pytest orchestration layer. Each collected test case maps to one lifecycle phase.
- `objects/playbooks/*.yml`: focused playbooks for each phase so failures are isolated and easy to read in Jenkins.
- `objects/playbooks/vars/test_data.yml`: shared test data used across all lifecycle phases.
- `objects/conftest.py`: shared playbook execution and session cleanup logic.
- `ftd/test_ftd_registration.py`: complete cdFMC-managed FTD registration through
  `onboard_cdfmc_ftd`, direct SSH `configure_manager`, and an `ONLINE` state check.

## Why This Shape

- Jenkins gets one test case per lifecycle phase instead of one large pass/fail result.
- The test data lives in one file, which reduces drift between create, verify, update, and delete phases.
- The runner and playbook execution use the Poetry-managed environment, which keeps local and CI toolchains aligned.

## Running

Run the full integration suite with:

```
 sccfm-ansible/e2e/run_e2e.sh
```

JUnit output is written to `results/ci-ansible-tests.xml` for Jenkins to ingest.

## FTD registration inputs

The registration phases are skipped unless CI provides a dedicated persistent
FTD and all required values:

- `FTD_HOST`, `FMC_ACCESS_POLICY_UID`, and `FTD_PERFORMANCE_TIER`
- `SCCFM_FTD_PASSWORD` through a secret environment binding

Optional overrides are `FTD_USER` (default `admin`), `FTD_PORT` (default `22`),
`FTD_JUMP_HOST`, `SCCFM_JUMP_PASSWORD`, and `FTD_SSH_TIMEOUT`. Ansible and CLI
run sequentially against the same appliance. Their lifecycle cleanup runs
`configure manager delete` over SSH before and after each suite, then removes
the reserved SCCFM record. Cleanup is refused unless
`SCCFM_E2E_FTD_MANAGER_DELETE_HOST` exactly matches `FTD_HOST`. CI also sets
`SCCFM_E2E_REQUIRE_FTD_REGISTRATION=1` so missing inputs fail the job instead of
silently skipping the registration phases.
