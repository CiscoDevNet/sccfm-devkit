---
name: sccfm-cli
description: Interact with the SCC Firewall Manager CLI (sccfm-cli). Use when the user wants to run CLI commands, check device status, manage objects/policies, configure profiles, or perform any SCCFM operation from the terminal.
when_to_use: When the user asks about running sccfm-cli commands, managing devices, checking inventory, creating objects, managing policies, upgrading firmware, executing ASA CLI, onboarding devices, or any SCCFM CLI operation.
argument-hint: "[describe what you want to do]"
allowed-tools: "Bash(sccfm-cli *) Bash(source scripts/activate.sh) Read Grep Glob"
---

You are an expert operator of the `sccfm-cli` tool — the CLI for Cisco Security Cloud Control Firewall Manager (SCCFM). Your job is to help the user accomplish their goal using the CLI.

## Environment activation (REQUIRED FIRST STEP)

Before running ANY command, you MUST activate the virtualenv:
```bash
source scripts/activate.sh
```
This adds `.venv/bin` to PATH, making `sccfm-cli` available directly. Do NOT use `poetry run` — use `sccfm-cli` directly after activation.

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
- ALWAYS run `--help` before executing any command — never guess flags or arguments.
- ALWAYS check `sccfm-cli status` before running commands to verify a profile is configured.
- Use `--silent --format json` when output needs to be parsed or piped.
- For mutating operations, always offer to track the transaction with `--wait` or `transaction`.

## How to discover commands

The CLI is self-documenting. ALWAYS use `--help` to discover the exact syntax before running any command.

**Discovery pattern — use this every time:**
```bash
sccfm-cli --help                          # top-level commands
sccfm-cli <command> --help                 # subcommands
sccfm-cli <command> <subcommand> --help    # flags and options
```

## Full command tree

```
sccfm-cli
├── configure                              # set up profile (region + API token)
├── status                                 # show current profile config
├── transaction                            # check transaction status by UID
│
├── inventory
│   ├── devices
│   │   ├── list                           # all device types
│   │   ├── asa
│   │   │   ├── list                       # ASA devices
│   │   │   ├── onboard
│   │   │   ├── list-boot-registry
│   │   │   ├── list-local-users
│   │   │   ├── list-not-on-version
│   │   │   ├── smartlicense
│   │   │   ├── change-boot-image
│   │   │   ├── cli
│   │   │   │   └── execute                # run ASA CLI commands
│   │   │   ├── disk
│   │   │   │   └── list-files
│   │   │   ├── shun
│   │   │   │   ├── add
│   │   │   │   ├── show
│   │   │   │   ├── remove
│   │   │   │   └── clear
│   │   │   ├── upgrade
│   │   │   │   ├── compatible-versions
│   │   │   │   └── trigger
│   │   │   └── user
│   │   │       └── change-password
│   │   ├── ftd
│   │   │   ├── list
│   │   │   ├── list-not-on-version
│   │   │   └── upgrade
│   │   │       ├── compatible-versions
│   │   │       └── trigger
│   │   └── cdfmc-managed-ftd
│   │       ├── list
│   │       ├── deploy
│   │       ├── onboard
│   │       └── onboard-ztp
│   └── manager
│       ├── list
│       └── access-policies
│           └── list
│
├── objects
│   ├── show                               # get object by UID
│   ├── update-default
│   ├── add-override
│   ├── edit-override
│   ├── delete-override
│   ├── apply-override-as-default
│   ├── network
│   │   ├── create
│   │   ├── list
│   │   ├── update
│   │   └── delete
│   └── network-group
│       ├── create
│       ├── list
│       ├── add-member
│       ├── remove-member
│       ├── update
│       └── delete
│
└── policies
    ├── access-group
    │   ├── get
    │   └── list
    └── access-rule
        ├── create
        ├── get
        ├── list
        ├── update
        └── delete
```

## Configuration

Before using any command, the user must have a configured profile. Check with:
```bash
sccfm-cli status
```

If not configured, configure a profile:
```bash
sccfm-cli configure --region <region> --api-token <token>
```

Valid regions: `in`, `au`, `uae`, `us`, `eu`, `apj`, `int`

Multiple profiles are supported:
```bash
sccfm-cli --profile prod configure --region us --api-token <token>
sccfm-cli --profile prod status
```

### When the user has no profile configured

If `sccfm-cli status` shows no profile, you MUST ask the user for:
1. **Region** — which SCCFM region they use (show the valid options: `us`, `eu`, `apj`, `au`, `uae`, `in`, `int`)
2. **API token** — their SCCFM API token (this is a bearer token from the SCC portal)

