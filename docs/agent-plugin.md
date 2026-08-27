---
layout: page
title: SCC Firewall Manager Agent Plugin
---

# SCC Firewall Manager Agent Plugin

The `sccfm` plugin gives Claude Code and Codex a supported way to install,
configure, inspect, and operate Cisco Security Cloud Control Firewall Manager
from natural-language requests. It packages three focused skills rather than one
large general-purpose instruction file:

| Component | Responsibility |
|---|---|
| `sccfm-setup` | Diagnose prerequisites, plan a version-matched installation, guide authentication, verify the runtime, and safely remove managed setup artifacts. |
| `sccfm-cli` | Discover the installed CLI schema and generate or execute validated CLI commands. |
| `sccfm-ansible` | Discover the installed collection with `ansible-doc` and generate or execute validated Ansible automation. |
| Cross-agent command guard | Require explicit authorization when a shell command is not proven read-only. |

The plugin does not contain an SCCFM API token, duplicate the SCCFM API, or
provide a separate MCP server. It teaches the agent to use the published CLI and
Ansible collection safely.

## Goals

The first release is intended to provide one installable package that:

- supports Claude Code and Codex from the same repository;
- installs compatible CLI and Ansible artifacts instead of letting their
  versions drift;
- guides users through local token configuration without asking them to paste a
  token into chat;
- discovers commands, flags, modules, and parameters from the installed tools;
- runs verified read-only operations with minimal friction;
- requires review and explicit confirmation before changing SCCFM or a managed
  device; and
- fails closed when the command, target, credentials, or safety classification
  is unclear.

## Capabilities

### Runtime setup and repair

The setup skill can:

- detect Python 3.12, `pipx`, `sccfm-cli`, `ansible-doc`, and
  `ansible-galaxy`;
- report whether an SCCFM profile exists without reading or displaying its
  contents;
- export CLI schema metadata and discover the installed Ansible collection;
- detect a mismatch between the CLI and collection versions;
- produce an exact installation plan without executing it;
- install a selected stable version after the user types
  `INSTALL SCCFM X.Y.Z`; and
- plan and remove the Galaxy collection and managed pipx environment after
  explicit teardown confirmation; and
- verify schema discovery, collection discovery, authentication readiness, and
  a harmless read-only operation.

The managed installation uses `pipx` for the Python package, injects
`ansible-core` into the same isolated environment, and installs the identical
`cisco.sccfm` Galaxy collection version. Keeping Ansible and
`cisco_sccfm_core` in the same Python environment prevents module import
failures. The collection is installed at the standard per-user Galaxy path and
the helper stores an ownership record for that exact directory. It refuses to
overwrite a pre-existing collection that it cannot prove it owns.

### Authentication guidance

The setup skill directs users to the CLI's hidden local prompt. The API token is
stored in the canonical named-profile store used by both `sccfm-cli` and the
Ansible collection.

The agent must not:

- ask for the token in chat;
- place it on the command line;
- echo or log it;
- copy it into a playbook, `.env` file, or Ansible Vault; or
- inspect the contents of the profile store during diagnostics.

Ansible Vault remains appropriate for playbook-specific secrets such as managed
device passwords, but not for the SCCFM API token.

### CLI operations

The CLI skill exports `sccfm-cli schema export --format json` once per session
and treats that schema as the source of truth. It can:

- match a natural-language request to a command path;
- validate required options and option constraints;
- normalize regions using schema-declared values;
- translate supported natural-language filters into schema-declared queries;
- select named profiles;
- generate a command without executing it;
- run a verified read-only command; and
- preflight and plan a mutating command before asking for confirmation.

It does not guess missing commands, flags, query fields, targets, or defaults.

### Ansible operations

The Ansible skill uses `ansible-doc` as its runtime schema. It can:

- discover modules, inventory plugins, and lookup plugins;
- inspect required parameters, choices, examples, return values, and secret
  fields;
- generate playbooks and inventory configuration;
- run syntax checks and inventory validation;
- run documented read-only automation;
- use check mode for mutations when the module supports it; and
- present an execution plan before a mutating playbook runs.

When the documentation does not prove an Ansible action is read-only, the skill
classifies it as mutating.

### Generate-only mode

Users can ask for a command or playbook without allowing execution. The agent
may still perform local schema discovery and harmless validation unless the user
also prohibits those checks. It then returns the exact command or playbook and
states whether it was validated against live state.

## Safety model

Every operation is assigned one of three classes:

