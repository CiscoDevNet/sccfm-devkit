# sccfm-devkit

Toolkit for interacting with SCC Firewall Manager (SCCFM): a Python CLI (`sccfm-cli`) plus a `cisco.sccfm` Ansible collection. Shared business logic lives in `sccfm_core`; the CLI entry points are in `sccfm_cli`; Ansible plugins are in `sccfm-ansible/`.

## Agent skills (read these FIRST)

This repository ships skill files that document how to interact with the CLI and Ansible collection. Load the relevant skill before doing any related work — the skills cover environment activation, command discovery, exit-code handling, and verification patterns that you will get wrong without them.

- [skills/sccfm-cli/SKILL.md](skills/sccfm-cli/SKILL.md) — using the `sccfm-cli` tool
- [skills/sccfm-ansible/SKILL.md](skills/sccfm-ansible/SKILL.md) — using the `cisco.sccfm` Ansible collection
- [skills/README.md](skills/README.md) — overview of the skills system

**When making changes to CLI commands or Ansible modules, you MUST use the relevant skill to verify your changes work end-to-end** — run the discovery flow, exercise the affected commands, and check exit codes as the skill describes.

## Dev environment tips

- **Python version**: Use Python 3.12 (managed by pyenv; `scripts/setup_environment.sh` installs it automatically).
- **Virtual env**:
  ```bash
  scripts/setup_environment.sh   # installs pyenv, Python 3.12.4, Poetry deps, pre-commit hooks
  source scripts/activate.sh     # activates the project virtualenv
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
- **No long methods.** The code should be structured so it can be easily extended. Use the command pattern for each command; one file per command under `sccfm_cli/commands/`.
- Each external library (e.g., the `scc-firewall-manager-sdk`) must be isolated in a separate services directory under `sccfm_core/services/`, not in CLI or Ansible modules directly.
- Humans will be extending this code; do not generate AI slop.

### Quick run examples

```bash
source scripts/activate.sh

# Configure credentials once
sccfm-cli configure --region us --api-token <YOUR_TOKEN>

# Check connectivity
sccfm-cli status

# List devices
sccfm-cli inventory devices list --format table

# Interactive developer menu (test, lint, format, build collection, etc.)
devkit
```

## Required environment variables

Copy `.env.example` to `.env` and fill in your values (loaded automatically by direnv):

```bash
export SCCFM_REGION=us          # int | us | eu | apj | au | uae | in | ci
export SCCFM_API_TOKEN="..."    # from SCCFM UI > Settings > API Tokens
```

Credentials are also stored under `~/.sccfm-cli/` after running `sccfm-cli configure`. Override the path with `--config-path` or `SCCFM_CONFIG`.

## Testing instructions

```bash
source scripts/activate.sh
pytest                          # full unit test suite
pytest -k "test_inventory"      # filter by name
coverage run -m pytest && coverage report
```

- Unit tests live alongside source: `sccfm_cli/tests/`, `sccfm_core/tests/`, `sccfm-ansible/` (excluding `e2e/`).
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

# Set up tokens and vault
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
  git cz    # or: ./scripts/cz.sh commit
  ```
  CI will fail on non-compliant commit messages.
- **Security**: Never commit real credentials, tokens, or secrets. Use placeholders and document required env vars. See [SECURITY.md](SECURITY.md) for vulnerability reporting.
- New commands go in `sccfm_cli/commands/` as a `BaseCommand` subclass, registered in `sccfm_cli/cli.py`.
- New SDK integrations go in `sccfm_core/services/`.
- Every behavior change must be accompanied by tests.

## Contribution conventions

- **Backward compatibility**: Do not change existing command behavior unless clearly improving or fixing a bug; document changes in the PR description.
- **No AI slop**: short, well-named methods only; no generated boilerplate.
- **Line length**: 100 characters (`black` and `flake8` are configured accordingly).
- See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide.
