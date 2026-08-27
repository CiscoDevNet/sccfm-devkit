# SCC Firewall Manager agent plugin

This plugin packages guided setup and safety-aware operation for `sccfm-cli` and
the `cisco.sccfm` Ansible collection. It supports Claude Code and Codex from the
same source tree.

See the [complete capability and end-user guide](../../docs/agent-plugin.md) for
the three-skill design, safety model, workflows, and examples.

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

The guided setup checks prerequisites, proposes an exact version-matched
installation plan, installs the CLI and Ansible runtime only after confirmation,
and explains how to enter an SCCFM API token through the CLI's masked local
prompt. Tokens are never requested in chat.

The recommended runtime keeps `sccfm-cli`, `ansible-core`, and
`cisco_sccfm_core` in the same pipx environment, then installs the identical
`cisco.sccfm` collection version from Ansible Galaxy. The helper uses the
standard per-user Galaxy path and records the exact collection directory it
owns; it refuses to overwrite an existing unowned copy.

## Uninstall and teardown

Removing the plugin does not remove the pipx environment, the Galaxy collection,
or local SCCFM profiles. Ask the installed plugin:

```text
Uninstall the SCCFM runtime installed by this plugin.
```

The setup skill first shows a validated removal plan. After the exact
confirmation `UNINSTALL SCCFM`, it removes the discovered `cisco.sccfm`
collection only when it matches the helper's ownership record, then runs `pipx
uninstall cisco-sccfm-devkit`. Other reported Galaxy copies and the profile
store at `~/.sccfm-cli/config.json` are preserved by default.

Profile deletion is separate. Request it explicitly and confirm with
`UNINSTALL SCCFM AND DELETE PROFILES`; the setup helper then removes the profile
file after the runtime. It never reads or displays the profile contents.

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
host-aware command guard. When the agent presents a complete mutation plan, its
final response includes `SCCFM_APPROVAL_COMMAND: <exact shell command>`. The
`Stop` hook records only that command's hash. A later standalone
`EXECUTE <exact shell command>` message creates a ten-minute, one-use receipt
only when it exactly matches the previously recorded plan. Editing the command,
including adding or removing `--check`, cannot create a receipt. Claude then
requests interactive host approval; Codex continues through its native command
permission flow. An unused receipt is cleared when that agent turn ends.
Schema-proven read-only CLI commands do not need a receipt. Compound, nested,
unknown, or sensitive-argv commands fail closed.

## Local development

Keep the distributed operational skills synchronized with their canonical
repository copies:

```bash
python3 plugins/sccfm/scripts/sync_skills.py
python3 plugins/sccfm/scripts/sync_skills.py --check
```

Validate the Codex plugin with the bundled plugin creator validator and run the
repository tests before publishing.
