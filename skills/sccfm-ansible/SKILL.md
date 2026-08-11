---
name: sccfm-ansible
description: Use the cisco.sccfm Ansible collection for SCC Firewall Manager by discovering modules and inventory plugins with ansible-doc at runtime, validating parameters, auth, check mode, and safety before generating or running playbooks. Use for cisco.sccfm Ansible modules, inventory, vault, and playbook workflows. Do NOT use for sccfm-cli commands; use the sccfm-cli skill instead. Do not use for Jira/Confluence work, architecture design, or non-Ansible tasks.
allowed-tools: "Bash(command -v *) Bash(source cisco_sccfm_scripts/activate.sh) Bash(ansible-doc *) Bash(ansible-playbook *) Bash(ansible-inventory *) Bash(ansible-vault *) Bash(ansible-galaxy *) Bash(build-ansible-collection) Bash(devkit *) Bash(jq *) Read Grep Glob Write Edit"
---

# SCC Firewall Manager Ansible Collection

Generate or run `cisco.sccfm` Ansible automation by dynamically discovering the
installed collection with `ansible-doc`. Treat `ansible-doc` JSON output as the
schema for modules, inventory plugins, options, examples, return values, and
secret handling. Do not hardcode module names, parameters, examples, choices, or
behavior.

This skill operates against customer SCC Firewall Manager environments and
managed devices. Optimize for customer safety first and convenience second.

## Scope: Ansible vs. CLI

This skill covers only the `cisco.sccfm` Ansible collection (modules and the
inventory plugin). For `sccfm-cli` command-line invocations, use the `sccfm-cli`
skill. For requests spanning both surfaces, apply each skill only to its
respective operations.

## Core Rules

1. Run `ansible-doc` before writing, running, or answering detailed questions
   about any `cisco.sccfm` module or inventory plugin.
2. Prefer stopping over guessing. If module match, target identity, region,
   credentials, inventory, or safety class is ambiguous, ask the user or switch
   to Generate-Only.
3. Never improvise module names, parameters, defaults, target lists, inventory
   files, vault paths, or output paths.
4. Never ask the user to paste secrets into chat.
5. Use Ansible Vault, environment variables, or existing local variable files
   for secrets; never put API tokens or device passwords directly in playbooks.
6. Treat any task as mutating unless `ansible-doc`, examples, and source context
   prove it is read-only.
7. Use fully qualified collection names, such as `cisco.sccfm.<module>`, in
   playbooks.

## Execution Modes

Select one execution mode for each user request.

### Mode 1: Execute

Use this mode when the user asks you to perform the Ansible operation.

- You may run discovery, syntax checks, inventory checks, dry runs, and readonly
  playbooks, subject to the safety rules below.
- Never execute a mutating playbook immediately. Build a plan, run check mode
  or another preflight when available, and require confirmation.
- If credentials are missing or intent is ambiguous, default to Generate-Only.

### Mode 2: Generate-Only

Use this mode when the user says anything like "show me the playbook",
"generate the playbook", "show me the command", "do not run it", "don't run
it", "I will run it myself", or "command only".

In Generate-Only mode:

- Never execute the final business playbook or inventory query.
- You may still run `ansible-doc` because discovery depends on it.
- You may run local syntax checks on generated playbooks when no live
  credentials are required and the user did not forbid all execution.
- If the user forbids all command execution and no cached `ansible-doc` schema
  is available, stop and explain that safe generation requires module
  discovery.
- Always return exact commands or playbook snippets in fenced code blocks.
- Mark generated automation as `not validated against live state` when live
  preflight was not allowed or credentials were unavailable.

## Safety Model

Classify the playbook or command before execution. Ansible does not expose the
same explicit `readonly` schema field as `sccfm-cli`, so classify from
`ansible-doc` descriptions, examples, options, return docs, and source only when
needed. If classification is unclear, use Class C.

### Class A: Readonly, no local writes

Use Class A only when the matched module or inventory action is clearly
read-only and the invocation does not write local files.

Signals include:

- `ansible-doc` describes list, get, show, inspect, validate, or health-check
  behavior.
- The task does not create, update, delete, onboard, deploy, trigger, clear,
  execute arbitrary device commands, change credentials, or change managed
  device state.
- The command does not redirect output to a file and does not use modules such
  as local copy/template/file/write operations.

These commands are safe to execute after discovery and credential validation.

### Class B: Readonly, local-write/export side effects

Use Class B when the operation is read-only against SCCFM but writes local data.

