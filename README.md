# sccfm-cli

Command-line tool for interacting with the SCC Firewall Manager (SCCFM). The CLI follows a strict command pattern so new commands can be added safely and consistently.

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

## Development

```bash
scripts/activate.sh
poetry run pytest
poetry run mypy sccfm_cli
poetry run black .
```

See `CONTRIBUTING.md` for commit guidelines (Commitizen) and contribution expectations.

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

To add a new command, drop a file under `sccfm_cli/commands/`, subclass `BaseCommand`, and register it in `sccfm_cli/cli.py`. Delegating integrations to `sccfm_cli/services/` keeps external dependencies isolated and easy to mock.
