---
name: sccfm-uninstall
description: Safely discover and remove local SCC Firewall Manager runtime artifacts, including Homebrew, pipx, or legacy Python sccfm-cli installs, the managed Ansible companion, the standard cisco.sccfm collection, and optional named profiles. Use for uninstall, teardown, or complete SCCFM cleanup. Do not use for installation, repair, CLI operations, or Ansible automation.
allowed-tools: "Bash(python3 *) Read"
---

# SCC Firewall Manager Uninstall

Remove SCCFM runtime artifacts before removing this plugin. Use only the packaged
helper; do not construct manual `pip uninstall` or recursive-delete commands.

## 1. Generate the reviewed plan

Resolve this skill's plugin root, then run:

```bash
python3 scripts/setup_runtime.py cleanup-plan --json
```

Add `--remove-profiles` only when the user explicitly asks to delete named
profiles and their stored API tokens. The helper reports profile metadata but
never reads or displays profile contents.

The plan discovers the canonical `ciscodevnet/tap/sccfm-cli` Homebrew formula,
the managed pipx environment, the helper-owned Homebrew Ansible companion,
non-editable Python installs, and the positively identified standard Galaxy
collection. It reports each installation method and version independently so
multiple installs can be reviewed and removed together. Never infer Homebrew
ownership from an executable path or remove a same-named formula from another
tap. The reviewed Homebrew command disables automatic dependency removal so it
mutates only the SCCFM formula.

The helper preserves collections outside the standard per-user path. It also
preserves editable Python installs by default; if any are reported, explain
their source and ask whether the user also wants to remove those development
installs. Only after that explicit choice, regenerate the plan with
`--include-editable`.

Show the complete plan, including preserved artifacts and `plan_digest`. Do not
continue if discovery or path validation fails.

## 2. Require exact confirmation

When profiles are preserved, require the standalone confirmation:

```text
UNINSTALL SCCFM
```

When profiles and their API tokens will be deleted, require:

```text
UNINSTALL SCCFM AND PROFILES
```

`AND PROFILES` explicitly authorizes deletion of the named-profile store and
its API tokens. The confirmation authorizes only the reviewed plan. It does not
authorize different targets, editable installs that were not included in that
plan, or plugin removal.

## 3. Execute the same plan

After confirmation, use the same options and the exact digest returned by the
plan:

```bash
python3 scripts/setup_runtime.py cleanup --plan-digest <digest> --yes
```

Include `--remove-profiles` and `--include-editable` exactly when they appeared
in the reviewed plan. The helper recomputes discovery and refuses to proceed if
the target set changed after review.

The helper removes the standard Galaxy collection and its owned Ansible
companion first, then reviewed pipx, Homebrew, and discovered Python packages,
and finally the profile when requested. Never bypass a helper refusal with
direct filesystem deletion.

## 4. Verify and remove the plugin separately

Run:

```bash
python3 scripts/setup_runtime.py doctor --json
```

Teardown is complete only when the requested CLI packages, collection, and
profile are absent. A preserved editable install is not an error when the user
chose to keep it.

After successful teardown, tell the user that plugin removal is separate. Use
`/plugin uninstall sccfm@sccfm-devkit` in Claude Code or
`codex plugin remove sccfm@sccfm-devkit` in Codex.
