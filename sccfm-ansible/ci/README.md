# Ansible CI Integration Tests

This directory contains the tenant-backed integration tests for the Ansible collection.

## Structure

- `run_ci.sh`: installs the local `cisco.sccfm` collection and runs pytest with JUnit output for Jenkins.
- `test_network_object_lifecycle.py`: pytest orchestration layer. Each collected test case maps to one lifecycle phase.
- `playbooks/*.yml`: focused playbooks for each phase so failures are isolated and easy to read in Jenkins.
- `playbooks/vars/test_data.yml`: shared test data used across all lifecycle phases.
- `conftest.py`: shared playbook execution and session cleanup logic.

## Why This Shape

- Jenkins gets one test case per lifecycle phase instead of one large pass/fail result.
- The test data lives in one file, which reduces drift between create, verify, update, and delete phases.
- The runner and playbook execution use the Poetry-managed environment, which keeps local and CI toolchains aligned.

## Running

Run the full integration suite with:

```bash
bash sccfm-ansible/ci/run_ci.sh
```

JUnit output is written to `results/ci-ansible-tests.xml` for Jenkins to ingest.