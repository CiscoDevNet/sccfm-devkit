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
- **Device Grouping**: Automatically group devices by type (ASA, CDFMC_MANAGED_FTD, etc.)
- **Ansible Vault Integration**: Secure credential management for API tokens and device passwords
- **Module Defaults Support**: Set region/API token once for all tasks

## Installation

See instructions in the [INSTALL.md](INSTALL.md) file.

### Local Development

**Build and install (recommended):**
```bash
cd sccfm-ansible
./build.sh
```

This script will:
1. Initialize the poetry virtual environment (if needed)
2. Install Python dependencies (`sccfm_core`, `sccfm_cli`, etc.)
3. Install the Ansible collection

## Trying out examples

### 1. Set Up Ansible Vault

Create a vault password file (do NOT commit this!):

```bash
cd examples
cp .vault_pass.example .vault_pass
echo "YourSecureVaultPassword" > .vault_pass
chmod 600 .vault_pass
```

### 2. Edit playbook

Edit the `onboard_asas.yml` playbook, and change the `asas_to_onboard` list to match your devices.

### 2. Create Encrypted Secrets

```bash
# Copy the example vault file
cp group_vars/all/vault.yml.example group_vars/all/vault.yml.temp

# Edit with your actual secrets
vim group_vars/all/vault.yml.temp
```

Add your secrets:
```yaml
---
# SCC Firewall Manager API token
sccfm_api_token: "your-actual-api-token-here"

# Password for each ASA device
vault_asa_branch_office_01_password: "ActualPassword1"
# and so on for each ASA device
```

Encrypt the vault file:
```bash
ansible-vault encrypt group_vars/all/vault.yml.temp \
  --vault-password-file .vault_pass \
  --output group_vars/all/vault.yml

rm group_vars/all/vault.yml.temp
```

### 3. Configure Plain Variables

Edit `examples/group_vars/all/vars.yml`:

```yaml
sccfm_region: us  # Change to your region (us, eu, apj, aus, uae, in, or int)
```

### 4. Run Examples

**Graph inventory:**
```bash
export SCCFM_REGION=int
export SCCFM_API_TOKEN=$(ansible-vault view ./examples/group_vars/all/vault.yml --vault-password-file ./examples/.vault_pass | grep sccfm_api_token | cut -d '"' -f2)
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
      api_token: "{{ sccfm_api_token }}"
  
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

## Ansible Vault Management

### What is Ansible Vault?

Ansible Vault encrypts sensitive data (API tokens, passwords) so you can safely commit them to version control. The encrypted `vault.yml` file is committed, but the `.vault_pass` password file is **never** committed.

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

Instead of repeating `region` and `api_token` for every task, use `module_defaults`:

```yaml
- name: Manage SCCFM devices
  hosts: localhost
  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"
  
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

1. **Never commit unencrypted secrets** to version control
2. **Always encrypt vault files** before committing
3. **Store `.vault_pass` securely** and never commit it
4. **Use different vault passwords** for different environments (dev/prod)
5. **Rotate API tokens regularly** and update vault files accordingly
6. **Use `.gitignore`** to prevent accidental commits of sensitive files
7. **Use `no_log: true`** for password parameters in custom tasks

## Troubleshooting

### "Decryption failed" error
- Check your vault password is correct
- Ensure you're using the right vault password file

### "region is required" error
- Verify `sccfm_region` is set in `group_vars/all/vars.yml`
- Or set `SCCFM_REGION` environment variable
- Or provide `region` parameter in module defaults

### "api_token is required" error
- Verify `sccfm_api_token` is in encrypted `group_vars/all/vault.yml`
- Or set `SCCFM_API_TOKEN` environment variable
- Or provide `api_token` parameter in module defaults

### Inventory returns no hosts
- Check your API token has proper permissions
- Verify the region is correct
- Test API access: `curl -H "Authorization: Bearer $SCCFM_API_TOKEN" https://<region>.cdo.cisco.com/api/rest/v1/inventory/devices`

## Examples

See the `examples/` directory for complete working examples:

- **`inventory.sccfm.yml`** - Dynamic inventory configuration
- **`show_devices.yml`** - Display all devices from inventory
- **`onboard_asas.yml`** - Onboard multiple ASA devices with vault passwords
- **`group_vars/all/vars.yml`** - Plain variables (region, defaults)
- **`group_vars/all/vault.yml`** - Encrypted secrets (API token, passwords)
- **`group_vars/all/vault.yml.example`** - Template for vault structure

## Additional Resources

- [Ansible Vault Documentation](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [Ansible Inventory Plugins](https://docs.ansible.com/ansible/latest/plugins/inventory.html)
- [SCC Firewall Manager API Documentation](https://developer.cisco.com/docs/security-cloud-control/)
- [Module Defaults](https://docs.ansible.com/ansible/latest/user_guide/playbooks_module_defaults.html)
