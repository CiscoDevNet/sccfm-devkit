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
