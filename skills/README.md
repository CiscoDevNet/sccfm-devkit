# AI Agent Skills

This directory contains skill files that give AI coding agents (Copilot, Claude, Cursor, etc.) the context they need to work effectively with this project.

## What are skills?

Each skill is a `SKILL.md` file containing:

- **When to activate** — what kinds of user requests trigger this skill
- **Environment setup** — how to activate the virtualenv and configure tokens
- **Command reference** — how to discover and run commands
- **Patterns and conventions** — project-specific patterns the agent should follow
- **Architecture context** — where code lives and how it's structured

Skills are tool-agnostic markdown files. Any AI agent that reads them gets the same context.

## Available skills

| Skill | File | Use when... |
|-------|------|-------------|
| **sccfm-cli** | [sccfm-cli/SKILL.md](sccfm-cli/SKILL.md) | Running CLI commands, managing devices, objects, policies |
| **sccfm-ansible** | [sccfm-ansible/SKILL.md](sccfm-ansible/SKILL.md) | Discovering `cisco.sccfm` modules with `ansible-doc`, writing/running playbooks, managing Ansible vault, creating modules |

## How agents use these

### VS Code Copilot / Claude

Skills are auto-discovered via the `.claude/skills` symlink. When a user's request matches a skill's `description`, the agent loads the skill file before responding.

### Codex

Skills are auto-discovered via `.agents/skills` symlinks. The symlinks point at
the canonical files under `skills/`, so Claude and Codex read the same skill
content.

### Claude Code (or any agent reading `~/.claude/skills/`)

If you have the repo cloned, the project-level `.claude/skills` symlink is enough. To install the skills **user-wide** so they're available outside this repo, run:

```bash
./cisco_sccfm_scripts/install_skills.sh
```

This copies each skill into `~/.claude/skills/`. Use `--uninstall` to remove them, or pass a custom target directory as the first argument.

### Other agents

Point your agent at the relevant `SKILL.md` file, or include it in your system prompt. The files are self-contained — no special tooling needed.

### Manual reference

The skill files are also useful as human-readable quick-reference guides for the CLI and Ansible collection.

## Adding a new skill

1. Create a directory under `skills/` with a descriptive name
2. Add a `SKILL.md` file with the following frontmatter:

```yaml
---
name: my-skill
description: One-line description of what this skill covers and when to use it.
allowed-tools: "Read Grep Glob"
---
```

3. Write the skill body with sections for environment setup, discovery commands, patterns, and architecture
4. The `.claude/skills` symlink ensures VS Code auto-discovery works without duplicating files
