# sccfm-devkit

Toolkit for interacting with SCC Firewall Manager (SCCFM): a Python CLI (`sccfm-cli`) plus a `cisco.sccfm` Ansible collection. Shared business logic lives in `cisco_sccfm_core`; the CLI entry points are in `cisco_sccfm_cli`; Ansible plugins are in `sccfm-ansible/`.

## Agent skills (read these FIRST)

This repository ships skill files that document how to interact with the CLI and Ansible collection. Load the relevant skill before doing any related work — the skills cover environment activation, command discovery, exit-code handling, and verification patterns that you will get wrong without them.

- [skills/sccfm-cli/SKILL.md](skills/sccfm-cli/SKILL.md) — using the `sccfm-cli` tool
- [skills/sccfm-ansible/SKILL.md](skills/sccfm-ansible/SKILL.md) — using the `cisco.sccfm` Ansible collection
- [skills/README.md](skills/README.md) — overview of the skills system

**When making changes to CLI commands or Ansible modules, you MUST use the relevant skill to verify your changes work end-to-end** — run the discovery flow, exercise the affected commands, and check exit codes as the skill describes.

## Dev environment tips

- **Python version**: Use Python 3.12 (managed by pyenv; `cisco_sccfm_scripts/setup_environment.sh` installs it automatically).
- **Virtual env**:
  ```bash
  cisco_sccfm_scripts/setup_environment.sh   # installs pyenv, Python 3.12.4, Poetry deps, pre-commit hooks
  source cisco_sccfm_scripts/activate.sh     # activates the project virtualenv
  ```
- **direnv (recommended)**: Install direnv so the venv activates automatically on `cd`:
  ```bash
  brew install direnv
  echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
  source ~/.zshrc
  direnv allow
  ```
- Use `poetry` for dependency management.
- Use `black` for syntax formatting.
- Use `isort` for import sorting.
- Use `mypy` for static type checking.
- Use `pytest` for testing.
- Use `coverage` for test coverage.
- Use `pre-commit` for pre-commit hooks.
- Use `click` for CLI configuration.
- Use `rich` for command-line output.
- Use `questionary` for user prompts.
- Add virtualenv scripts.
- **Type hints are mandatory.** Every function and method must be fully typed. `mypy --strict` is enforced.
- **No long methods.** The code should be structured so it can be easily extended. Use the command pattern for each command; one file per command under `cisco_sccfm_cli/commands/`.
- Each external library (e.g., the `scc-firewall-manager-sdk`) must be isolated in a separate services directory under `cisco_sccfm_core/services/`, not in CLI or Ansible modules directly.
- Humans will be extending this code; do not generate AI slop.

### Quick run examples

```bash
source cisco_sccfm_scripts/activate.sh

# Configure credentials once
sccfm-cli configure --region us  # API token is entered at a hidden prompt

# Check connectivity
sccfm-cli status

# List devices
sccfm-cli inventory devices list --format table

# Interactive developer menu (test, lint, format, build collection, etc.)
devkit
```

## Required environment variables

For non-interactive use, pre-set these values in the environment (loaded automatically by direnv):

```bash
export SCCFM_REGION=us          # int | us | eu | apj | au | uae | in | ci
export SCCFM_API_TOKEN="..."    # from SCCFM UI > Settings > API Tokens
```

Credentials are also stored under `~/.sccfm-cli/` after running `sccfm-cli configure`. On POSIX,
the CLI enforces mode `0700` on that directory and `0600` on its configuration file. On Windows,
keep it in the user profile and rely on filesystem ACLs. Override the path with `--config-path` or
`SCCFM_CONFIG`, and keep custom paths private.

## Testing instructions

```bash
source cisco_sccfm_scripts/activate.sh
pytest                          # full unit test suite
pytest -k "test_inventory"      # filter by name
coverage run -m pytest && coverage report
```

- Unit tests live alongside source: `cisco_sccfm_cli/tests/`, `cisco_sccfm_core/tests/`, `sccfm-ansible/` (excluding `e2e/`).
- Tests marked `ci` require a live SCCFM tenant and run only in CI.
- **Test the CLI against a real SCCFM tenant** using a DevNet sandbox:
  Visit [https://devnetsandbox.cisco.com/DevNet](https://devnetsandbox.cisco.com/DevNet) to book a related sandbox.

### MCP server links

No MCP servers are currently configured for this project. Skill files under `skills/` provide the equivalent context for AI agents.

### Latest Cisco API documentation

- SCCFM authentication guide: [https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/authentication/](https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/authentication/)
- Full Cisco developer docs: [https://developer.cisco.com/docs/](https://developer.cisco.com/docs/)

### Ansible collection

```bash
# Build and install locally
build-ansible-collection

# Set up tokens and vault (generated credential files are ignored and excluded from builds)
devkit   # select "change-tokens"

# Verify inventory plugin
ansible-inventory -i sccfm-ansible/examples/inventory.sccfm.yml --graph

# Run starter playbook
ansible-playbook -i sccfm-ansible/examples/inventory.sccfm.yml sccfm-ansible/examples/show_devices.yml
```

Add `sccfm-ansible` to `ANSIBLE_COLLECTIONS_PATH` so IDE/mypy resolves `ansible_collections.cisco.sccfm` imports.

## PR instructions

- **Do not commit unless explicitly instructed.** ("Do not commit unless I tell you to.")
- **Conventional commits** are enforced via Commitizen and pre-commit hooks:
  ```bash
  pre-commit install && pre-commit install --hook-type commit-msg
  git cz    # or: ./cisco_sccfm_scripts/cz.sh commit
  ```
  CI will fail on non-compliant commit messages.
- **Security**: Never commit real credentials, tokens, or secrets. Use placeholders and document required env vars. See [SECURITY.md](SECURITY.md) for vulnerability reporting.
- New commands go in `cisco_sccfm_cli/commands/` as a `BaseCommand` subclass, registered in `cisco_sccfm_cli/cli.py`.
- New SDK integrations go in `cisco_sccfm_core/services/`.
- Every behavior change must be accompanied by tests.

## Contribution conventions

- **Backward compatibility**: Do not change existing command behavior unless clearly improving or fixing a bug; document changes in the PR description.
- **No AI slop**: short, well-named methods only; no generated boilerplate.
- **Line length**: 100 characters (`black` and `flake8` are configured accordingly).
- **License header**: every `.py` file must start with the Apache-2.0 SPDX header (after a shebang, if present). `reuse` enforces this in pre-commit and CI:
  ```python
  # Copyright 2026 Cisco Systems, Inc. and its affiliates
  #
  # SPDX-License-Identifier: Apache-2.0
  ```
- **Secrets**: never read or commit `.env`, `.env.*`, `.vault_pass`, or real `vault.yml` files — use the `*.example` templates. Keep tracked `.envrc` files secret-free. `gitleaks` and `detect-private-key` block secrets in pre-commit.
- See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide.
