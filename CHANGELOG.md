## v0.39.4 (2026-08-24)

### Fix

- **lh-114517**: harden public release verification

## v0.39.3 (2026-08-19)

### Fix

- **lh-114527**: prepare Ansible changelog for 0.39.3
- **lh-114527**: repair developer setup and Ansible guidance

## v0.39.2 (2026-08-19)

### Fix

- **lh-114358**: publish the interactive customer CLI

## v0.39.1 (2026-08-19)

### Fix

- **lh-102436**: honor keyword-only object lookups
- **lh-102436**: prepare first ansible release metadata
- **lh-102436**: vault ansible e2e device password
- **lh-102436**: make ansible sanity checks pass
- **lh-102436**: align network group service conventions
- **lh-102436**: align network object service conventions
- **lh-102436**: resolve generated documentation conflicts
- **lh-102436**: integrate profile workflow with release
- **lh-102436**: correct gitleaks module path
- **lh-102436**: address release review feedback
- **lh-102436**: proper release
- **lh-102436**: fix doc styling
- **lh-102436**: use repository secrets for publishing
- **lh-102436**: close remaining release blockers
- **lh-102436**: use current vault key in CLI E2E
- **lh-102436**: harden release and credential workflows
- **lh-102436**: add manual build-once release workflow
- **lh-102436**: stabilizes the final package metadata and README
- **lh-102436**: poetry run in venv
- **lh-102436**: Galaxy metadata/runtime issues
- **lh-102436**: make the Galaxy artifact independently installable and usable.
- **lh-102436**: remove tests and e2e files from pypi wheel
- **lh-102436**: query correct distribution name
- **lh-102436**: unresolved runtime dependency
- **lh-102436**: hide api-token
- **lh-102436**: install resolves a broken SDK
- **lh-102436**: hide smart licensing token
- **lh-102436**: Inventory plugin remove exports of the API token

## v0.39.0 (2026-08-18)

### Feat

-  comment fix
- bug and comment fix
- unify SCCFM interactive command and token configuration

## v0.38.0 (2026-07-27)

### Feat

- **inventory**: add FtdRegisterService and register_cdfmc_ftd Ansible module
- **skills**: reference sccfm-ansible skill into sccfm-cli skill and vice versa
- **lh-102436**: prepare devkit for PyPI publishing
- **skills**: reference sccfm-ansible skill into sccfm-cli skill and vice versa
- add schema-driven Ansible skill
- prepare sccfm for pypi publishing
- add schema-driven sccfm-cli skill
- **cdfmc-ftd**: add configure-manager to complete FTD registration over SSH
- add cli schema export

### Fix

- pass strict typing and FTD confirmation checks
- **lh-102436**: make packaging metadata portable
- **README**: Add license statement & clarify name acronym

## v0.37.0 (2026-06-04)

### Feat

