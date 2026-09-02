---
name: sccfm-setup
description: Set up or repair the managed Cisco SCC Firewall Manager runtime with a pipx-installed sccfm-cli, the matching cisco.sccfm Ansible collection, named-profile authentication, and verification. Use for first-time managed setup, upgrades, authentication guidance, or setup diagnostics. Use sccfm-cli for an explicitly requested CLI-only Homebrew installation, sccfm-uninstall for teardown, and sccfm-cli or sccfm-ansible for ordinary operations.
allowed-tools: "Bash(command -v *) Bash(python3 *) Bash(pipx *) Bash(sccfm-cli *) Bash(ansible-doc *) Bash(ansible-galaxy *) WebSearch WebFetch Read"
---

# SCC Firewall Manager Setup

Install the requested runtime with the fewest necessary discovery steps. Keep
secrets out of chat and do not install or replace software until the user
approves the exact plan.

## Setup modes

- **Check:** inspect the current runtime without changing it.
- **Install or upgrade:** install one stable, matching CLI and collection version
  in the helper-managed pipx runtime.
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

1. Run `command -v python3.12` and `command -v pipx` in parallel when possible.
   Stop only for a missing prerequisite.
2. If the user supplied a stable version, use it. Otherwise query the PyPI and
   Ansible Galaxy release metadata in parallel, then select the highest stable
   version present in both. Do not browse release notes or general
   documentation. Never mix versions.
3. Generate the exact plan once:

   ```bash
   python3 scripts/setup_runtime.py plan --version X.Y.Z --python python3.12
   ```

4. Summarize only the packages, version, destination, and exact confirmation.
   Require `INSTALL SCCFM X.Y.Z`, then run exactly one helper command:

   ```bash
   python3 scripts/setup_runtime.py install --version X.Y.Z --python python3.12 --yes
   ```

5. Verify the CLI schema export and Ansible collection discovery once. Do not
   run connectivity checks before the user configures a profile, and do not
   rerun the full doctor after a successful clean install.

If the plan reports an existing Homebrew installation, stop. Do not create a
duplicate CLI installation. Route an explicitly requested CLI-only Homebrew
installation to `sccfm-cli`.

### Check and repair path

Resolve this skill's plugin root, then run:

```bash
python3 scripts/setup_runtime.py doctor --json
```

Summarize missing commands, detected versions, schema availability, collection
discovery, whether a profile file exists, and whether the CLI is managed by the
canonical `ciscodevnet/tap/sccfm-cli` Homebrew formula. Never read or display
the profile file contents.

Python 3.12 or later and `pipx` are prerequisites for this managed installation.
If either is missing, explain the smallest platform-appropriate installation
step and wait for approval before changing the machine.

This skill never installs through Homebrew. If the user explicitly wants a
CLI-only Homebrew installation, route that request to `sccfm-cli`. If the doctor
finds an existing Homebrew formula, explain that it is an external CLI-only
installation and stop before planning a duplicate managed runtime. Let the user
either keep it and use `sccfm-cli`, or remove it through `sccfm-uninstall` before
continuing here.

## 2. Detailed installation and repair rules

Use a stable release that exists for both `cisco-sccfm-devkit` on PyPI and
`cisco.sccfm` on Ansible Galaxy. Do not guess a version or mix versions.

Select an available Python 3.12 executable from the doctor report. Generate the
exact plan without executing it:

```bash
python3 scripts/setup_runtime.py plan --version X.Y.Z --python python3.12
```

If the helper reports an existing Homebrew installation, stop. Do not bypass
that refusal or create a duplicate CLI installation.

Explain that pipx is the canonical installation method for this complete
CLI-plus-Ansible runtime. The plan installs the Python package with `pipx`,
injects Ansible into that same environment so modules can import
`cisco_sccfm_core`, and installs the collection at the identical version. The
helper installs the collection at the standard per-user path
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
inventory, and lookup discovery through `ansible-doc`.

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

This skill manages the pipx-based complete setup and repair only. Route an
explicit CLI-only Homebrew installation to `sccfm-cli` and teardown to
`sccfm-uninstall`.
After setup, route CLI work to
`sccfm-cli` and Ansible work to `sccfm-ansible`. Those skills may execute
verified read-only operations. Mutating operations require a reviewed plan, the
exact command, and the explicit confirmation phrase defined by the operational
skill.