Examples include saving inventory output, writing reports, creating local
playbook artifacts, or exporting customer data to a path. Require explicit user
opt-in and an explicit destination path before executing. Never rely on a
default path for customer data.

### Class C: Mutating SCCFM or managed devices

Use Class C when the operation may modify SCCFM, a managed device, local
credential state, or any deployment/upgrade workflow.

Signals include:

- `ansible-doc` describes creating, updating, deleting, adding, removing,
  onboarding, deploying, triggering, clearing, applying, editing, executing CLI
  commands, changing passwords, changing boot images, or changing defaults.
- The task writes SCCFM objects, device configuration, licensing/deployment
  state, shun state, object overrides, access rules, local users, firmware, or
  credentials.
- The source or docs are unclear.

Class C requires a plan, preflight when possible, and explicit confirmation
before execution.

## Prerequisites

### Step A: Resolve Ansible and the Collection

Follow these checks in order:
1. Run `command -v ansible-doc`.
2. If you are inside this repository, `ansible-doc` is missing, and
   `cisco_sccfm_scripts/activate.sh` exists, run `source cisco_sccfm_scripts/activate.sh` once for the
   shell session, then resolve again. Do not use `poetry run`.
3. Run discovery:

   ```bash
   ansible-doc -j -l -t module cisco.sccfm
   ```

4. If discovery fails and you are inside this repository, run both commands,
   then rerun discovery:

   ```bash
   build-ansible-collection
   ansible-galaxy collection install dist/cisco-sccfm-*.tar.gz --force
   ```

5. If discovery succeeds and you are inside this repository, compare discovered
   module FQCNs with `sccfm-ansible/plugins/modules/*.py` only to detect a stale
   installed collection. If source modules are missing from `ansible-doc`, build
   and install the generated tarball as above, then rerun discovery. Do not use source filenames as the module schema.
6. If you are outside this repository, install or modify local Ansible state only
   when the user explicitly asks for setup. Otherwise, stop and explain that the
   `cisco.sccfm` collection is not installed.

Re-discover if the virtualenv, collection install, or branch changes.

### Step B: Discover Runtime Schema

Export the module list once per session:

```bash
ansible-doc -j -l -t module cisco.sccfm
```

For a matched module, fetch full JSON docs:

```bash
ansible-doc -j cisco.sccfm.<module_name>
```

For dynamic inventory work, list inventory plugins, then fetch the matched plugin docs:
```bash
ansible-doc -j -l -t inventory cisco.sccfm
ansible-doc -j -t inventory <inventory_plugin_fqcn>
```

Parse the JSON output. Use these fields as the schema:

- module or plugin FQCN
- short description and description
- `doc.options`: parameter names, types, required flags, defaults, choices,
  `elements`, `env`, and `no_log`
- examples
- return values
- plugin type and inventory options

Cache the discovered JSON in memory for the session. Do not use stale docs after
building or reinstalling the collection.

If discovery fails, stop and report the error. Do not guess what the collection
supports.

The discovery commands above are the only hardcoded bootstrap commands. They are
the Ansible equivalent of schema export: all module, inventory plugin,
parameter, example, and return-value knowledge must come from the discovered
`ansible-doc` JSON.

### Step C: Verify Credentials Without Exposing Secrets

Use the matched docs to identify credential options. Most modules support
`region` and `api_token`; inventory docs expose their own auth options.

Rules:

1. Prefer `module_defaults: group/cisco.sccfm.all:` for module auth.
2. Prefer Ansible Vault for API tokens and device passwords.
3. Environment variables are acceptable when `ansible-doc` documents them, such
   as `SCCFM_REGION` and `SCCFM_API_TOKEN`.
4. Never ask for token or password contents in chat.
5. Never print decrypted vault contents.
6. Never write real secrets to tracked files.
7. If credentials are missing, generate the playbook with placeholders or tell
   the user which local setup command to run.
8. Use Write/Edit only for non-secret playbook, inventory, vars template, or
   documentation artifacts.

Use `change-tokens` for local credential setup only when the user explicitly asks for it. It
configures `.env`, CLI profile state, Ansible vars, and encrypted vault files. Its default Ansible
path is `sccfm-ansible/examples`; generated credential files there are Git-ignored and excluded
from collection artifacts. Use `--path` only when the user supplies a different examples directory.

## Step 1: Match User Intent Conservatively

Derive the user's request into this structured shape before matching modules:

- requested action
- target object or device type
- target identity, query, inventory group, or host pattern
- desired state or operation
- region
- whether they asked to read, export, or modify
- whether they want a playbook, an ad hoc command, inventory output, or a dry run