| Class | Meaning | Agent behavior |
|---|---|---|
| A | Read-only with no local writes | May execute after command, profile, and target validation. |
| B | Read-only against SCCFM but writes a local profile, file, or export | Requires explicit opt-in and an explicit destination when applicable. |
| C | May modify SCCFM, a managed device, credentials, deployment state, or other local state | Requires a plan, preflight when available, exact targets, and typed confirmation. |

For a CLI mutation, the final confirmation has this shape:

```text
EXECUTE <exact shell command>
```

For an Ansible mutation, it has this shape:

```text
EXECUTE <exact ansible-playbook shell command>
```

Production, upgrade, credential, broad-target, and bulk mutations require two
separate confirmations: approval of the plan followed by the exact `EXECUTE`
message. The text after `EXECUTE ` must exactly match the shell command shown in
the plan.

Claude Code and Codex load the conventional shared `hooks/hooks.json` manifest,
with a root `hooks.json` compatibility copy kept in sync. Both use the same
host-aware guard. The agent places
`SCCFM_APPROVAL_COMMAND: <exact shell command>` on a standalone line only after
presenting a complete mutation plan. The `Stop` hook stores that planned
command's SHA-256 digest, never its contents. A later standalone exact-command
confirmation creates a ten-minute, one-use execution receipt only when its
digest matches the previously stored plan. Edited commands—including adding or
removing `--check`—cannot authorize themselves. Mutating, locally-writing, and
Ansible execution commands are blocked without a matching receipt. Claude
requests interactive host approval after consuming the receipt; Codex continues
through its native sandbox and permission flow. If the agent does not attempt the
command in that turn, the `Stop` hook clears the unused receipt. Schema-proven
read-only commands continue without a receipt. Compound, nested, unknown, and
sensitive-argv commands cannot receive a receipt.

## End-user workflow

### 1. Install the plugin

Claude Code:

```text
/plugin marketplace add CiscoDevNet/sccfm-devkit
/plugin install sccfm@sccfm-devkit
```

Codex:

```bash
codex plugin marketplace add CiscoDevNet/sccfm-devkit
codex plugin add sccfm@sccfm-devkit
```

These GitHub installation commands become the supported public path after the
plugin changes are merged into the repository's default branch.

### 2. Ask for setup

The user can start with:

```text
Set up SCC Firewall Manager for this machine.
```

The agent first runs diagnostics. If installation or repair is required, it
shows the exact commands and selected version. Nothing is installed until the
user sends the requested `INSTALL SCCFM X.Y.Z` message.

### 3. Configure a profile locally

The agent asks for a profile name and region, then directs the user to a local
CLI configuration flow. Token entry happens in the CLI's hidden prompt, not in
the agent conversation. The resulting profile is shared by CLI and Ansible
operations.

### 4. Make natural-language requests

The user describes the desired outcome. The plugin automatically routes setup
questions to `sccfm-setup`, CLI tasks to `sccfm-cli`, and playbook or collection
tasks to `sccfm-ansible`.

### 5. Review changes before execution

For mutations, the agent resolves the exact target, runs available preflight or
check-mode validation, explains the intended effect, and displays the exact
command. The command runs only after the required confirmation message and host
approval.

### 6. Uninstall and teardown

Plugin removal and runtime teardown are separate operations. `/plugin uninstall`
or `codex plugin remove` removes the agent plugin but leaves its pipx environment,
Galaxy collection, and profile store behind.

While the plugin is still installed, ask:

```text
Uninstall the SCCFM runtime installed by this plugin.
```

The setup skill resolves its plugin root and runs the plan-only helper:

```bash
python3 scripts/setup_runtime.py uninstall-plan
```

The plan validates the `cisco.sccfm` directories positively reported by
`ansible-galaxy`, then selects for removal only the path matching the helper's
ownership record at `~/.sccfm-agent-plugin/runtime.json`. It verifies that the
CLI belongs to the managed pipx environment and preserves every unowned Galaxy
copy plus `~/.sccfm-cli/config.json` by default. After the user sends the exact
confirmation `UNINSTALL SCCFM`, the agent runs:

```bash
python3 scripts/setup_runtime.py uninstall --yes
```

Removal order matters: the helper removes its recorded Galaxy collection while
`ansible-galaxy` is still available, deletes the ownership record, then
uninstalls `cisco-sccfm-devkit` with pipx. It refuses to guess an installation
path, remove another reported collection copy, or remove an unmanaged CLI.

