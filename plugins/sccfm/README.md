# SCC Firewall Manager agent plugin

This plugin packages guided setup and safety-aware operation for `sccfm-cli` and
the `cisco.sccfm` Ansible collection. It supports Claude Code and Codex from the
same source tree.

See the [complete capability and end-user guide](../../docs/agent-plugin.md) for
the four-skill design, safety model, workflows, and examples.

## Install in Claude Code

```text
/plugin marketplace add CiscoDevNet/sccfm-devkit
/plugin install sccfm@sccfm-devkit
```

Then ask: `Set up SCC Firewall Manager for this machine.`

## Install in Codex

```bash
codex plugin marketplace add CiscoDevNet/sccfm-devkit
codex plugin add sccfm@sccfm-devkit
```

Alternatively, open `/plugins` and select **SCC Firewall Manager**. Then ask
Codex to set up SCC Firewall Manager.

## What setup does

The guided setup uses a fast path for explicit installation requests: it checks
only required prerequisites, resolves one version shared by PyPI and Ansible
Galaxy, installs the reviewed CLI and Ansible runtime after confirmation, and
verifies local discovery once. Full diagnostics are reserved for check and
repair requests. It finishes with the exact profile configuration command so
the API token is entered through the CLI's masked local prompt. Tokens are never
requested in chat.

Without an existing Homebrew CLI, setup keeps `sccfm-cli`, `ansible-core`, and
`cisco_sccfm_core` in one pipx environment. With the canonical Homebrew CLI, it
preserves that installation and creates a private matching Ansible companion at
`~/.sccfm-agent-plugin/ansible-runtime`. The companion is not added to `PATH`,
so it cannot shadow or duplicate the user-facing Homebrew CLI.

Both paths install the identical `cisco.sccfm` collection version from Ansible
Galaxy at the standard per-user path. The helper records every directory it
owns and refuses to overwrite an existing unowned copy. Homebrew installation
itself remains an explicitly requested `sccfm-cli` skill operation.

## Uninstall and teardown

Removing the plugin does not remove a Homebrew or pipx CLI installation, the
Galaxy collection, or local SCCFM profiles. Ask the installed plugin:

```text
Completely uninstall SCCFM from this machine.
```

The uninstall skill first shows a validated removal plan with a digest. It can
remove the canonical `ciscodevnet/tap/sccfm-cli` Homebrew formula, the managed
pipx environment, positively discovered non-editable Python installs, and the
standard per-user `cisco.sccfm` collection. Galaxy copies outside the standard
path and editable development installs are preserved by default. After the
exact confirmation `UNINSTALL SCCFM`, the helper recomputes the plan and refuses
to proceed if any target changed.

Profile deletion is separate. Request it explicitly and confirm with
`UNINSTALL SCCFM AND PROFILES`; the uninstall helper then removes the
profile file after the runtime. It never reads or displays the profile contents.
Removing an editable development install also requires an explicit choice before
the plan is confirmed.

Only after runtime teardown, remove the plugin:

Claude Code:

```text
/plugin uninstall sccfm@sccfm-devkit
```

Codex:

```bash
codex plugin remove sccfm@sccfm-devkit
```

Removing the `sccfm-devkit` marketplace is optional and separate. The setup
helper intentionally validates Galaxy paths instead of publishing a broad
recursive-delete command.

## Operation safety

- Verified read-only operations may run automatically.
- Read-only exports or local writes require an explicit destination and opt-in.
- Mutating operations show their preflight result, targets, and exact command,
  then require a standalone `EXECUTE <exact shell command>` message.
- Broad, production, upgrade, and bulk changes require two confirmations.

Claude Code and Codex load the conventional shared `hooks/hooks.json` manifest,
with a root `hooks.json` compatibility copy kept in sync. Both use the same
command guard. When the agent presents a complete mutation plan, it shows
exactly one standalone `EXECUTE <exact shell command>` confirmation line. The
`Stop` hook derives the command from that visible line and records only its hash.
A later identical standalone `EXECUTE <exact shell command>` message creates a
ten-minute, one-use receipt
only when it exactly matches the previously recorded plan. Editing the command,
including adding or removing `--check`, cannot create a receipt. Execution then
continues through the host's normal permission flow. An unused receipt is
cleared when that agent turn ends. Schema-proven read-only CLI commands and
schema-declared preflight-only modes do not need a receipt. Local
`ansible-playbook --syntax-check` validation also proceeds without one,
including with an absolute `ANSIBLE_LOCAL_TEMP` override for sandboxed hosts.
Compound, nested, unknown, or sensitive-argv commands fail closed.

## Local development

Keep the distributed operational skills synchronized with their canonical
repository copies:

```bash
python3 plugins/sccfm/scripts/sync_skills.py
python3 plugins/sccfm/scripts/sync_skills.py --check
```

Validate the Codex plugin with the bundled plugin creator validator and run the
repository tests before publishing.