Then match modules using this algorithm:

1. Filter the discovered module list by exact tokens in FQCN, short
   description, and description.
2. Fetch full docs for every plausible candidate.
3. Reject candidates whose documented behavior conflicts with the user's intent.
4. Prefer modules whose documented action and object type both match exactly.
5. Use the inventory plugin only for inventory/discovery requests.
6. If exactly one candidate remains, use it.
7. If multiple plausible candidates remain, show the candidates and ask the user
   to choose.
8. If no candidate matches, say so clearly and stop.

Never choose between ambiguous modules by vibe. Ask or stop.

## Step 2: Build the Playbook or Command

Construct automation strictly from the matched `ansible-doc` entry.

### Required Inputs

1. Check every option where `required` is true.
2. Gather values from the user's request, inventory variables, group vars, or
   existing variable files.
3. If a required value is missing, ask for it or leave a clear placeholder in
   Generate-Only mode.
4. Enforce `choices`, `type`, and `elements` exactly as documented.

### Natural-Language Filters and Queries
If the user describes a filter in natural language, such as "online ASAs",
"devices named branch-*", or "FTDs not on the recommended version", translate it
only through documented Ansible options and discovered inventory variables.

1. Use only options exposed by the matched `ansible-doc` entry.
2. If an option named `query` exists, read its current description before using
   it. Do not assume it accepts Lucene, field:value filters, or the same syntax
   as `sccfm-cli`.
3. If the docs describe only a narrow query behavior, such as a name filter,
   generate only that documented behavior.
4. If the user wants filtering by inventory host metadata, first discover the
   inventory plugin docs, then verify host variables from generated docs or
   source context; use only verified host variables.
5. If no documented option or host variable supports the requested filter, ask
   for the exact supported filter or propose a readonly list/inventory step plus
   local post-filtering. Do not invent query fields or values.

### Auth Pattern

For SCCFM modules, prefer this shape when `region` and `api_token` are supported:

```yaml
module_defaults:
  group/cisco.sccfm.all:
    region: "{{ lookup('env', 'SCCFM_REGION') }}"
    api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
```

Do not repeat `region` or `api_token` inside each task unless the user asks for a
self-contained snippet or the docs require task-local values.

### Play Targets

Use `hosts: localhost` and `gather_facts: false` for SCCFM API operations unless
the user specifically wants to target hosts from the dynamic inventory.

### Ansible Command Shape

Build commands in this shape:

```text
ansible-playbook [ansible CLI options] <playbook.yml>
ansible-inventory -i <inventory.yml> [ansible inventory options]
```

Module parameters belong in YAML under `cisco.sccfm.<module_name>`. Inventory
plugin options belong in the inventory YAML file. Never turn module or inventory
plugin parameters into `ansible-playbook` CLI flags unless Ansible itself
documents that flag.

For inventory-driven tasks:

1. Discover the inventory plugin docs.
2. Build an inventory file with only options documented by the plugin.
3. Validate it with `ansible-inventory` before running playbooks when
   credentials are available.

### Secret Parameters

For every option where `no_log: true` is documented, or whose name or description indicates a token, password, key, or secret:

- Use a vault variable, environment lookup, or placeholder.
- Do not place real values in generated artifacts.
- Do not print resolved values.

## Step 3: Validate Before Execution

Run validation appropriate to the selected mode and safety class.

### Always Safe Validation

These do not contact SCCFM:

```bash
ansible-doc -j -l -t module cisco.sccfm
ansible-doc -j cisco.sccfm.<module_name>
ansible-playbook --syntax-check <playbook.yml>
```

Use `--syntax-check` on generated playbooks whenever a playbook file exists and
the user did not forbid local validation.

### Inventory Validation

When credentials are available and the user requested inventory behavior:

```bash
ansible-inventory -i <inventory.yml> --graph --playbook-dir <playbook_dir>
```

Use `--list`, `--yaml`, or `--graph --vars` only after confirming that the inventory and all
adjacent `group_vars`/`host_vars` are secret-free. These formats can print variables loaded by
Ansible even though the SCCFM inventory plugin itself never exports its authentication token.

If credentials are missing, validate only the file shape and mark it as not
validated against live SCCFM.

### Check Mode

For Class C playbooks, run check mode before execution whenever the matched
module supports it and credentials are available:

```bash
ansible-playbook -i <inventory> <playbook.yml> --check
```

