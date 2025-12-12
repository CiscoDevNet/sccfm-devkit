# sccfm-devkit ![CI](https://github.com/cisco-lockhart/sccfm-devkit/actions/workflows/ci.yml/badge.svg)

Toolkit for interacting with SCC Firewall Manager (SCCFM): a CLI plus an upcoming Ansible collection. Shared business logic lives in `sccfm_core` so both the CLI and the collection can reuse the same inventory/health SDK integrations; the CLI remains in `sccfm_cli`.

## Getting started

```bash
scripts/setup_environment.sh   # installs pyenv, Python 3.12.4, Poetry deps
scripts/activate.sh            # activates the project virtualenv
sccfm-cli --help
```

`setup_environment.sh` keeps everything local to the repository: pyenv provides Python 3.12.4, `.venv/` hosts the runtime, and Poetry installs the project plus dev dependencies.

## Commands

- `sccfm-cli configure [--region REGION] [--api-token TOKEN] [--config-path PATH]`: Captures the SCCFM region (`in`, `au`, `uae`, `us`, `eu`, `apj`, `int`) plus an API token (see the [auth guide](https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/authentication/)) and stores it under `~/.sccfm-cli/` (override with `--config-path` or `SCCFM_CONFIG`).
- `sccfm-cli status [--config-path PATH]`: Shows the current profile plus mock subsystem health using Rich tables.
- `sccfm-cli inventory devices list [--limit N] [--offset N] [--query TEXT] [--format table|json]`: Lists device inventory with pagination and optional name filtering.
- `sccfm-cli inventory managers list [--limit N] [--offset N] [--query TEXT] [--format table|json]`: Lists manager inventory with the same filters.

Set the active profile once via the global option: `sccfm-cli --profile lab status`.
Every command lives in `sccfm_cli/commands/` as a concrete implementation of the command-pattern friendly `BaseCommand`, keeping files small and behavior isolated.

## Ansible collection

- macOS: `brew install ansible` (this includes `ansible-galaxy`; verify with `ansible-galaxy --version`).
- Install the collection locally from the collection root (`sccfm-ansible/`) with `ansible-galaxy collection install ./sccfm-ansible`.
- For IDEs/mypy, add `sccfm-ansible` to `ANSIBLE_COLLECTIONS_PATH` (or mark it as a source root) so imports under `ansible_collections.cisco.sccfm` resolve without installing.
- Configure SCCFM region (`int`, `us`, `eu`, `apj`, `aus`, `uae`, or `in`) plus `SCCFM_API_TOKEN`; you can set them via env vars or inline (i.e., write the values directly in the inventory file—useful for local dev, but prefer env vars or Ansible Vault for anything shared).
- Point Ansible at an inventory file that uses the plugin, e.g. `ansible-inventory -i sccfm-ansible/examples/inventory.sccfm.yml --graph`.
- A starter playbook is in `sccfm-ansible/examples/show_devices.yml`; it runs against the SCCFM devices discovered by the inventory plugin.

## Development

```bash
scripts/activate.sh
poetry run pytest
poetry run mypy sccfm_cli
poetry run black .
```

See `CONTRIBUTING.md` for commit guidelines (Commitizen) and contribution expectations. The setup script also installs a local `git cz` alias that runs `./scripts/cz.sh commit` so you can use `git cz` for conventional commits with visible pre-commit output.

## Packaging for pip

Build a source distribution plus wheel using Poetry and install them with pip:

```bash
poetry build
pip install dist/sccfm_cli-*.whl    # or `pip install dist/sccfm_cli-*.tar.gz`
```

See `INSTALL.md` for installing a released wheel and enabling shell completion.

Key tooling:

- `click` plus `click-option-group` power the CLI ergonomics, and `rich` handles presentation.
- `pytest`, `coverage`, `mypy`, `black`, `isort`, and `pre-commit` enforce correctness and consistency.

To add a new command, drop a file under `sccfm_cli/commands/`, subclass `BaseCommand`, and register it in `sccfm_cli/cli.py`. SDK integrations live in `sccfm_core/`, keeping external dependencies isolated and easy to reuse (CLI or Ansible).

## Troubleshooting

### Tests fail with "No such command" errors

If tests fail with messages like `Usage: group inventory devices asa [OPTIONS] COMMAND [ARGS]...` instead of executing commands, you likely have stale Python bytecode caches.

**Solution:**

```bash
poetry install  # Reinstall the package in editable mode
find . -type d -name "__pycache__" -exec rm -rf {} +  # Clear all bytecode caches
poetry run pytest  # Rerun tests
```

**Why this happens:** When you modify command structure or add new CLI commands, Python's `__pycache__` directories can retain old `.pyc` files that don't reflect your changes. Tests then run against the cached version instead of your updated source code.

**Prevention:** After modifying command registrations or CLI structure, always reinstall the package and clear caches before running tests.
