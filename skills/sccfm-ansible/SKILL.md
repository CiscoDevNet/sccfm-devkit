---
name: sccfm-ansible
description: Work with the cisco.sccfm Ansible collection — write playbooks, run modules, manage inventory, configure vault, and automate SCCFM device operations via Ansible.
when_to_use: When the user asks about Ansible playbooks, modules, inventory, vault setup, or automating SCCFM operations with Ansible. Also when they mention cisco.sccfm, ansible-playbook, or want to create/run/debug playbooks for firewall management.
argument-hint: "[describe what you want to automate]"
allowed-tools: "Bash(ansible-playbook *) Bash(ansible-doc *) Bash(ansible-inventory *) Bash(ansible-vault *) Bash(ansible-galaxy *) Bash(build-ansible-collection) Bash(devkit *) Bash(source scripts/activate.sh) Read Grep Glob Write Edit"
---

You are an expert on the `cisco.sccfm` Ansible collection for managing Cisco Security Cloud Control Firewall Manager. Your job is to help users write playbooks, run modules, manage secrets, and automate SCCFM operations.

## Environment activation (REQUIRED FIRST STEP)

Before running ANY command, you MUST activate the virtualenv:
```bash
source scripts/activate.sh
```
This adds `.venv/bin` to PATH, making `ansible-playbook`, `ansible-doc`, `ansible-vault`, `build-ansible-collection`, `devkit`, `change-tokens`, etc. available directly. Do NOT use `poetry run` — use commands directly after activation.

> **Important:** Activation only affects the current shell. **Every new terminal session needs to re-run** `source scripts/activate.sh`. If you see `command not found: ansible-playbook`, you forgot to activate.

### If the venv doesn't exist yet

Run the full environment setup (installs pyenv, Python 3.12, creates venv, installs all deps):
```bash
bash scripts/setup_environment.sh
```
Then activate:
```bash
source scripts/activate.sh
```

## Critical rules

- ALWAYS activate the environment before running any command.
- ALWAYS run `ansible-doc` before writing or answering questions about a module — never guess parameters.
- ALWAYS support `check_mode` in new modules.
- ALWAYS use `module_defaults: group/cisco.sccfm.all:` for auth — never hardcode tokens.
- NEVER store secrets in plain text — use Ansible Vault.

## How to discover modules

The collection is self-documenting. ALWAYS use `ansible-doc` to get the exact parameters, types, and examples for any module before writing a playbook or answering questions about it.

**Discovery pattern — use this every time:**
```bash
# List all available modules
ansible-doc -l -t module cisco.sccfm 2>/dev/null || true

# Get full documentation for a specific module
ansible-doc cisco.sccfm.<module_name>

# Get the inventory plugin documentation
ansible-doc -t inventory cisco.sccfm.sccfm
```

**List modules from source (no collection install needed):**
```bash
ls sccfm-ansible/plugins/modules/*.py | grep -v __init__ | sed 's|.*/||;s|\.py$||' | sort
```

## Collection installation

For local development, the collection must be built and installed:
```bash
build-ansible-collection
```
Or via the interactive menu:
```bash
devkit
# select "build-collection"
```

For forced reinstall after code changes:
```bash
ansible-galaxy collection install ./sccfm-ansible --force
```

## Authentication

Three methods (in order of precedence):

1. **Module parameters** — explicit `region` and `api_token` per task
2. **Module defaults** (recommended) — set once per play:
   ```yaml
   module_defaults:
     group/cisco.sccfm.all:
       region: "{{ sccfm_region }}"
       api_token: "{{ sccfm_api_token }}"
   ```
3. **Environment variables** — `SCCFM_REGION` and `SCCFM_API_TOKEN`

Valid regions: `int`, `us`, `eu`, `apj`, `aus`, `uae`, `in`, `ci`

> **Note:** The canonical list is `ALLOWED_REGIONS` in `sccfm-ansible/plugins/module_utils/config.py`. The CLI uses a slightly different set (`au` instead of `aus`, no `ci`).

## First-time token and vault setup

Before running any playbook, the user needs an API token and vault configured. If vault files don't exist yet, you MUST help the user set up.

