---
name: sccfm-cli
description: Use the customer-facing SCC Firewall Manager CLI by discovering the live schema, validating command metadata, and either executing or generating safe sccfm-cli commands without hardcoded command knowledge.
when_to_use: When the user asks to use, install, configure, inspect, or generate commands for sccfm-cli or SCC Firewall Manager CLI workflows.
argument-hint: "[describe the SCCFM CLI task]"
allowed-tools: "Bash(command -v *) Bash(sccfm-cli *) Bash(source cisco_sccfm_scripts/activate.sh) Bash(brew *) Bash(pipx *) Bash(jq *) Read Grep Glob"
---

# SCC Firewall Manager CLI

Execute or generate `sccfm-cli` commands by dynamically discovering available
operations from the CLI schema. All command knowledge comes from the schema. Do
not hardcode command names, options, examples, or behavior.

This skill operates against customer SCC Firewall Manager environments. Optimize
for customer safety first and convenience second.

## Core Rules

1. Treat every operation as customer-impacting until the schema proves otherwise.
2. Prefer stopping over guessing. If command match, target identity, region,
   profile, or safety class is ambiguous, ask the user or switch to
   generate-only mode.
3. Never improvise command names, flags, defaults, target lists, or file paths.
4. Never ask the user to paste secrets into chat.
5. Always use the schema's `readonly` flag.
6. Use canonical schema values in generated commands.

## Execution Modes

Select one execution mode for each user request.

### Mode 1: Execute

Use this mode by default when the user asks you to perform the operation.

- You may run the matched business command, subject to the safety rules in this
  skill.
- You may run schema discovery, readonly validation, or preflight commands when
  needed.
- If intent is ambiguous, default to Generate-Only.

### Mode 2: Generate-Only

Use this mode when the user says anything like "show me the command",
"generate the command", "do not run it", "don't run it", "I will run it myself",
or "command only".

In Generate-Only mode:

- Never execute the final business command.
- You may still run schema export because command discovery depends on it.
- You may run readonly validation or preflight commands unless the user
  explicitly said not to run anything at all.
- If the user forbids all command execution and no cached schema is available,
  stop and explain that safe generation requires schema discovery.
- If readonly validation or preflight is not allowed, mark the command as
  `not validated against live state`.
- Always return the exact command in a fenced `bash` block.
- Never ask for mutating confirmation phrases because the agent is not executing
  the command.

## Safety Model

Classify every matched command before execution.

### Class A: Readonly, no local writes

- `readonly: true`
- The invocation does not write to a local file, profile, export destination, or
  config path.

These commands are safe to execute after validation.

### Class B: Readonly, local-write/export side effects

- `readonly: true`
- `side_effects` or option metadata indicates a local write, export,
  destination, output path, config path, or profile write.

These commands do not mutate SCC Firewall Manager, but they still have side
effects and may spill customer data. Require explicit user opt-in and an explicit
destination path. Never rely on a schema default output location for exported
customer data.

### Class C: Mutating

- `readonly: false`

These commands may modify SCC Firewall Manager or a managed device. They require
preflight where available, a plan, unambiguous targets, and explicit
confirmation. Never execute them on a vague instruction.

## Prerequisites

### Platform

The CLI is Python 3.12 based and supports normal Python installs on macOS,
Linux, and Windows. Prefer macOS or Linux shells for direct agent operation; on
Windows, use the documented Python install path or WSL when shell features are
needed.

### Step A: Resolve the CLI Binary

Follow these checks in order:

1. Run `command -v sccfm-cli`.
   - If found, the invocation prefix is `sccfm-cli`.
2. If you are inside this repository, the binary is not on `PATH`, and
   `cisco_sccfm_scripts/activate.sh` exists, run `source cisco_sccfm_scripts/activate.sh` once for the
   shell session, then resolve again. Do not use `poetry run`.