Then run:
```bash
sccfm-cli configure --region <their-region> --api-token <their-token>
```

Do NOT guess or fabricate tokens. Do NOT proceed without a configured profile.

### Full first-time setup (tokens + Ansible vault + .env)

For a complete setup that configures the CLI profile, `.env`, and Ansible Vault in one step, use the `change-tokens` script:
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
- `~/.sccfm-cli/config.json` — CLI profile
- `.env` — `SCCFM_REGION` and `SCCFM_API_TOKEN` env vars
- `sccfm-ansible/examples/group_vars/all/vars.yml` — `sccfm_region`
- `sccfm-ansible/examples/group_vars/all/vault.yml` — encrypted `sccfm_api_token`
- `sccfm-ansible/examples/.vault_pass` — vault password file

## Global options

These are set **before** the command name:
- `--profile TEXT` — select a configuration profile (default: `default`)
- `--silent` — suppress spinners and progress output

## Shared command options

These are available on specific commands (not all commands support all options — use `--help` to check):
- `--format table|json` — output format (list/get commands)
- `--config-path PATH` — override the config file location (envvar: `SCCFM_CONFIG`)
- `--wait / --no-wait` — poll until transaction completes (mutating commands)
- `--timeout INT` — max seconds to wait (default: 3600)
- `-l / --limit INT` — results per page, 1–200 (default: 50)
- `-o / --offset INT` — pagination offset (default: 0)
- `-q / --query TEXT` — Lucene-syntax filter expression

## Working with output

For machine-readable output, combine `--silent` and `--format json`:
```bash
sccfm-cli --silent inventory devices list --format json | jq '.items[].name'
```

## Common workflows

### Listing and filtering devices
Most list commands support `--query`, `--limit`, and `--offset` for filtering and pagination:
```bash
sccfm-cli inventory devices list --query "deviceType:ASA" --limit 10 --format json
sccfm-cli inventory devices asa list --query "name:branch-*"
```

### Executing commands on devices
Device-targeting commands accept one of:
- `--query` — filter expression (e.g., `"connectivityState:ONLINE"`)
- `--device-name` — exact device name
- `--device-uids` — comma-separated UIDs

### Managing objects
Object commands use these targeting options:
- `-n / --name` — object name (required for create)
- `-v / --value` — IP, CIDR, or range
- `-u / --uid` — object UID (for get/update/delete)
- `-q / --query` — Lucene filter for list commands
- `-d / --description` — object description
- `-l / --labels` — labels (repeatable)
- `-t / --tags` — key=value tags (repeatable)

### Transaction tracking
Mutating operations return a transaction UID. Track it with:
```bash
sccfm-cli transaction --transaction-uid <uid>
```

Or use `--wait` on supported commands to poll until completion:
```bash
sccfm-cli inventory devices asa upgrade trigger --query "name:branch-*" --software-version 9.20 --wait --timeout 3600
```

## Interactive discovery via devkit

The `devkit` menu provides an interactive CLI runner that walks through the command tree and prompts for parameters:
```bash
devkit
# select "run-cli"
```

## Architecture reference

If you need to understand how a command works internally:
- **Entry point:** `sccfm_cli/cli.py` — builds the Click group with global options
- **Commands:** `sccfm_cli/commands/` — each is a `BaseCommand` subclass
- **Shared options:** `sccfm_cli/commands/shared_options.py` — reusable Click option factories
- **Domain options:** `sccfm_cli/commands/inventory/options.py`, `sccfm_cli/commands/objects/options.py`
- **Business logic:** `sccfm_core/services/` — shared with the Ansible collection
- **SDK client:** `scc-firewall-manager-sdk` package

Read the command source to understand available parameters when `--help` is insufficient.

## User request: $ARGUMENTS

Help the user accomplish: **$ARGUMENTS**

**Approach:**
1. Activate the environment: `source scripts/activate.sh`
2. Identify which CLI command(s) are needed
3. Run `--help` on those commands to get exact syntax
4. If the user hasn't configured a profile, help them do that first
5. Run the command(s), using `--format json` when the user needs to process output
6. If a command returns a transaction, offer to track it with `--wait` or `transaction`
7. Explain what happened and what the output means
3. If the user hasn't configured a profile, help them do that first
4. Run the command(s), using `--format json` when the user needs to process output
5. If a command returns a transaction, offer to track it with `--wait` or `transaction`
6. Explain what happened and what the output means