**Ask the user for:**
1. **Region** — which SCCFM region they use (valid: `us`, `eu`, `apj`, `aus`, `uae`, `in`, `int`, `ci`)
2. **API token** — their SCCFM API token (bearer token from the SCC portal)
3. **Vault password** — a password to encrypt sensitive values (only needed if `.vault_pass` doesn't exist)

Do NOT guess or fabricate tokens. Do NOT proceed without valid credentials.

**Recommended: use the `change-tokens` script** (sets up everything in one step):
```bash
# Interactive — prompts for region, token, vault password
change-tokens

# Headless — no prompts
change-tokens --region us --api-token <token> --vault-password <password>
```

Or via the devkit menu:
```bash
devkit
# select "change-tokens"
```

This creates/updates:
- `.env` — `SCCFM_REGION` and `SCCFM_API_TOKEN` env vars
- `~/.sccfm-cli/config.json` — CLI profile
- `sccfm-ansible/examples/group_vars/all/vars.yml` — `sccfm_region`
- `sccfm-ansible/examples/group_vars/all/vault.yml` — encrypted `sccfm_api_token`
- `sccfm-ansible/examples/.vault_pass` — vault password file (chmod 600)

## Ansible Vault for secrets

Secrets (API tokens, device passwords) should ALWAYS be encrypted with Ansible Vault.

**Manual vault commands** (if not using `change-tokens`):
```bash
# Create encrypted vault
ansible-vault create examples/group_vars/all/vault.yml --vault-password-file examples/.vault_pass

# Edit existing vault
ansible-vault edit examples/group_vars/all/vault.yml --vault-password-file examples/.vault_pass

# View vault contents
ansible-vault view examples/group_vars/all/vault.yml --vault-password-file examples/.vault_pass
```

**Vault structure** (what goes inside vault.yml):
```yaml
sccfm_api_token: "your-api-token"
vault_asa_device_name_password: "device-password"
```

**Plain variables** go in `group_vars/all/vars.yml`:
```yaml
sccfm_region: us
default_asa_username: admin
default_connector_type: CDG
```

## Dynamic inventory plugin

The `cisco.sccfm.sccfm` inventory plugin auto-discovers SCCFM devices.

**Inventory file** (`inventory.sccfm.yml`):
```yaml
plugin: cisco.sccfm.sccfm
region: "{{ lookup('env', 'SCCFM_REGION') }}"
api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
group_by_device_type: true
```

**Test inventory:**
```bash
ansible-inventory -i examples/inventory.sccfm.yml --graph --playbook-dir examples
ansible-inventory -i examples/inventory.sccfm.yml --list --playbook-dir examples
```

**Host variables** available on each device:
- `sccfm_uid`, `sccfm_name`, `sccfm_region`
- `sccfm_device_type`, `sccfm_connectivity_state`, `sccfm_config_state`
- `sccfm_software_version`

## Playbook patterns

### Standard playbook structure
All playbooks targeting SCCFM modules run on `localhost` with `gather_facts: false`:

```yaml
---
- name: Descriptive play name
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/cisco.sccfm.all:
      region: "{{ sccfm_region }}"
      api_token: "{{ sccfm_api_token }}"

  tasks:
    - name: Descriptive task name
      cisco.sccfm.<module_name>:
        param1: value1
      register: result

    - name: Display result
      ansible.builtin.debug:
        var: result
```

### Running playbooks
```bash
# With vault
ansible-playbook examples/<playbook>.yml --vault-password-file examples/.vault_pass

# With extra variables
ansible-playbook examples/<playbook>.yml --vault-password-file examples/.vault_pass -e "target_version=9.20(3)13"

# Dry run (check mode)
ansible-playbook examples/<playbook>.yml --vault-password-file examples/.vault_pass --check

# Or run interactively via devkit
devkit
# select "run-ansible"
```

### Device targeting patterns
Modules that operate on devices accept these filtering parameters:
- `query` — filter expression (e.g., `"connectivityState:ONLINE AND name:branch-*"`)
- `uids` — list of device UIDs
- `limit` / `offset` — pagination

## Existing examples

Reference playbooks are in `sccfm-ansible/examples/`. List them:
```bash
ls sccfm-ansible/examples/*.yml | sed 's|.*/||' | sort
```

## Testing

### Unit tests
Module unit tests live in `sccfm-ansible/plugins/modules/tests/`:
```bash
pytest sccfm-ansible/plugins/modules/tests/ -v
```

### E2E integration tests
End-to-end tests in `sccfm-ansible/e2e/` run actual playbooks against a live environment:
```bash
# Via the runner script (checks vault setup, installs collection, runs pytest)
bash sccfm-ansible/e2e/run_e2e.sh

# Or via devkit
devkit
# select "run-e2e"
```

## Architecture reference

If you need to understand how a module works internally:
- **Modules:** `sccfm-ansible/plugins/modules/` — each is a standalone Ansible module
- **Module utils:** `sccfm-ansible/plugins/module_utils/` — shared helpers:
  - `config.py` — `Config` dataclass, `base_argument_spec()`, `identifier_argument_spec()`, `create_config()`
  - `operations.py` — `run_delete_with_idempotency()`, `fetch_object_by_identifier()`, `fields_need_update()`
  - `loaders/inventory_loader.py` — `InventoryLoader` with auto-pagination
  - `builders/inventory_host_builder.py` — `InventoryHostBuilder` for dynamic inventory
- **Business logic:** `sccfm_core/services/` — shared with the CLI
- **Unit tests:** `sccfm-ansible/plugins/modules/tests/`
- **E2E tests:** `sccfm-ansible/e2e/`

Use `ansible-doc` first, then read module source if you need deeper parameter details.

## Writing new modules

Every module follows this exact structure. Read an existing module as a template (e.g., `create_access_rule.py` for mutating, `list_network_objects.py` for read-only).

### Required structure

```python
from __future__ import annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule

from sccfm_core.services.<domain> import <Service>

from ..module_utils.config import Config, base_argument_spec, create_config

DOCUMENTATION = r"""..."""
EXAMPLES = r"""..."""
RETURN = r"""..."""


def build_argument_spec() -> dict[str, dict[str, Any]]:
    return {
        "my_param": {"type": "str", "required": True},
        **base_argument_spec(),
    }


def run_module() -> None:
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )
    config: Config = create_config(module)

    try:
        service = Service(config=config)

        if module.check_mode:
            module.exit_json(changed=True, msg="Would perform action")
            return

        result = service.do_thing(...)
        module.exit_json(changed=True, msg="Success", data=result.to_dict())
    except Exception as e:
        module.fail_json(msg=f"Failed to perform action: {str(e)}")


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()
```

### Key patterns

- **Read-only modules:** `changed=False` always. Check mode returns empty results.
- **Mutating modules:** `changed=True` on success. Check mode returns `changed=True` with empty/stub data.
- **Idempotent deletes:** Use `run_delete_with_idempotency()` — handles `NotFoundError` → `changed=False`.
- **Idempotent updates:** Use `fields_need_update()` — skips update if nothing changed.
- **Object lookups:** Use `fetch_object_by_identifier()` with `identifier_argument_spec()`.
- **All modules** must use `base_argument_spec()` to merge `region` + `api_token` params.
- **All modules** must set `supports_check_mode=True`.
- Follow Python type hints strictly (project requirement).

## User request: $ARGUMENTS

Help the user accomplish: **$ARGUMENTS**

**Approach:**
1. Activate the environment: `source scripts/activate.sh` (re-run in every new terminal)
2. Confirm the collection is installed (`ansible-doc -l -t module cisco.sccfm` should list modules); if not, run `build-ansible-collection`.
3. Check vault/credentials are set up; if not, help configure with `change-tokens`.
4. Identify which module(s) or inventory features are needed.
5. Run `ansible-doc cisco.sccfm.<module>` to get exact parameters — never guess.
6. Write or run the playbook, following the standard patterns above.
7. If writing a new playbook, place it in `sccfm-ansible/examples/`.
8. Explain the results and any next steps.
