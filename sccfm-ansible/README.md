# cisco.sccfm Ansible Collection

Ansible collection for managing Cisco Security Cloud Control Firewall Manager (SCCFM) devices. Includes inventory plugin and modules for device onboarding.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Requirements](#requirements)
  - [Install a matched release](#install-a-matched-release)
  - [Upgrade or downgrade](#upgrade-or-downgrade)
  - [Automation Controller and execution environments](#automation-controller-and-execution-environments)
  - [Verify the installation offline](#verify-the-installation-offline)
- [Trying out examples](#trying-out-examples)
  - [Configure authentication](#configure-authentication)
  - [Run an example](#run-an-example)
  - [Test Inventory](#test-inventory)
  - [Host Variables](#host-variables)
- [Modules](#modules)
  - [cisco.sccfm.onboard_asa](#ciscosccfmonboard_asa)
  - [cisco.sccfm.execute_asa_cli](#ciscosccfmexecute_asa_cli)
  - [cisco.sccfm.execute_ftd_cli](#ciscosccfmexecute_ftd_cli)
  - [cisco.sccfm.asa_ha_check](#ciscosccfmasa_ha_check)
  - [cisco.sccfm.change_asa_boot_image](#ciscosccfmchange_asa_boot_image)
- [Ansible Vault Management](#ansible-vault-management)
  - [What is Ansible Vault?](#what-is-ansible-vault)
  - [Vault Commands Reference](#vault-commands-reference)
- [Module Defaults Pattern](#module-defaults-pattern)
- [Authentication Methods](#authentication-methods)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)
  - ["Decryption failed" error](#decryption-failed-error)
  - ["region is required" error](#region-is-required-error)
  - ["api_token is required" error](#api_token-is-required-error)
  - [Inventory returns no hosts](#inventory-returns-no-hosts)
- [Examples](#examples)
- [Additional Resources](#additional-resources)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Features

- **Dynamic Inventory Plugin**: Automatically load SCCFM devices into Ansible inventory
- **ASA Onboarding Module**: Onboard ASA devices to your SCCFM tenant
- **ASA CLI Execution Module**: Execute CLI commands on ASA devices
- **FTD CLI Execution Module**: Execute read-only show commands on cdFMC-managed FTD devices
- **ASA HA Health Check Module**: Validate ASA failover health and common HA issues
- **ASA Boot Image Module**: Change the configured next-boot ASA image
- **Device Grouping**: Automatically group devices by type (ASA, CDFMC_MANAGED_FTD, etc.)
- **Ansible Vault Integration**: Secure credential management for API tokens and device passwords
- **Module Defaults Support**: Set region/API token once for all tasks

## Installation

The collection and its Python package form one release. Modules in `cisco.sccfm` import
`cisco_sccfm_core` from the `cisco-sccfm-devkit` Python distribution, but Galaxy does not install
Python packages. Install both published artifacts at the **same exact version**. Mixing versions is
unsupported.

### Requirements

- Python `>=3.12,<4.0` on the Ansible control node or inside the execution environment
- `ansible-core>=2.20,<2.22` in that same environment
- Network access from that environment to SCC Firewall Manager
- An SCCFM API token and one of these regions: `int`, `us`, `eu`, `apj`, `au`, `uae`, `in`, or
  `ci`

The bundled examples run SCCFM API modules on `localhost`, so the Python package normally belongs
on the control node or in the execution environment. If you run or delegate a module to another
Ansible host, install the package in that host's module Python environment too. ASA and FTD devices
managed through the SCCFM API do not need the package installed on them.

### Install a matched release

Create and activate a Python 3.12 virtual environment. Replace `X.Y.Z` with a version that exists
on both PyPI and Ansible Galaxy, then install the Python artifact first and the Galaxy artifact
second:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ansible-core>=2.20,<2.22" "cisco-sccfm-devkit==X.Y.Z"
ansible-galaxy collection install "cisco.sccfm:==X.Y.Z"
```

Do not continue with a partially published release. If either `X.Y.Z` artifact is unavailable,
install another version for which both artifacts exist.

### Upgrade or downgrade

Change both artifacts together, keeping the Python package first in the operation:

```bash
python -m pip install --upgrade "cisco-sccfm-devkit==X.Y.Z"
ansible-galaxy collection install "cisco.sccfm:==X.Y.Z" --upgrade
```

For a rollback, install the older Python version and force Ansible Galaxy to replace the installed
collection:

```bash
python -m pip install "cisco-sccfm-devkit==X.Y.Z"
ansible-galaxy collection install "cisco.sccfm:==X.Y.Z" --force
```

Never upgrade or roll back only one artifact.

### Automation Controller and execution environments

Automation Controller jobs must use an execution environment whose base image provides Python
`>=3.12,<4.0` and `ansible-core>=2.20,<2.22`. Pin the collection in the execution environment's
Galaxy requirements:

```yaml
---
collections:
  - name: cisco.sccfm
    version: "==X.Y.Z"
```

The packaged [`meta/execution-environment.yml`](meta/execution-environment.yml) directs Ansible
Builder to the packaged [`requirements.txt`](requirements.txt), which installs the exact matching
`cisco-sccfm-devkit` Python release. Do not override that dependency with a different version.
Provide `SCCFM_REGION` and `SCCFM_API_TOKEN` to the job through an Automation Controller
credential or another secret manager; do not bake tokens into an image.

### Verify the installation offline

These checks resolve the installed Python package, modules, and inventory plugin without contacting
SCCFM:

```bash
python -c 'from importlib.metadata import version; print(version("cisco-sccfm-devkit"))'
python -m pip check
ansible-galaxy collection list cisco.sccfm
ansible-doc -l -t module cisco.sccfm
ansible-doc -t inventory cisco.sccfm.sccfm
```

The two reported release versions must be identical. For an offline syntax smoke test, save this as
`sccfm-smoke.yml`:

```yaml
---
- name: Validate cisco.sccfm collection resolution
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Resolve a read-only SCCFM module
      cisco.sccfm.list_network_objects:
        limit: 1
```

Then run:

```bash
ansible-playbook -i localhost, --syntax-check sccfm-smoke.yml
```

## Trying out examples

### Configure authentication

For local use, provide credentials to the process environment. Enter the token through your shell,
CI secret store, or credential manager without putting it in a playbook, a tracked file, or a
command-line argument:

```bash
export SCCFM_REGION=us
printf "SCCFM API token: "
read -r -s SCCFM_API_TOKEN
printf "\n"
export SCCFM_API_TOKEN
```

For long-lived automation, use a secret manager or an Ansible Vault variable in a playbook-local
file. For example, create `vault.yml` with `ansible-vault create vault.yml` and store:

```yaml
---
vault_sccfm_api_token: "replace-with-your-token"
```

Reference it without exposing the token:

```yaml
vars_files:
  - vault.yml
module_defaults:
  group/cisco.sccfm.all:
    region: "{{ lookup('env', 'SCCFM_REGION') }}"
    api_token: "{{ vault_sccfm_api_token }}"
```

Run vault-backed playbooks with `--ask-vault-pass` or with your organization's approved vault
secret integration. Never commit a real token, decrypted vault, or vault password.

### Run an example

The `examples/` directory is included in the Galaxy artifact. Copy the example you want into your
Ansible project before editing it. Use fully qualified collection names in your own playbooks.

**Graph inventory:**
```bash
ansible-inventory -i examples/inventory.sccfm.yml \
  --graph \
  --playbook-dir examples
```

**Show all devices:**
```bash
ansible-playbook \
-i examples/inventory.sccfm.yml \
examples/show_devices.yml
```

### Test Inventory

```bash
ansible-inventory -i inventory.sccfm.yml --graph
```

Do not use `--list`, `--yaml`, or `--graph --vars` while decrypted `group_vars` contain
secrets: those output formats can print any variables supplied by Ansible Vault or other vars
plugins. Plain `--graph` validates discovery without rendering variables.

### Host Variables

Each device gets the following variables:
- `sccfm_uid` - Device unique identifier
- `sccfm_name` - Device name
- `sccfm_region` - SCCFM region
- `sccfm_device_type` - Device type (ASA, CDFMC_MANAGED_FTD, etc.)
- `sccfm_connectivity_state` - Device connectivity state
- `sccfm_config_state` - Device configuration state
- `sccfm_software_version` - Device software version

The inventory plugin never adds its API token to a group or host. It consumes the configured
token only while refreshing inventory. This guarantee does not apply to secrets that users place
in `group_vars`, which are ordinary Ansible inventory data and may be rendered by inventory
commands.

## Modules

Discover the module and inventory documentation from the installed collection:

```bash
ansible-doc -l -t module cisco.sccfm
ansible-doc cisco.sccfm.onboard_asa
ansible-doc -t inventory cisco.sccfm.sccfm
```

### cisco.sccfm.onboard_asa

Onboard an ASA device to your SCCFM tenant.

**Parameters:**
- `name` (required): Human-readable name for the device
- `device_address` (required): Address in format `host:port`
- `username` (required): Authentication username
- `password` (required): Authentication password
- `connector_type` (required): `SDC` or `CDG`
- `connector_name`: Required if `connector_type` is `SDC`
- `ignore_certificate`: Skip certificate validation (default: false)
- `grouped_labels`: Dictionary of label groups
- `ungrouped_labels`: List of labels
- `region`: SCCFM region (optional, uses vault/env)
- `api_token`: API token (optional, uses vault/env)

**Example:**
```yaml
- name: Onboard ASA devices
  hosts: localhost
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  
  tasks:
    - name: Onboard branch ASA
      cisco.sccfm.onboard_asa:
        name: branch-asa-01
        device_address: "192.0.2.10:443"
        username: admin
        password: "{{ vault_asa_branch_password }}"
        connector_type: SDC
        connector_name: branch-sdc-01
        ignore_certificate: true
        grouped_labels:
          location: ["branch"]
          environment: ["production"]
        ungrouped_labels:
          - asa
          - firewall
```

### cisco.sccfm.execute_asa_cli

Execute CLI commands on ASA devices via SCCFM. Show commands require devices to be `ONLINE`. Config commands require devices to be `SYNCED`.

See [`examples/execute_asa_cli.yml`](examples/execute_asa_cli.yml) for usage, or run `ansible-doc cisco.sccfm.execute_asa_cli` for full parameter documentation.

### cisco.sccfm.execute_ftd_cli

Execute read-only `show` commands on cdFMC-managed FTD devices via SCCFM. The module resolves target devices from either a Lucene query or an explicit list of UIDs, then runs the command through the cdFMC bulk command proxy endpoint.

See [`examples/execute_ftd_cli.yml`](examples/execute_ftd_cli.yml) for usage, or run `ansible-doc cisco.sccfm.execute_ftd_cli` for full parameter documentation.

### cisco.sccfm.asa_ha_check

Run HA health checks on ASA failover devices via SCCFM. The module executes
`show failover` and `show failover state`, then validates failover enablement,
LAN/stateful health, version parity, interface health, config sync, and
interfaces that are enabled but not monitored for failover.

See [`examples/asa_ha_check.yml`](examples/asa_ha_check.yml) for usage,
or run `ansible-doc cisco.sccfm.asa_ha_check` for full parameter
documentation.

### cisco.sccfm.change_asa_boot_image

Change the configured ASA boot image for the next reload. The image must already
exist on the device. This module does not upload the image and does not reboot
the device. In `check_mode`, it validates the image path and inspects the
containing filesystem without changing config.

See [`examples/change_asa_boot_image.yml`](examples/change_asa_boot_image.yml) for usage,
or run `ansible-doc cisco.sccfm.change_asa_boot_image` for full parameter
documentation.

## Ansible Vault Management

### What is Ansible Vault?

Ansible Vault encrypts sensitive data such as API tokens and passwords. The local `vault.yml` and
`.vault_pass` files are Git-ignored and excluded from collection artifacts; do not commit either
file, even when the vault is encrypted.

### Vault Commands Reference

**Create new encrypted file:**
```bash
ansible-vault create group_vars/all/vault.yml --vault-password-file .vault_pass
```

**Edit encrypted vault file (recommended):**
```bash
ansible-vault edit group_vars/all/vault.yml --vault-password-file .vault_pass
```

**View encrypted vault file:**
```bash
ansible-vault view group_vars/all/vault.yml --vault-password-file .vault_pass
```

**Encrypt existing file:**
```bash
ansible-vault encrypt group_vars/all/vault.yml --vault-password-file .vault_pass
```

**Decrypt vault file (temporarily):**
```bash
ansible-vault decrypt group_vars/all/vault.yml --vault-password-file .vault_pass
# Edit the file
ansible-vault encrypt group_vars/all/vault.yml --vault-password-file .vault_pass
```

**Change vault password:**
```bash
ansible-vault rekey group_vars/all/vault.yml \
  --vault-password-file .vault_pass \
  --new-vault-password-file ~/.sccfm-vault-pass-new
```

**Verify file is encrypted:**
```bash
head -1 group_vars/all/vault.yml
# Should output: $ANSIBLE_VAULT;1.1;AES256
```

## Module Defaults Pattern

Instead of repeating `region` and `api_token` for every task, use `module_defaults`:

```yaml
- name: Manage SCCFM devices
  hosts: localhost
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
  
  tasks:
    - name: Onboard device 1
      cisco.sccfm.onboard_asa:
        name: device-1
        # No need to specify region/api_token here!
        
    - name: Onboard device 2
      cisco.sccfm.onboard_asa:
        name: device-2
        # Still no region/api_token needed!
```

## Authentication Methods

Three ways to provide credentials (in order of precedence):

1. **Module parameters** (explicit in task)
2. **Module defaults** (recommended - set once per playbook)
3. **Environment variables**:
   ```bash
   export SCCFM_REGION=us
   # Inject SCCFM_API_TOKEN through your shell or secret manager as shown above.
   ```

## Security Best Practices

1. **Never commit credential files**, including encrypted customer vaults, to your project
2. **Keep vault files encrypted** whenever they are at rest
3. **Store `.vault_pass` securely** and never commit it
4. **Use different vault passwords** for different environments (dev/prod)
5. **Rotate API tokens regularly** and update vault files accordingly
6. **Use `.gitignore`** to prevent accidental commits of sensitive files
7. **Use `no_log: true`** for password parameters in custom tasks
8. **Do not serialize secret-bearing inventory** with `ansible-inventory --list`, `--yaml`, or
   `--graph --vars`

## Troubleshooting

### "Decryption failed" error
- Check your vault password is correct
- Ensure you're using the right vault password file

### "region is required" error
- Verify `sccfm_region` is set in `group_vars/all/vars.yml`
- Or set `SCCFM_REGION` environment variable
- Or provide `region` parameter in module defaults

### "api_token is required" error
- Verify `SCCFM_API_TOKEN` is set in the controller environment
- Or provide a Vault-backed `api_token` parameter in module defaults; keep the Vault
  playbook-local instead of placing it in inventory or `group_vars`

### Inventory returns no hosts
- Check your API token has proper permissions
- Verify the region is correct
- Run plain `ansible-inventory --graph` to test discovery without printing inventory variables

## Examples

See the `examples/` directory for complete working examples. Locally generated credential files
are Git-ignored and excluded from collection artifacts:

- **`inventory.sccfm.yml`** - Dynamic inventory configuration
- **`show_devices.yml`** - Display all devices from inventory
- **`onboard_asas.yml`** - Onboard multiple ASA devices with vault passwords
- **`execute_asa_cli.yml`** - Execute CLI commands on ASA devices
- **`execute_ftd_cli.yml`** - Execute show commands on cdFMC-managed FTD devices
- **`asa_ha_check.yml`** - Run HA health checks on ASA failover devices
- **`change_asa_boot_image.yml`** - Change the configured ASA boot image
- **`group_vars/all/vars.yml`** - Plain variables (region, defaults)
- **`group_vars/all/vault.yml`** - Locally generated encrypted secrets; never packaged
- **`group_vars/all/vault.yml.example`** - Template for vault structure

## Additional Resources

- [Installing Ansible collections](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_installing.html)
- [Ansible Core support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix)
- [Ansible Vault Documentation](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [Ansible Inventory Plugins](https://docs.ansible.com/ansible/latest/plugins/inventory.html)
- [SCC Firewall Manager API Documentation](https://developer.cisco.com/docs/security-cloud-control/)
- [Module Defaults](https://docs.ansible.com/ansible/latest/user_guide/playbooks_module_defaults.html)
