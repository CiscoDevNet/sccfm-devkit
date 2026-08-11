# cisco.sccfm Ansible Collection

Ansible collection for managing Cisco Security Cloud Control Firewall Manager (SCCFM) devices. Includes inventory plugin and modules for device onboarding.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Local Development](#local-development)
- [Trying out examples](#trying-out-examples)
  - [1. Set Up Ansible Vault](#1-set-up-ansible-vault)
  - [2. Edit playbook](#2-edit-playbook)
  - [2. Create Encrypted Secrets](#2-create-encrypted-secrets)
  - [3. Configure Plain Variables](#3-configure-plain-variables)
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

See instructions in the [INSTALL.md](INSTALL.md) file.

### Local Development

From the repository root, build the collection with the source-only helper:

```bash
source cisco_sccfm_scripts/activate.sh
build-ansible-collection
```

The helper reads the repository version, creates the tarball under `dist/`, and verifies the exact
artifact. Install the built collection explicitly:

```bash
ansible-galaxy collection install dist/cisco-sccfm-*.tar.gz --force
```

## Trying out examples

### 1. Set Up Tokens (Recommended — interactive)

The PyPI package exposes only the `sccfm-cli` console command; it does not install repository
maintenance helpers. In an activated source checkout, run the token helper from the repository
root:

```bash
change-tokens
```

This will interactively:
1. Let you pick a previously saved token or create a new one
2. Ask which SCCFM region you're connecting to (for new tokens)
3. Prompt you to paste your API token
4. Save the token for future reuse
5. Create the `.env` file with `SCCFM_REGION` and `SCCFM_API_TOKEN`
6. Create the `.vault_pass` password file (if it doesn't exist)
7. Write and encrypt `group_vars/all/vault.yml`
8. Update `group_vars/all/vars.yml` with the selected region

By default, Ansible credentials are written under `sccfm-ansible/examples`. They are Git-ignored
and explicitly excluded from collection artifacts. You can also point the standalone command at a
custom examples directory:

```bash
change-tokens --path /path/to/examples
```

Users of installed artifacts should configure `SCCFM_REGION` and `SCCFM_API_TOKEN` through their
controller environment or secret manager, or use the manual Ansible Vault setup below.

<details>
<summary><strong>Manual setup (alternative)</strong></summary>

Create a vault password file (do NOT commit this!):

```bash
cd sccfm-ansible/examples
cp .vault_pass.example .vault_pass
echo "YourSecureVaultPassword" > .vault_pass
chmod 600 .vault_pass
```

Copy and edit the example vault file:

```bash
cp group_vars/all/vault.yml.example group_vars/all/vault.yml.temp
vim group_vars/all/vault.yml.temp
```

Add your secrets:
```yaml
---
sccfm_api_token: "your-actual-api-token-here"
vault_asa_branch_office_01_password: "ActualPassword1"
```

Encrypt the vault file:
```bash
ansible-vault encrypt group_vars/all/vault.yml.temp \
  --vault-password-file .vault_pass \
  --output group_vars/all/vault.yml

rm group_vars/all/vault.yml.temp
```

Edit `group_vars/all/vars.yml`:

```yaml
sccfm_region: us  # Change to your region (int, us, eu, apj, au, uae, in, or ci)
```

</details>

### 2. Edit playbook

Edit the `onboard_asas.yml` playbook, and change the `asas_to_onboard` list to match your devices.

### 4. Run Examples

**Graph inventory:**
```bash
# Load SCCFM_REGION and SCCFM_API_TOKEN without putting the token on argv.
# `change-tokens` writes the repository .env for use with direnv.
ansible-inventory -i examples/inventory.sccfm.yml \
  --graph \
  --playbook-dir examples \
  --vault-password-file examples/.vault_pass
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
ansible-inventory -i inventory.sccfm.yml --graph --vault-password-file .vault_pass
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

Generated module and inventory reference docs can be previewed locally. Generate them with:

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
   export SCCFM_API_TOKEN=your-token-here
   ```

## Security Best Practices

1. **Never commit credential files**, including encrypted customer vaults, to this repository
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
- Test API access: `curl -H "Authorization: Bearer $SCCFM_API_TOKEN" https://<region>.cdo.cisco.com/api/rest/v1/inventory/devices`

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

- [Ansible Vault Documentation](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [Ansible Inventory Plugins](https://docs.ansible.com/ansible/latest/plugins/inventory.html)
- [SCC Firewall Manager API Documentation](https://developer.cisco.com/docs/security-cloud-control/)
- [Module Defaults](https://docs.ansible.com/ansible/latest/user_guide/playbooks_module_defaults.html)