To also delete named profiles and their API tokens, the user must request that
separately. The agent shows:

```bash
python3 scripts/setup_runtime.py uninstall-plan --remove-profiles
```

and requires `UNINSTALL SCCFM AND DELETE PROFILES` before running:

```bash
python3 scripts/setup_runtime.py uninstall --remove-profiles --yes
```

The helper deletes only the canonical profile file and never reads or displays
its contents. After teardown succeeds, remove the plugin:

Claude Code:

```text
/plugin uninstall sccfm@sccfm-devkit
```

Codex:

```bash
codex plugin remove sccfm@sccfm-devkit
```

Marketplace removal is optional and separate.

## Examples

### Check the installation

User:

```text
Check whether my SCCFM CLI and Ansible setup is healthy.
```

Expected behavior:

1. Inspect prerequisites and versions without changing the machine.
2. Confirm whether the profile file exists without reading its contents.
3. Export CLI schema metadata and run Ansible discovery.
4. Report missing dependencies or version drift with the smallest corrective
   action.

### Run a read-only CLI request

User:

```text
Show the SCCFM subsystem status for my default profile.
```

Expected behavior:

1. Export and inspect the live CLI schema.
2. Verify that the matched command is read-only and requires no local write.
3. Validate the default profile.
4. Run the command and summarize its result.

### List devices using a named profile

User:

```text
Using my lab profile, list the first 20 SCCFM devices as JSON.
```

Expected behavior:

1. Resolve the schema-declared device-list operation.
2. Place the global profile option before the command path.
3. Use only schema-declared pagination and output options.
4. Execute the read-only request and summarize the relevant fields.

### Generate a mutation without running it

User:

```text
Generate the command to change the boot image for ASA branch-01. Do not run it.
```

Expected behavior:

1. Select generate-only mode.
2. Resolve the command and required parameters from the live schema.
3. Perform read-only target resolution or preflight when allowed.
4. Return the exact command, clearly marked as not executed.
5. Do not request an `EXECUTE` confirmation.

### Execute a mutation

User:

```text
Change the boot image for ASA branch-01 to disk0:/asa-new.bin.
```

Expected behavior:

1. Prove the command is mutating from the live schema.
2. Resolve `branch-01` to an unambiguous target.
3. Run the schema-declared check or preflight mode.
4. Present the profile, target, intended change, preflight result, and exact
   command.
5. Emit `SCCFM_APPROVAL_COMMAND: ` followed by that exact command on a standalone
   line, then ask for `EXECUTE ` followed by the same command.
6. Execute only after that message and host approval.

### Generate an Ansible playbook

User:

```text
Create an Ansible playbook that lists SCCFM network objects using my staging
profile, but do not run it.
```

Expected behavior:

1. Discover the matching module and parameters with `ansible-doc`.
2. Use the named profile through the collection's documented profile mechanism.
3. Avoid embedding the SCCFM token.
4. Generate the playbook and run a local syntax check when permitted.
5. Return the file and execution command without contacting SCCFM.

### Plan a broad Ansible change

User:

```text
Update this access rule across the production target group with Ansible.
```

Expected behavior:

1. Discover and classify the module as mutating.
2. Inspect the inventory and show the exact target count.
3. Validate syntax and run check mode when supported.
4. Present a plan and request the first confirmation.
5. Emit `SCCFM_APPROVAL_COMMAND: ` followed by the exact `ansible-playbook`
   command on a standalone line, then request a separate `EXECUTE ` message
   containing the same command.
6. Execute only after both confirmations and host approval.

## Deliberate boundaries

The first release does not:

- publish or rotate SCCFM API tokens;
- execute an ambiguous or unclassified operation;
- bypass Claude Code or Codex permissions;
- guarantee transactional rollback for SCCFM changes;
- install prerelease or mismatched artifacts;
- automatically retry failed mutations;
- replace the generated CLI and Ansible reference documentation; or
- provide identical hook enforcement on every agent host.

The skills are the portable policy layer. Host permissions, sandboxing, and the
shared Claude Code/Codex hooks provide additional enforcement where available.

## Maintenance model

The canonical operational skills remain under `skills/`. Before release, the
plugin copies must be synchronized and checked:

```bash
python3 plugins/sccfm/scripts/sync_skills.py
python3 plugins/sccfm/scripts/sync_skills.py --check
```

The plugin and all three skills must pass their validators. The setup helper,
command guard, manifest alignment, secret-safe diagnostics, and copied-skill
integrity are covered by automated tests.