3. Only install or perform setup when the user explicitly asks for it.
4. Otherwise, stop and tell the user the CLI is not installed or not on `PATH`.

Store the invocation prefix for the rest of the session. Do not switch
invocation modes mid-session unless the user explicitly asks.

#### Installing via Homebrew

Only do this if the user explicitly asked for installation or setup.

1. Verify `brew` is in `PATH`. If not, stop and tell the user to install
   Homebrew.
2. Use `brew search` or the project release docs to discover the exact
   tap/formula.
3. Install only the exact documented formula. Do not invent a Homebrew package
   name.
4. If no Homebrew formula is published for the release, say so and use the
   documented wheel or `pipx` install path instead.

### Step B: Verify Credentials

This skill uses customer SCC Firewall Manager API-token/profile auth, not
internal SystemDB tokens.

Use the selected command's `auth` object:

- If `auth.requires_profile` is false, skip profile verification.
- If `auth.requires_profile` is true, verify a configured customer profile is
  available before executing.
- Profiles contain a region and API token. Tokens come from developer.cisco.com
  or the SCC Firewall Manager UI.

#### Secret Handling Rules

1. Never ask the user to paste a token into chat.
2. Never echo a token back to the user.
3. Never log tokens or include them in final answers.
4. Never use internal SystemDB credentials.
5. If a profile is missing, guide the user to run the documented configuration
   flow locally, or generate a validated configuration command with a placeholder
   token.
6. Only configure a profile yourself when the user explicitly provides a secure,
   local mechanism for the token.

#### Credential Verification Algorithm

Before executing any command where `auth.requires_profile` is true:

1. Determine the profile from the user's request, global options, or schema
   defaults.
2. Run a readonly profile/connectivity check only if the schema exposes one and
   the selected execution mode allows validation.
3. If validation succeeds, proceed with command construction.
4. If no validation command is available, proceed only if a profile is already
   configured or the user explicitly provides the profile name to use.
5. If the profile is missing or invalid, stop and tell the user to configure a
   customer SCC Firewall Manager API token locally.
6. Do not ask for token contents, do not print token values, and do not retry
   with alternate credentials unless the user explicitly selects them.

AWS credentials and internal SystemDB tokens are out of scope for `sccfm-cli`.

#### Canonical Region Mapping

Normalize user-friendly region names before using them. The canonical values are
the choices exposed by the schema for the region option.

Common aliases:

- United States or USA -> `us`
- Europe -> `eu`
- Asia Pacific/Japan -> `apj`
- Australia or `aus` -> `au`
- United Arab Emirates -> `uae`
- India -> `in`
- CI -> `ci`
- integration or internal -> `int`

Only use the normalized value if it is present in the schema choices. If the user
supplies any other region string, say it is not recognized and show the valid
schema choices.

## Step 1: Discover Available Commands

Export the schema once per session:

```bash
sccfm-cli schema export --format json
```

This is the only hardcoded command exception. It bootstraps schema discovery; all
other command names, flags, options, examples, and behavior must come from the
exported schema.

Parse the JSON output. The schema contains:

- `commands`: available leaf operations
- `command`: full executable command text
- `path`: command path segments
- `description`: human-readable behavior
- `readonly`: whether the command mutates SCC Firewall Manager
- `side_effects`: local or remote side effects
- `auth`: auth requirements
- `option_groups`: inter-option constraints
- `constraints`: validation and preflight constraints
- `global_options`: flags that must appear before the command path
- `options`: accepted flags, types, defaults, choices, and descriptions
- `examples`: declared usage examples, if any

Cache the schema in memory for the session. Do not re-export unless:

- the user explicitly asks you to refresh it
- the CLI binary or invocation prefix changed
- the environment changed
- a command is missing

If schema export fails, stop and report the error. Do not guess what the CLI
supports.

## Step 2: Match User Intent Conservatively

Derive the user's request into this structured shape before matching commands:

- requested action
- target object type
- target identity or target list
- region or profile
- whether they asked to read, export, or modify

