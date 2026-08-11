# Cisco Security Cloud Control Firewall Manager (SCCFM) DevKit ![CI](https://github.com/CiscoDevNet/sccfm-devkit/actions/workflows/ci.yml/badge.svg)

Toolkit for interacting with Security Cloud Control Firewall Manager (SCCFM): a Python
package with the `sccfm-cli` command, a reusable `cisco_sccfm_core` automation library,
and an Ansible collection. Shared business logic lives in `cisco_sccfm_core` so the CLI,
Python scripts, and collection can reuse the same SDK integrations.

**Documentation:** [Generated CLI and Ansible reference](https://ciscodevnet.github.io/sccfm-devkit/)

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Getting started](#getting-started)
- [Commands](#commands)
- [Python library](#python-library)
- [Ansible collection](#ansible-collection)
- [Development](#development)
- [CLI Installation](#cli-installation)
- [Troubleshooting](#troubleshooting)
  - [Tests fail with "No such command" errors](#tests-fail-with-no-such-command-errors)
- [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Getting started

```bash
cisco_sccfm_scripts/setup_environment.sh   # installs pyenv, Python 3.12.4, Poetry deps
source cisco_sccfm_scripts/activate.sh     # activates the project virtualenv
sccfm-cli --help               # the main SCCFM CLI
devkit                         # interactive developer toolkit menu
```

`setup_environment.sh` keeps everything local to the repository: pyenv provides Python 3.12.4, `.venv/` hosts the runtime, and Poetry installs the project plus dev dependencies.

## Commands

- `sccfm-cli configure --region REGION [--config-path PATH]`: Captures the SCCFM region (`int`, `us`, `eu`, `apj`, `au`, `uae`, `in`, or `ci`) plus an API token (see the [auth guide](https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/authentication/)). The token comes from a pre-set `SCCFM_API_TOKEN` or, in an interactive terminal, a hidden prompt. Direct `--api-token` input remains available for compatibility but can expose the token in shell history and process listings.
- `sccfm-cli status [--config-path PATH]`: Shows the current profile plus SCCFM connectivity health using Rich tables.
- `sccfm-cli inventory devices list [--limit N] [--offset N] [--query TEXT] [--format table|json]`: Lists device inventory with pagination and optional name filtering.
- `sccfm-cli inventory manager list [--limit N] [--offset N] [--query TEXT] [--format table|json]`: Lists manager inventory with the same filters.
- `sccfm-cli inventory devices asa change-boot-image --image-path disk0:/asa9xxx.bin ...`: Changes the configured ASA boot image for the next reload. The image must already exist on the device; the command does not upload or reboot. `--check` performs non-mutating validation of the image path and containing filesystem before any change.

Set the active profile once via the global option: `sccfm-cli --profile lab status`.
Every command lives in `cisco_sccfm_cli/commands/` as a concrete implementation of the command-pattern friendly `BaseCommand`, keeping files small and behavior isolated.

By default, configuration is stored in `~/.sccfm-cli/config.json`. On POSIX systems the CLI
enforces mode `0700` on `~/.sccfm-cli` and `0600` on the configuration file, including existing
storage. On Windows, keep the configuration in your user profile and rely on the filesystem's
per-user access controls. Keep custom configuration paths private on every platform.

Generated CLI reference docs can be previewed locally:

```bash
generate-cli-docs
generate-cli-man-docs
```

The generated Markdown is written under `docs/cli/`; generated man pages are written
under `docs/man/man1/`.

To install or refresh the CLI man pages for local `man sccfm-cli` lookup:

```bash
install-cli-man-docs
```

See [docs/README.md](docs/README.md) for generation details.

## Python library

Installing the `cisco-sccfm-devkit` package also exposes `cisco_sccfm_core`, a typed high-level
Python automation library built on top of the generated `scc-firewall-manager-sdk`.

```python
from dataclasses import dataclass

from cisco_sccfm_core import InventoryService


@dataclass(frozen=True)
class Config:
    region: str
    api_token: str


inventory = InventoryService(Config(region="us", api_token="..."))
devices = inventory.get_devices(limit=10, offset=0, query=None)
```

The package root exports the supported public service classes and response models through
`cisco_sccfm_core.__all__`. Internal modules may change between releases.

## Ansible collection

- macOS: `brew install ansible` (this includes `ansible-galaxy`; verify with `ansible-galaxy --version`).
- Build and install the collection locally: `build-ansible-collection`.
- Set up tokens interactively with `devkit` and select **change-tokens**. By default this writes
  `.vault_pass` and encrypted `group_vars/all/vault.yml` under `sccfm-ansible/examples`; both are
  Git-ignored and explicitly excluded from collection artifacts. Use `--path` to override the
  examples directory when needed.
- For IDEs/mypy, add `sccfm-ansible` to `ANSIBLE_COLLECTIONS_PATH` (or mark it as a source root) so imports under `ansible_collections.cisco.sccfm` resolve without installing.
- Configure SCCFM region (`int`, `us`, `eu`, `apj`, `au`, `uae`, `in`, or `ci`) plus
  `SCCFM_API_TOKEN` in the controller environment. Never commit a plaintext token to an inventory
  source.
- Point Ansible at an inventory file that uses the plugin, e.g. `ansible-inventory -i sccfm-ansible/examples/inventory.sccfm.yml --graph`.
- The inventory plugin consumes its API token only during refresh and never exports it as a host
  or group variable. Do not use inventory output modes that render vars when your own
  `group_vars` or `host_vars` contain secrets.
- A starter playbook is in `sccfm-ansible/examples/show_devices.yml`; it runs against the SCCFM devices discovered by the inventory plugin.
- Generated Ansible reference docs can be previewed locally with `generate-ansible-docs`; see [docs/README.md](docs/README.md) for details.

## Development

All common development tasks are available through the interactive `devkit` menu:

```bash
source cisco_sccfm_scripts/activate.sh
devkit
```

This presents an interactive selector with the following tasks:

| Task | Description |
|------|-------------|
| **change-tokens** | Set up SCCFM API tokens, .env, and Ansible Vault |
| **build-collection** | Build the cisco.sccfm Ansible collection tarball |
| **generate-ansible-docs** | Generate Ansible reference docs from ansible-doc output |
| **generate-cli-docs** | Generate CLI reference docs from Click help output |
| **generate-cli-man-docs** | Generate CLI man pages from Click metadata |
| **install-cli-man-docs** | Install generated CLI man pages for local man lookup |
| **setup-env** | Bootstrap environment (pyenv, venv, Poetry deps) |
| **test** | Run the test suite (pytest), with optional filter & verbose |
| **lint** | Run mypy + flake8 |
| **format** | Auto-format code with black + isort |

After a task completes you're returned to the menu — select **Exit** when done.

The underlying tools are still available directly if needed:

```bash
source cisco_sccfm_scripts/activate.sh
pytest
mypy cisco_sccfm_cli
black .
```

See `CONTRIBUTING.md` for commit guidelines (Commitizen) and contribution expectations. The setup script also installs a local `git cz` alias that runs `./cisco_sccfm_scripts/cz.sh commit` so you can use `git cz` for conventional commits with visible pre-commit output.

## CLI Installation

For contributors, use the repository environment from [Getting started](#getting-started).

For end users, install the published PyPI package with `pipx` when possible. `pipx`
keeps the CLI isolated while exposing `sccfm-cli` on `PATH`:

```bash
pipx install cisco-sccfm-devkit
```

Installing into a virtual environment with `pip` is also supported:

```bash
python -m pip install cisco-sccfm-devkit
```

See `INSTALL.md` for installation options and shell completion.

Key tooling:

- `click` plus `click-option-group` power the CLI ergonomics, and `rich` handles presentation.
- `pytest`, `coverage`, `mypy`, `black`, `isort`, and `pre-commit` enforce correctness and consistency.
- ASA disk discovery can help operators find likely image paths before using `change-boot-image`, and `change-boot-image --check` validates the chosen path on-device before mutating config.

To add a new command, drop a file under `cisco_sccfm_cli/commands/`, subclass `BaseCommand`, and register it in `cisco_sccfm_cli/cli.py`. SDK integrations live in `cisco_sccfm_core/`, keeping external dependencies isolated and easy to reuse (CLI or Ansible).

## Troubleshooting

### Tests fail with "No such command" errors

If tests fail with messages like `Usage: group inventory devices asa [OPTIONS] COMMAND [ARGS]...` instead of executing commands, you likely have stale Python bytecode caches.

**Solution:**

```bash
poetry install  # Reinstall the package in editable mode
find . -type d -name "__pycache__" -exec rm -rf {} +  # Clear all bytecode caches
source cisco_sccfm_scripts/activate.sh
pytest  # Rerun tests
```

**Why this happens:** When you modify command structure or add new CLI commands, Python's `__pycache__` directories can retain old `.pyc` files that don't reflect your changes. Tests then run against the cached version instead of your updated source code.

**Prevention:** After modifying command registrations or CLI structure, always reinstall the package and clear caches before running tests.

## License

Distributed under the Apache 2.0 License. See [LICENSE](LICENSE) for more information.
