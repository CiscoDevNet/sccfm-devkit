---
name: sccfm-setup
description: Set up or repair Cisco SCC Firewall Manager with either a complete pipx runtime or a managed Ansible companion for an existing Homebrew CLI, plus matching versions, named-profile authentication, and verification. Use for first-time setup, upgrades, authentication guidance, or setup diagnostics. Use sccfm-cli for an explicitly requested CLI-only Homebrew installation, sccfm-uninstall for teardown, and sccfm-cli or sccfm-ansible for ordinary operations.
allowed-tools: "Bash(command -v *) Bash(python3 *) Bash(pipx *) Bash(sccfm-cli *) Bash(ansible-doc *) Bash(ansible-galaxy *) Bash(~/.sccfm-agent-plugin/ansible-runtime/bin/ansible-doc *) WebSearch WebFetch Read"
---

# SCC Firewall Manager Setup

Install the requested runtime with the fewest necessary discovery steps. Keep
secrets out of chat and do not install or replace software until the user
approves the exact plan.

## Setup modes

- **Check:** inspect the current runtime without changing it.
- **Install or upgrade:** install one stable, matching CLI and collection version
  while preserving an existing canonical Homebrew CLI when present.
- **Authenticate:** configure a named SCCFM profile through the CLI's hidden prompt.
- **Repair:** rerun checks and change only the failed component.

## 1. Choose the shortest path

For an explicit first-time install or upgrade request, use the fast path below.
Do not run the full doctor before installation unless a prerequisite, ownership
check, or install command fails. Use the full doctor for check, diagnosis, and
repair requests.

Before requesting install confirmation, resolve the intended profile and
region. Use profile `default` when the user did not request another profile.
Never guess the region. If it is missing, ask only for the SCCFM region and
continue once it is known.

### Fast install path

1. Run `command -v python3.12`, `command -v pipx`, and `command -v sccfm-cli` in
   parallel when possible. Python 3.12 or later is required for both paths;
   `pipx` is required only when no canonical Homebrew CLI is installed.
2. If `sccfm-cli` already exists, export its schema and use its stable version
   as the candidate. Otherwise use a stable version supplied by the user, or
   query the PyPI and Ansible Galaxy release metadata in parallel and select the
   highest stable version present in both. Verify that the candidate exists for
   both `cisco-sccfm-devkit` and `cisco.sccfm`. Never mix versions.
3. Generate the exact plan once:

   ```bash
   python3 scripts/setup_runtime.py plan --version X.Y.Z --python python3.12
   ```

4. The helper automatically chooses the complete pipx path or, for the
   canonical Homebrew formula, a private Ansible companion path. Summarize only
   the retained or installed packages, version, destination, and exact
   confirmation.
   Require `INSTALL SCCFM X.Y.Z`, then run exactly one helper command:

   ```bash
   python3 scripts/setup_runtime.py install --version X.Y.Z --python python3.12 --yes
   ```

5. Verify the CLI schema export and Ansible collection discovery once. For a
   Homebrew CLI, use the absolute managed `ansible-doc` path reported by the
   helper; do not activate its virtual environment or expose its `sccfm-cli`.
   Do not run connectivity checks before the user configures a profile, and do
   not rerun the full doctor after a successful clean install.

### Check and repair path

Resolve this skill's plugin root, then run:

```bash
python3 scripts/setup_runtime.py doctor --json
```

Summarize missing commands, detected versions, schema availability, collection
discovery, whether a profile file exists, and whether the CLI is managed by the
canonical `ciscodevnet/tap/sccfm-cli` Homebrew formula. Never read or display
the profile file contents.

Python 3.12 or later is required. `pipx` is also required for a complete install
when no Homebrew CLI is present. If a required prerequisite is missing, explain
the smallest platform-appropriate installation step and wait for approval
before changing the machine.

This skill never installs through Homebrew. If the user explicitly wants a
CLI-only Homebrew installation, route that request to `sccfm-cli`. When the
doctor finds the canonical formula, keep it and repair or install only its
helper-owned Ansible companion. Do not install a second CLI with pipx.

## 2. Detailed installation and repair rules

Use a stable release that exists for both `cisco-sccfm-devkit` on PyPI and
`cisco.sccfm` on Ansible Galaxy. Do not guess a version or mix versions.