Then match commands using this algorithm:

1. Filter schema commands whose `command`, `path`, or `description` directly
   match the requested action and object type.
2. Prefer exact token matches in `path` over looser description matches.
3. If the user names a concrete subtype and the schema has a subtype-specific
   path segment for it, prefer that command over a generic command plus a
   `deviceType` query.
4. Reject any command whose safety category conflicts with the user's intent.
5. If exactly one command remains, use it.
6. If multiple plausible commands remain, show the candidates and ask the user
   to choose.
7. If no command matches, say so clearly and stop.

Never guess between multiple commands. Fail closed on ambiguity.

## Step 3: Build the Invocation

Construct the command strictly from the matched schema entry.

### Required Inputs

1. Check every option where `required` is true.
2. Gather values from the user's request.
3. If a required value is missing, ask for it. Do not invent it.

### Option Placement

Build commands in this order:

```text
sccfm-cli <global options> <schema command path> <command options>
```

Global options come from the root schema's `global_options` list and must be
placed before the command path. Command options come from the matched command's
`options` list and must be placed after the command path.

Never place a `global_options` flag after the leaf command. Click will reject it.

### Option Groups

Apply every `option_groups` entry and every `constraints` entry exactly as
described in the schema. See "Parsing `option_groups`" below.

### Output Format

In Execute mode, pass JSON output only when the selected command schema declares
an output format option whose values include `json`.

In Generate-Only mode, omit JSON output unless the user explicitly requested it
or the schema requires it.

### Natural-Language Query Filters

If the user describes a filter in natural language, such as "online ASAs" or
"objects named web-*", build a `--query` value only from the matched command's
`queryable_fields` and `field_notes` metadata.

1. Match the user's words to field names, allowed values, aliases, or examples
   declared in `queryable_fields`.
2. Use the exact field spelling and value casing from the schema metadata.
3. If `field_notes` says a command automatically adds a filter, do not duplicate
   that filter in the generated query.
4. If no schema-declared field matches the requested filter, ask the user for the
   exact Lucene query instead of guessing.
5. Never pass bare words like `online` as a query unless the schema explicitly
   documents that form.

### Region

Always pass canonical region values from schema choices, not friendly aliases.

### Optional Flags

Only pass an optional flag if one of these is true:

- the user explicitly requested it
- it is required to satisfy a schema constraint
- it is required for safe machine-readable execution in Execute mode

Do not add optional flags because they seem convenient.

### Sensitive and Risky Flags

1. Never include API tokens in chat output.
2. Do not pass diagnostic or verbose flags unless the user explicitly asked for
   diagnostic output on a failed readonly command.
3. Do not pass local output/export/config path options unless the user explicitly
   asked for local writes and provided the destination path.
4. Never rely on schema default output paths for customer data exports.

### Target Identity Rules

For Class C commands, require an explicit, unambiguous target selector before
execution.

- If the user gives a broad search, friendly name, or query and the schema
  exposes a readonly lookup that can resolve the target set, run that lookup
  first when allowed.
- Present the resolved target or exact target count before asking for
  confirmation.
- Do not mutate based on vague wording like "all of them" unless the target set
  has been enumerated and confirmed.

### Bulk Input Rules

If a command uses a file or list input for bulk work:

1. Inspect the file before execution.
2. Count non-empty targets.
3. Surface duplicates or obviously malformed lines to the user.
4. Tell the user the exact target count.
5. Never create a bulk file for a mutating operation unless the user explicitly
   asked you to.

## Step 4: Execution Policy

Apply these rules after selecting execution mode.

### Class A: Readonly, No Local Writes

In Execute mode, run the command after validation if:

- the command match is unambiguous
- region/profile is resolved
- auth requirements are satisfied
- all schema constraints are satisfied

In Generate-Only mode, validate the invocation as far as the selected mode
allows, then return the exact command.

### Class B: Readonly, Local Writes or Exports

