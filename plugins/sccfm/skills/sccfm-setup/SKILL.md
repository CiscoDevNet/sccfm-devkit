---
name: sccfm-setup
description: Set up, repair, or remove the local Cisco SCC Firewall Manager agent runtime, including sccfm-cli, the matching cisco.sccfm Ansible collection, named-profile authentication, verification, and safe teardown. Use for first-time setup, installation, upgrades, authentication guidance, setup diagnostics, uninstall, or teardown. Do not use for ordinary SCCFM operations after setup; use sccfm-cli or sccfm-ansible instead.
allowed-tools: "Bash(python3 *) Bash(pipx *) Bash(sccfm-cli *) Bash(ansible-doc *) Bash(ansible-galaxy *) Read"
---

# SCC Firewall Manager Setup

Guide the user through a safe, resumable setup. Keep secrets out of chat and do
not install or replace software until the user approves the exact plan.

## Setup modes

- **Check:** inspect the current runtime without changing it.
- **Install or upgrade:** install one stable, matching CLI and collection version.
- **Authenticate:** configure a named SCCFM profile through the CLI's hidden prompt.
- **Repair:** rerun checks and change only the failed component.
- **Uninstall:** remove the managed Galaxy collection and pipx environment, preserving profiles by default.

## 1. Inspect first

Resolve this skill's plugin root, then run:

```bash
python3 scripts/setup_runtime.py doctor --json
```

Summarize missing commands, detected versions, schema availability, collection
discovery, and whether a profile file exists. Never read or display the profile
file contents.

Python 3.12 or later and `pipx` are prerequisites for the managed installation.
If either is missing, explain the smallest platform-appropriate installation
step and wait for approval before changing the machine.

## 2. Plan installation

Use a stable release that exists for both `cisco-sccfm-devkit` on PyPI and
`cisco.sccfm` on Ansible Galaxy. Do not guess a version or mix versions. If the
user did not select one, inspect the official release sources and propose the
latest matching stable version.

Select an available Python 3.12 executable from the doctor report. Generate the
exact plan without executing it:

```bash
python3 scripts/setup_runtime.py plan --version X.Y.Z --python python3.12
```

Explain that the plan installs the Python package with `pipx`, injects Ansible
into that same environment so modules can import `cisco_sccfm_core`, and installs
the collection at the identical version. The helper installs the collection at
the standard per-user path
`~/.ansible/collections/ansible_collections/cisco/sccfm` and records that exact
owned path in `~/.sccfm-agent-plugin/runtime.json`. If the target collection
already exists without that ownership record, stop and ask the user to resolve
the pre-existing installation; never overwrite or adopt it automatically.

Require the exact confirmation `INSTALL SCCFM X.Y.Z`. Only then run:

```bash
python3 scripts/setup_runtime.py install --version X.Y.Z --python python3.12 --yes
```

Do not use `--yes` before receiving that confirmation. Do not install from an
unreviewed branch, draft release, or mismatched artifact set.

## 3. Configure authentication

SCCFM API tokens belong in the canonical named-profile store, never in chat,
shell history, playbooks, `.env` files, or Ansible Vault.

Ask which profile name and region the user wants. Then tell the user to run the
schema-documented configure command locally so the token is entered through its
hidden prompt. The default-profile shape is:

```bash
sccfm-cli configure --region <canonical-region>
```

For a non-default profile, place the schema-declared global profile option before
the command path. Derive accepted regions and all option names from
`sccfm-cli schema export --format json`; do not invent them. Tokens are created
in the SCC Firewall Manager UI or the linked Cisco developer authentication
flow. Never ask the user to paste a token into the conversation.

The same profile is consumed by `sccfm-cli` and the `cisco.sccfm` collection.
Ansible Vault remains only for playbook-specific device secrets.

## 4. Verify

Rerun the doctor. Then use the `sccfm-cli` skill to discover and run the
schema-declared read-only connectivity/status operation. Use the `sccfm-ansible`
skill to verify module, inventory, and lookup discovery through `ansible-doc`.

Setup is complete only when:

- CLI schema export succeeds;
- CLI, Python package, and Ansible collection versions match;
- the selected profile passes a read-only connectivity check;
- `ansible-doc` discovers the installed collection; and
- one harmless read-only operation succeeds, if the user permits live validation.

If a check fails, stop at that component. Do not reinstall everything or retry
authentication with another profile unless the user chooses that action.

## 5. Uninstall and teardown

Teardown must happen before the plugin itself is removed, because uninstalling
the plugin does not remove the pipx environment, Galaxy collection, or profile
store. Resolve this skill's plugin root and generate a removal plan:

```bash
python3 scripts/setup_runtime.py uninstall-plan
```

The helper discovers `cisco.sccfm` through `ansible-galaxy`, validates each
reported collection path, selects only the path matching its runtime ownership
record, confirms that `sccfm-cli` belongs to the managed pipx environment, and
preserves unowned collection copies. The helper preserves `~/.sccfm-cli/config.json` by default.
Show the full plan and require the exact confirmation `UNINSTALL SCCFM`. Only
then run:

```bash
python3 scripts/setup_runtime.py uninstall --yes
```

The helper removes only its recorded Galaxy collection before uninstalling the
pipx environment. If discovery or ownership validation fails, stop; never guess
a collection directory, delete another reported copy, or construct a broad
recursive-delete command.

Deleting named profiles and their API tokens is a separate destructive choice.
Only when the user explicitly asks to delete them, generate the expanded plan:

```bash
python3 scripts/setup_runtime.py uninstall-plan --remove-profiles
```

Require the exact confirmation `UNINSTALL SCCFM AND DELETE PROFILES`, then run:

```bash
python3 scripts/setup_runtime.py uninstall --remove-profiles --yes
```

After runtime teardown succeeds, tell the user how to remove the plugin. Use
`/plugin uninstall sccfm@sccfm-devkit` in Claude Code or
`codex plugin remove sccfm@sccfm-devkit` in Codex. Marketplace removal is
optional and separate.

## Safety boundary

This skill manages setup and teardown only. After setup, route CLI work to
`sccfm-cli` and Ansible work to `sccfm-ansible`. Those skills may execute
verified read-only operations. Mutating operations require a reviewed plan, the
exact command, and the explicit confirmation phrase defined by the operational
skill.