Select an available Python 3.12 executable from the doctor report. Generate the
exact plan without executing it:

```bash
python3 scripts/setup_runtime.py plan --version X.Y.Z --python python3.12
```

The helper supports two version-aligned layouts:

- **No Homebrew CLI:** pipx is the canonical installation method. The helper
  installs `cisco-sccfm-devkit`, injects Ansible into the same environment, and
  installs the identical Galaxy collection version.
- **Canonical Homebrew CLI present:** keep that CLI and its profile behavior.
  The helper creates `~/.sccfm-agent-plugin/ansible-runtime`, installs
  `ansible-core` and the exact matching `cisco-sccfm-devkit` library there, and
  installs the same `cisco.sccfm` collection version. The companion virtual
  environment is never activated or added to `PATH`, so it provides Ansible and
  `cisco_sccfm_core` without exposing a second `sccfm-cli`.

Both layouts install the collection at
`~/.ansible/collections/ansible_collections/cisco/sccfm` and record every
helper-owned path in `~/.sccfm-agent-plugin/runtime.json`. If the collection or
Homebrew companion directory already exists without that ownership record,
stop and ask the user to resolve it; never overwrite or adopt it automatically.
If the requested version differs from the installed Homebrew CLI version, stop
instead of producing a mixed runtime.

Require the exact confirmation `INSTALL SCCFM X.Y.Z`. Only then run:

```bash
python3 scripts/setup_runtime.py install --version X.Y.Z --python python3.12 --yes
```

Do not use `--yes` before receiving that confirmation. Do not install from an
unreviewed branch, draft release, or mismatched artifact set.

## 3. Configure authentication

SCCFM API tokens belong in the canonical named-profile store, never in chat,
shell history, playbooks, `.env` files, or Ansible Vault.

After installation, finish by telling the user exactly which configure command
to run locally so the token is entered through its hidden prompt. Always include
the resolved profile and canonical region; never return placeholders such as
`<profile>` or `<canonical-region>`.

```bash
sccfm-cli --profile default configure --region us
```

The command above illustrates the exact shape only. Substitute the profile and
region resolved for the current request before showing it. Quote a profile when
its name requires shell quoting. Place the schema-declared global profile option
before the command path. Derive accepted regions and option names from
`sccfm-cli schema export --format json`; do not invent them.

Make the configure command the final actionable instruction in the setup
response and explain in one sentence that it prompts securely for the token.
Do not execute it through a non-interactive agent shell. Tokens are created in
the SCC Firewall Manager UI or the linked Cisco developer authentication flow.
Never ask the user to paste a token into the conversation.

The same profile is consumed by `sccfm-cli` and the `cisco.sccfm` collection.
Ansible Vault remains only for playbook-specific device secrets.

## 4. Verify

For check and repair requests, rerun the doctor after changes. Then use the
`sccfm-cli` skill to discover and run the schema-declared read-only
connectivity/status operation. Use the `sccfm-ansible` skill to verify module,
inventory, and lookup discovery through the selected `ansible-doc`. When the
doctor reports a managed Homebrew companion, use its absolute Ansible command
paths for all subsequent Ansible work.

For a clean install without a profile, runtime installation is complete when
the CLI schema and Ansible discovery checks succeed; finish by showing the exact
configure command. Authenticated setup is complete after the user runs that
command and the following checks succeed:

- CLI schema export succeeds;
- CLI, Python package, and Ansible collection versions match;
- the selected profile passes a read-only connectivity check;
- `ansible-doc` discovers the installed collection; and
- one harmless read-only operation succeeds, if the user permits live validation.

If a check fails, stop at that component. Do not reinstall everything or retry
authentication with another profile unless the user chooses that action.

## 5. Removal and teardown

Route uninstall, teardown, and complete-cleanup requests to the
`sccfm-uninstall` skill. It handles both helper-managed and positively
discovered legacy installations with a separate destructive confirmation.

## Safety boundary

This skill manages either the complete pipx setup or the Ansible companion for
an existing canonical Homebrew CLI. Route the Homebrew installation itself to
`sccfm-cli` and teardown to `sccfm-uninstall`.
After setup, route CLI work to
`sccfm-cli` and Ansible work to `sccfm-ansible`. Those skills may execute
verified read-only operations. Mutating operations require a reviewed plan, the
exact command, and the explicit confirmation phrase defined by the operational
skill.
