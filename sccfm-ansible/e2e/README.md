<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Ansible E2E Integration Tests](#ansible-e2e-integration-tests)
  - [Structure](#structure)
  - [Why This Shape](#why-this-shape)
  - [Running](#running)
  - [FTD configure-manager registration suite](#ftd-configure-manager-registration-suite)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Ansible E2E Integration Tests

This directory contains the tenant-backed integration tests for the Ansible collection.

## Structure

- `run_e2e.sh`: installs the local `cisco.sccfm` collection and runs pytest with JUnit output for Jenkins.
- `objects/test_network_object_lifecycle.py`: pytest orchestration layer. Each collected test case maps to one lifecycle phase.
- `objects/playbooks/*.yml`: focused playbooks for each phase so failures are isolated and easy to read in Jenkins.
- `objects/playbooks/vars/test_data.yml`: shared test data used across all lifecycle phases.
- `objects/conftest.py`: shared playbook execution and session cleanup logic.

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

## FTD configure-manager registration suite

`ftd/test_ftd_registration.py` drives the full onboarding path against one
dedicated persistent FTD (CI: `10.10.1.231`) with focused playbooks:

- `onboard_and_configure_ftd.yml` — onboards the reserved `ci-e2e-ansible-ftd-*`
  device, records its pre-registration `NOT_SYNCED` state, then registers it over
  SSH with `cisco.sccfm.configure_manager` (keeping the one-time key in one
  playbook so it never lands on disk).
- `verify_ftd_registration.yml` — polls until the device is `ONLINE` **and** its
  config state has moved off the recorded `NOT_SYNCED` value.

The suite's `lifecycle_cleanup` fixture deletes the record and clears the
manager off the appliance over SSH (`configure manager delete`) before and after
the run. Skipped unless `FTD_HOST`, `FTD_PERFORMANCE_TIER`, and
`SCCFM_FTD_PASSWORD` are set; the SSH cleanup also requires
`SCCFM_E2E_FTD_MANAGER_DELETE_HOST` to equal `FTD_HOST`. The FMC access policy is
resolved from the tenant's cdFMC automatically — override with
`FMC_ACCESS_POLICY_UID`, or `FMC_ACCESS_POLICY_NAME` to pick one by name. Set
`SCCFM_E2E_REQUIRE_FTD_REGISTRATION=1` to fail rather than skip on missing
inputs.