- **hooks**: add pre-commit hooks for Python formatting and secret guarding (#77)

## v0.36.0 (2026-05-26)

### Feat

- **lh-106911**: add copyright (#64)

## v0.35.0 (2026-04-22)

### Feat

- add consistency check workflow and script for PR validation (#59)

## v0.34.0 (2026-04-22)

### Feat

- **LH-106647**: add Ansible e2e test suite for FTD (#62)

## v0.33.0 (2026-04-21)

### Feat

- **LH-102404**: add FTD CLI execution for cdFMC-managed devices (#57)

## v0.32.0 (2026-04-21)

### Feat

- **LH-106922**: access rules e2e (#56)

## v0.31.0 (2026-04-17)

### Feat

- **LH-106648**: add ASA HA check Ansible e2e test suite (#58)

## v0.30.0 (2026-04-15)

### Feat

- **LH-102404**: add ASA HA health check command (#55)

## v0.29.0 (2026-04-14)

### Feat

- **Lh 105871**: add sccfm ansible asa test suite (#53)

## v0.28.0 (2026-04-08)

### Feat

- **LH-102418**: add access rule creation for policies (#51)

## v0.27.0 (2026-04-08)

### Feat

- **LH-102432**: Onboard CDFMC Managed FTD (ZTP) (#52)

## v0.26.0 (2026-04-07)

### Feat

- **LH-102412**: create CDFMC Managed FTD (Non-ZTP) (#50)

## v0.25.0 (2026-04-01)

### Feat

- **LH-104308**: add network group add-member and remove-member commands (#46)

## v0.24.0 (2026-04-01)

### Feat

- **LH-106152**: object override improvements (#49)

## v0.23.0 (2026-03-31)

### Feat

- **LH-104307**: add override to object ansible and cli (#48)

## v0.22.0 (2026-03-25)

### Feat

- add cdfmc-managed FTD device deployment command (#43)

## v0.21.0 (2026-03-23)

### Feat

- **LH-102401**: add ASA boot image change workflow (#40)

## v0.20.0 (2026-03-23)

### Feat

- **lh-105592**: wait for transaction on asa upgrade (#41)

## v0.19.0 (2026-03-20)

### Feat

- **LH-105684**: ASA shun add wait flag and improve bulk inside a single transaction (#39)

## v0.18.0 (2026-03-18)

### Feat

- **LH-102405**: implement shun commands for ASA devices (#37)

## v0.17.0 (2026-03-10)

### Feat

- **lh-104999**: asa list boot registry ansible (#31)

## v0.16.0 (2026-03-06)

### Feat

- add --check preflight flag to CLI and Ansible check_mode support (#30)

## v0.15.1 (2026-02-27)

### Fix

- **lh-104598**: create network object idempotency (#27)

## v0.15.0 (2026-02-25)

### Feat

- **LH-102402**: add compatible upgrade versions for ASA devices (#21)

## v0.14.1 (2026-02-25)

### Fix

- **tests**: include all test directories and fix mock usage (#25)

## v0.14.0 (2026-02-25)

### Feat

- **lh-104305**: list network groups (#23)

## v0.13.0 (2026-02-24)

### Feat

- **LH-104302**: add delete network group cli command (#19)

## v0.12.0 (2026-02-20)

### Feat

- **LH-102397**: implement list local users command for ASA devices (#17)

## v0.11.0 (2026-02-18)

### Feat

- improve Ansible example playbooks with auto-discovery of SYNCED devices (#18)

## v0.10.0 (2026-02-18)

### Feat

- **LH-102398**: add change local password command for ASA devices (#16)

## v0.9.0 (2026-02-17)

### Feat

- **lh-102408**: list and search network objects (#13)

## v0.28.0 (2026-04-08)

### Feat

- **LH-102418**: add access rule creation for policies — core service, CLI command, and Ansible module

## v0.27.0 (2026-04-08)

### Feat

- **LH-102432**: Onboard CDFMC Managed FTD (ZTP) (#52)

## v0.26.0 (2026-04-07)

### Feat

- **LH-102412**: create CDFMC Managed FTD (Non-ZTP) (#50)

## v0.25.0 (2026-04-01)

### Feat

- **LH-104308**: add network group add-member and remove-member commands (#46)

## v0.24.0 (2026-04-01)

### Feat

- **LH-106152**: object override improvements (#49)

## v0.23.0 (2026-03-31)

### Feat

- **LH-104307**: add override to object ansible and cli (#48)

## v0.22.0 (2026-03-25)

### Feat

- add cdfmc-managed FTD device deployment command (#43)

## v0.21.0 (2026-03-23)

### Feat

- **LH-102401**: add ASA boot image change workflow (#40)

## v0.20.0 (2026-03-23)

### Feat

- **lh-105592**: wait for transaction on asa upgrade (#41)

## v0.19.0 (2026-03-20)

### Feat

- **LH-105684**: ASA shun add wait flag and improve bulk inside a single transaction (#39)
- **LH-102401**: add ASA boot image change workflow for CLI and Ansible (#40)

## v0.18.0 (2026-03-18)

### Feat

- **LH-102405**: implement shun commands for ASA devices (#37)

## v0.17.0 (2026-03-10)

### Feat

- **lh-104999**: asa list boot registry ansible (#31)

## v0.16.0 (2026-03-06)

### Feat

- add --check preflight flag to CLI and Ansible check_mode support (#30)

## v0.15.1 (2026-02-27)

### Fix

- **lh-104598**: create network object idempotency (#27)

## v0.15.0 (2026-02-25)

### Feat

- **LH-102402**: add compatible upgrade versions for ASA devices (#21)

## v0.14.1 (2026-02-25)

### Fix

- **tests**: include all test directories and fix mock usage (#25)

## v0.14.0 (2026-02-25)

### Feat

- **lh-104305**: list network groups (#23)

## v0.13.0 (2026-02-24)

### Feat

- **LH-104302**: add delete network group cli command (#19)

## v0.12.0 (2026-02-20)

### Feat

- **LH-102397**: implement list local users command for ASA devices (#17)

## v0.11.0 (2026-02-18)

### Feat

- improve Ansible example playbooks with auto-discovery of SYNCED devices (#18)

## v0.10.0 (2026-02-18)

### Feat

- **LH-102398**: add change local password command for ASA devices (#16)

## v0.9.0 (2026-02-17)

### Feat

- **lh-102408**: list and search network objects (#13)

## v0.8.0 (2026-02-13)

### Feat

- Add AsaDiskCommand and AsaDiskFileService to inventory management (#10)

## v0.7.0 (2026-02-11)

### Feat

- **LH-103781**: ansible playbook for creating network objects (#9)

## v0.6.0 (2026-02-11)

### Feat

- **LH-102407**: add cli command for network object creation (#8)

## v0.5.0 (2026-02-02)

### Feat

- Add execute_asa_cli Ansible module for executing CLI commands on ASA devices (#5)

## v0.4.2 (2025-12-12)

### Fix

- **LH-101462**: Fix how galaxy.yml always ended up a version behind pyproject.toml

## v0.4.1 (2025-12-12)

### Fix

- **LH-101462**: Force re-release

## v0.4.0 (2025-12-12)

### Feat

- **LH-101462**: Add Ansible task to onboard ASA devices, add new onboard-asa command (#3)

## v0.3.2 (2025-12-01)

### Fix

- **sccfm-cli**: Fix auto-completion issues

## v0.3.1 (2025-12-01)

### Fix

- **sccfm-cli**: improve docs (#2)

## v0.3.0 (2025-12-01)

### Feat

- **sccfm-cli**: Add command to smart license ASAs using sccfm-cli (#1)

## v0.2.1 (2025-12-01)

### Fix

- **github-actions**: Fix tagging and release

## v0.2.0 (2025-12-01)

### Feat

- **github-actions**: Improve tagging
- **sccfm-cli**: Add a new command to execute ASA CLIs

### Fix

- **github-actions**: Bump version of poetry code

## v0.1.3 (2025-11-29)

### Fix

- **cli**: Fix issue with rendering as JSON

## v0.1.2 (2025-11-29)

### Refactor

- **sccfm-devkit**: Restructure the code so that the core services can be shared between the CLI and the upcoming Ansible collection

## v0.1.1 (2025-11-29)

## v0.1.0 (2025-11-29)

### Feat

- **sccfm-cli**: Prepare release of v0.1.0

## v0.0.1 (2025-11-29)

### Feat

- **sccfm-cli**: Create a CLI for SCC Firewall Manager, underpinned by the public API