If `ansible-doc` does not expose check-mode support, inspect the module source
only when you are in this repository. Look for `supports_check_mode=True` and a
real `module.check_mode` path. If support is missing or unclear, say so and do
not execute without explicit approval.

## Step 4: Execution Policy

Apply these rules after selecting execution mode.

### Class A: Readonly, No Local Writes

In Execute mode, run the playbook or inventory command after validation if:

- the module or inventory match is unambiguous
- region and credentials are available
- required options are satisfied
- the operation is documented as read-only

In Generate-Only mode, return the exact playbook and command, and state whether
it was syntax-checked or live-validated.

### Class B: Readonly, Local Writes or Exports

In Execute mode, before executing:

1. Confirm the user wants the local write/export.
2. Require an explicit destination path.
3. State what will be written and where.
4. Do not use schema or example defaults for customer data paths.

In Generate-Only mode, require an explicit destination path before generating the
write/export command or playbook.

### Class C: Mutating SCCFM or Managed Devices

In Execute mode, never execute immediately. Use this workflow:

1. Validate the module match, region, credentials, and all required options.
2. Resolve targets to an unambiguous host pattern, UID, object identifier, or
   exact target count.
3. Run `ansible-playbook --syntax-check`.
4. Run `ansible-playbook --check` when supported and credentials are available.
5. If check mode is unavailable or not meaningful, say so explicitly and stop
   unless the user approves proceeding without it.
6. Present an execution plan containing:
   - module FQCN
   - region
   - inventory or host pattern
   - target selector or target count
   - intended change
   - check-mode/preflight result
   - exact command that will be executed
7. Require explicit confirmation before execution.

In Generate-Only mode, validate as far as allowed, mark whether syntax check and
live preflight were performed, return the exact playbook/command, and do not
execute the mutating playbook.

#### Confirmation Rules for Mutating Playbooks

These confirmation rules apply only in Execute mode.

For any Class C playbook, require the user to send the exact confirmation phrase
you provide:

```text
EXECUTE cisco.sccfm <module-fqcn> <target-summary>
```

For production, deployment, upgrade, credential, or bulk mutations, require two
confirmations:

1. A first confirmation that they want to proceed with the plan.
2. A second message containing the exact `EXECUTE ...` phrase.

#### Red Lines for Mutating Playbooks

Never execute Class C automation when any of these is true:

- the module match is ambiguous
- region or credentials are ambiguous
- targets are vague or unresolved
- a bulk target list has not been inspected
- required parameters are missing
- secrets would be exposed in chat or committed to disk
- check mode is unavailable and the user has not explicitly accepted that risk
- the user gave a vague instruction like "fix it" or "do this everywhere"
- you cannot state the exact intended change in one sentence

## Step 5: Parse and Present Results

Parse JSON output when available, using Ansible's JSON callback when useful, and
summarize only what answers the request.

Result rules:

- For a scalar answer, state it directly.
- For small structured results, summarize important fields.
- For tabular results, use a markdown table when it improves clarity.
- For exported files, confirm the path and summarize what was written without
  dumping customer data unless the user explicitly asks.
- For failures, report the useful Ansible error details without exposing
  secrets, suggest the smallest corrective action, and do not auto-retry
  mutating tasks.

## Development Changes

When modifying or adding Ansible modules in this repository:

1. Read the matched module source and its tests.
2. Keep all module functions typed.
3. Use `base_argument_spec()` for shared `region` and `api_token` auth.
4. Set `supports_check_mode=True` on every module.
5. Implement a meaningful `module.check_mode` path for mutating modules.
6. Keep secrets marked `no_log=True`.
7. Run `build-ansible-collection` after changes that affect docs or installed
   module behavior.
8. Verify with `ansible-doc -j cisco.sccfm.<module_name>`.
9. Run targeted module tests, then broader tests based on risk:

   ```bash
   pytest sccfm-ansible/plugins/modules/tests/ -v
   ```

10. Run live e2e tests only when credentials and a suitable sandbox are
    available.

## Important Rules

1. Never hardcode modules. All module knowledge comes from `ansible-doc`.
2. Never fabricate options. Only use parameters listed in the matched docs.
3. Always use FQCNs.
4. Always protect secrets with Vault, environment lookups, or placeholders.
5. Never guess between ambiguous modules, targets, or regions.
6. Never rely on default local output paths for customer data.
7. Never execute mutating automation without the confirmation workflow.
8. Use check mode for mutating automation whenever the module supports it.
9. If a command fails, report it clearly and stop. Do not auto-retry unless the
   user explicitly asks.
10. In Generate-Only mode, never execute the final business playbook.