In Execute mode, before executing:

1. Confirm the user wants a local export or local write.
2. Require an explicit destination path.
3. State what will be written and where.
4. Do not use schema defaults for file locations.

In Generate-Only mode, require an explicit destination path before generating the
command, then state what will be written locally if the user runs it.

### Class C: Mutating Commands

In Execute mode, never execute a mutating command immediately. Use this workflow:

1. Validate the command match and canonical region/profile.
2. Validate credentials using the command's `auth` metadata.
3. Resolve targets to an unambiguous selector or exact target count.
4. For bulk work, inspect the target list and present the exact count.
5. If the schema exposes a preflight-only mode through a `check` option or a
   `mode` constraint, run the preflight first and present the result.
6. If no suitable preflight exists, say so explicitly and stop unless the user
   explicitly approves proceeding without preflight.
7. Present an execution plan containing:
   - command path
   - target selector or target count
   - auth profile
   - intended change
   - preflight result, if available
   - exact command that will be executed
8. Require explicit confirmation before execution.

In Generate-Only mode, validate as far as allowed, mark whether live preflight
was performed, return the exact command, and do not execute it.

#### Confirmation Rules for Mutating Commands

These confirmation rules apply only in Execute mode.

For any Class C command, require the user to send the exact confirmation phrase
you provide. Use this format:

```text
EXECUTE sccfm-cli <schema command path> <target-summary>
```

For bulk or broad-target mutations, require two confirmations:

1. A first confirmation that they want to proceed with the plan.
2. A second message containing the exact `EXECUTE ...` phrase.

#### Red Lines for Mutating Commands

Never execute a Class C command when any of these is true:

- the command match is ambiguous
- the region or profile is ambiguous
- the target is vague or unresolved
- a bulk file has not been inspected
- credentials are missing or would expose secrets in chat
- the user gave a vague instruction like "fix it" or "do this everywhere"
- you cannot state the exact intended change in one sentence

## Step 5: Parse and Present Results

Parse JSON output when available and summarize only the data needed to answer the
request.

### Result Presentation

- For a single boolean or scalar answer, state it directly.
- For small structured results, summarize the important fields.
- For tabular results, use a markdown table when that improves clarity.
- For exported data, confirm the output path and summarize what was written
  without dumping sensitive data into chat unless the user explicitly asks.

### Errors

If the command exits non-zero:

1. Report the failure clearly.
2. Include useful stderr details when they do not expose secrets.
3. Suggest the smallest corrective action.
4. Do not retry automatically, especially for mutating commands.

## Parsing `option_groups`

Each item in `option_groups` defines an explicit constraint. Enforce the schema
literally.

### Mutually Exclusive Groups (`"mutually_exclusive": true`)

The listed options cannot be used together.

- If `required` is true, exactly one must be present.
- Otherwise, at most one may be present.

### Dependency Groups (`"dependent": true`)

The listed options require another option named in `requires`.

### Other Constraints

Also enforce every entry in `constraints`, including required-any,
required-unless, exactly-one-unless, value-prefix, dependent, conditional, and
preflight mode constraints.

### Validation Rules

Before executing any command:

1. Check every mutually exclusive group.
2. Check every dependency group.
3. Check every command constraint.
4. If validation fails, explain the exact conflict and stop.
5. Do not silently add missing options unless the user supplied the needed value.
6. Do not silently remove conflicting flags.

## Important Rules

1. Never hardcode commands. All command knowledge comes from schema export.
2. Never fabricate options. Only use options listed in the matched schema entry.
3. Always pass canonical region values.
4. Never ask the user to paste secrets into chat.
5. Never guess between ambiguous commands or targets.
6. Never rely on schema default export paths for customer data.
7. Never execute a mutating command without the required confirmation workflow.
8. If a command fails, report it clearly and stop. Do not auto-retry unless the
   user explicitly asks.
9. In Generate-Only mode, never execute the final business command.
