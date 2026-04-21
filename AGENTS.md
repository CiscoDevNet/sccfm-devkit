# sccfm-api-cli

## Agent skills (read these FIRST)

This repository ships skill files that document how to interact with the CLI and Ansible collection. Load the relevant skill before doing any related work — the skills cover environment activation, command discovery, exit-code handling, and verification patterns that you will get wrong without them.

- [skills/sccfm-cli/SKILL.md](skills/sccfm-cli/SKILL.md) — using the `sccfm-cli` tool
- [skills/sccfm-ansible/SKILL.md](skills/sccfm-ansible/SKILL.md) — using the `cisco.sccfm` Ansible collection
- [skills/README.md](skills/README.md) — overview of the skills system

**When making changes to CLI commands or Ansible modules, you MUST use the relevant skill to verify your changes work end-to-end** — run the discovery flow, exercise the affected commands, and check exit codes as the skill describes.

## Dev environment tips

- Use `poetry` for dependency management.
- Use `black` for syntax formatting.
- Use `isort` for import sorting.
- Use `mypy` for static type checking.
- Use `pytest` for testing.
- Use `coverage` for test coverage.
- Use `pre-commit` for pre-commit hooks.
- Use `click` for CLI configuration
- Use `rich` for command-line output
- Use `questionary` for user prompts
- Add virtualenv scripts.
- The code should be structured in a way that it can be easily extended. Use the command pattern for each command.
- Each external library we use - for example, the scc firewall SDK and the pyvmomi libraries - should be put into a separate services directory.
- Humans will be extending this code; do not generate AI slop. No long methods!
- Use Python type hints strictly. Do not write code without typing.

## Commit and PR instructions

- Do not commit unless I tell you to.
