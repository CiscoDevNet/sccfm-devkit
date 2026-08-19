# cisco.sccfm Ansible Collection

Ansible collection for managing Cisco Security Cloud Control Firewall Manager (SCCFM) devices. Includes inventory plugin and modules for device onboarding.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Local Development](#local-development)
- [Trying out examples](#trying-out-examples)
  - [1. Configure an SCCFM Profile](#1-configure-an-sccfm-profile)
  - [2. Edit playbook](#2-edit-playbook)
  - [4. Run Examples](#4-run-examples)
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
- [Authentication](#authentication)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)
  - ["Decryption failed" error](#decryption-failed-error)
  - ["profile not found" error](#profile-not-found-error)
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
- **Canonical SCCFM Profiles**: Share one named region/token profile with both CLI surfaces
- **Ansible Vault Integration**: Secure device passwords and other playbook-specific secrets
- **Module Defaults Support**: Select one profile for all tasks

## Installation

See instructions in the [INSTALL.md](INSTALL.md) file.

### Local Development

Run these commands from an activated repository checkout.

**Build and install (recommended):**
```bash
sccfm-devkit
# then select "build-collection" from the menu
```

Or directly:
```bash
build-ansible-collection
```

This will:
1. Initialize the poetry virtual environment (if needed)
2. Install Python dependencies (`cisco_sccfm_core`, `cisco_sccfm_cli`, etc.)
3. Install the Ansible collection

## Trying out examples

### 1. Configure an SCCFM Profile

The CLI and Ansible collection use the same named profile store. Configure it directly:

```bash
sccfm-cli --profile default configure --region us
```

Or use the interactive flow:

```bash
sccfm-cli-interactive
# select "configure-profile"
```

Profiles live at `~/.sccfm-cli/config.json`. On POSIX systems, the containing directory is
restricted to the current user (`0700`) and the file is owner read/write (`0600`); on
Windows, the store inherits the user's profile-directory ACLs. Ansible modules
and inventory load the selected profile directly; do not duplicate its API token in
environment variables or Ansible Vault.

When developing from a source checkout, profiles from the former Ansible Vault token store can
be imported without modifying the source vault:

```bash
sccfm-devkit
# select "import-legacy-vault"
```

This migration helper is development-only and is not included in the public Python package.

<details>
<summary><strong>Set up Ansible-specific device secrets</strong></summary>

Create a vault password file (do NOT commit this!):

```bash
cd examples
cp .vault_pass.example .vault_pass
echo "YourSecureVaultPassword" > .vault_pass
chmod 600 .vault_pass
```

Copy and edit the example vault file:

```bash
cp group_vars/all/vault.yml.example group_vars/all/vault.yml.temp
vim group_vars/all/vault.yml.temp
```

Add only playbook-specific secrets:
```yaml
---
vault_asa_branch_office_01_password: "ActualPassword1"
```

Encrypt the vault file:
```bash
ansible-vault encrypt group_vars/all/vault.yml.temp \
  --vault-password-file .vault_pass \
  --output group_vars/all/vault.yml

rm group_vars/all/vault.yml.temp
```

</details>

### 2. Edit playbook

Edit the `onboard_asas.yml` playbook, and change the `asas_to_onboard` list to match your devices.

### 4. Run Examples

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
examples/show_devices.yml \
--vault-password-file examples/.vault_pass
```

**Onboard ASA devices:**
```bash
ansible-playbook onboard_asas.yml --vault-password-file .vault_pass
```

### Test Inventory

```bash
ansible-inventory -i inventory.sccfm.yml --list --vault-password-file .vault_pass
ansible-inventory -i inventory.sccfm.yml --graph --vault-password-file .vault_pass
```

### Host Variables

Each device gets the following variables:
- `sccfm_uid` - Device unique identifier
- `sccfm_name` - Device name
- `sccfm_region` - SCCFM region
- `sccfm_device_type` - Device type (ASA, CDFMC_MANAGED_FTD, etc.)
- `sccfm_connectivity_state` - Device connectivity state
- `sccfm_config_state` - Device configuration state
- `sccfm_software_version` - Device software version

## Modules

From an activated repository checkout, generate module and inventory reference docs with:

```bash
generate-ansible-docs
```

The generated Markdown is written under `docs/ansible/`.

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
- `profile`: Named SCCFM profile (optional, defaults to `default`)
- `config_path`: Optional path to the canonical profile file

**Example:**
```yaml
- name: Onboard ASA devices
  hosts: localhost
  module_defaults:
    group/cisco.sccfm.all:
      profile: default
  
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

Ansible Vault encrypts playbook-specific secrets such as managed-device passwords so you can safely commit them to version control. SCCFM API tokens belong only in the canonical profile store. The encrypted `vault.yml` file may be committed, but the `.vault_pass` password file is **never** committed.

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
  --new-vault-password-file .vault_pass_new
```

**Verify file is encrypted:**
```bash
head -1 group_vars/all/vault.yml
# Should output: $ANSIBLE_VAULT;1.1;AES256
```

## Module Defaults Pattern

Select a non-default profile once with `module_defaults`:

```yaml
- name: Manage SCCFM devices
  hosts: localhost
  module_defaults:
    group/cisco.sccfm.all:
      profile: production
  
  tasks:
    - name: Onboard device 1
      cisco.sccfm.onboard_asa:
        name: device-1
        # No need to repeat the profile here.
        
    - name: Onboard device 2
      cisco.sccfm.onboard_asa:
        name: device-2
        # The same profile is used here.
```

## Authentication

Configure credentials once with `sccfm-cli configure`. Modules and inventory use the
`default` profile unless `profile` selects another name. `config_path` selects a custom
canonical profile file when needed.

## Security Best Practices

1. **Never commit unencrypted secrets** to version control
2. **Always encrypt vault files** before committing
3. **Store `.vault_pass` securely** and never commit it
4. **Use different vault passwords** for different environments (dev/prod)
5. **Rotate API tokens regularly** with `sccfm-cli configure`
6. **Use `.gitignore`** to prevent accidental commits of sensitive files
7. **Use `no_log: true`** for password parameters in custom tasks

## Troubleshooting

### "Decryption failed" error
- Check your vault password is correct
- Ensure you're using the right vault password file

### "profile not found" error
- Run `sccfm-cli --profile <name> configure`.
- Ensure the playbook's `profile` value matches the configured name.
- If using `config_path`, ensure it points to the same canonical profile file.

### Inventory returns no hosts
- Check your API token has proper permissions
- Verify the region is correct
- Test API access without exposing the token: `sccfm-cli --profile <name> status`

## Examples

See the `examples/` directory for complete working examples:

- **`inventory.sccfm.yml`** - Dynamic inventory configuration
- **`show_devices.yml`** - Display all devices from inventory
- **`onboard_asas.yml`** - Onboard multiple ASA devices with vault passwords
- **`execute_asa_cli.yml`** - Execute CLI commands on ASA devices
- **`execute_ftd_cli.yml`** - Execute show commands on cdFMC-managed FTD devices
- **`asa_ha_check.yml`** - Run HA health checks on ASA failover devices
- **`change_asa_boot_image.yml`** - Change the configured ASA boot image
- **`group_vars/all/vars.yml`** - Plain playbook variables
- **`group_vars/all/vault.yml`** - Encrypted playbook-specific secrets
- **`group_vars/all/vault.yml.example`** - Template for vault structure

## Additional Resources

- [Ansible Vault Documentation](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [Ansible Inventory Plugins](https://docs.ansible.com/ansible/latest/plugins/inventory.html)
- [SCC Firewall Manager API Documentation](https://developer.cisco.com/docs/security-cloud-control/)
- [Module Defaults](https://docs.ansible.com/ansible/latest/user_guide/playbooks_module_defaults.html)
