# Installation

These are instructions to install the latest CLI and Python library from PyPI, plus the
Ansible collection from GitHub releases. Eventually, the `cisco.sccfm` collection will be
available on Ansible Galaxy.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Installing the CLI](#installing-the-cli)
  - [Prerequisites](#prerequisites)
    - [Install Python 3.12 using Pyenv](#install-python-312-using-pyenv)
  - [Install with pipx](#install-with-pipx)
  - [Install with pip](#install-with-pip)
  - [Install from GitHub Releases](#install-from-github-releases)
  - [Install CLI man pages](#install-cli-man-pages)
  - [Enable shell completion](#enable-shell-completion)
- [Using the Python library](#using-the-python-library)
- [Installing the Ansible collection](#installing-the-ansible-collection)
  - [Download the Ansible collection Bundle.](#download-the-ansible-collection-bundle)
  - [Install Ansible Collection](#install-ansible-collection)
  - [Verify installation](#verify-installation)
  - [Try out examples](#try-out-examples)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Installing the CLI

Follow these steps to install the `cisco-sccfm-devkit` Python package, which provides the
`sccfm-cli` command and the `cisco_sccfm_core` Python library.

### Prerequisites

- Python 3.12 or later available on your `PATH`
  - You can do this by running `python --version` and checking the version you've got installed.
- `pip` installed for that Python (e.g., `python3.12 -m pip`).


#### Install Python 3.12 using Pyenv

```bash
brew install pyenv
pyenv install -s 3.12
pyenv global 3.12
```

### Install with pipx

`pipx` is the recommended install method for the CLI. It keeps the Python environment
isolated while exposing `sccfm-cli` on your `PATH`.

```bash
pipx install cisco-sccfm-devkit
```

### Install with pip

Use `pip` when you are installing into an existing virtual environment:

```bash
python -m pip install cisco-sccfm-devkit
```

### Install from GitHub Releases

If you need an exact release artifact before PyPI is available, install the wheel from
GitHub Releases:

1. Navigate to the [GitHub Releases](https://github.com/CiscoDevNet/sccfm-devkit/releases) page for this project.
2. Download the latest wheel asset named like
   `cisco_sccfm_devkit-<version>-py3-none-any.whl` to your local machine.
3. Install the downloaded wheel:

```bash
pipx install /path/to/cisco_sccfm_devkit-<version>-py3-none-any.whl
```

### Install CLI man pages

Unix-style man pages are generated from the Click command metadata. If you are working
from the repository, install or refresh them locally with:

```bash
source cisco_sccfm_scripts/activate.sh
install-cli-man-docs
```

The helper regenerates `docs/man/man1/*.1`, replaces previously installed
`sccfm-cli*.1` pages in a user-level man directory, and verifies the install with
`man -w sccfm-cli` when `man` is available.

If the helper says the install directory is not in `manpath`, add the printed
`MANPATH` export to your shell startup file.

### Enable shell completion
Add one of the following lines to your shell startup file, then reload your shell (`source ~/.bashrc`, `source ~/.zshrc`, etc.). Note: the env var must match the CLI name (`_SCCFM_CLI_COMPLETE`). 

> ⚠️ Do this only the first time you install sccfm-cli; you don't need to do this every time.

- **bash**

  ```bash
  eval "$(_SCCFM_CLI_COMPLETE=bash_source sccfm-cli)"
  ```

- **zsh**

  ```bash
  autoload -U compinit && compinit
  eval "$(_SCCFM_CLI_COMPLETE=zsh_source sccfm-cli)"
  ```

- **fish**

  ```fish
  eval (env _SCCFM_CLI_COMPLETE=fish_source sccfm-cli)
  ```

If zsh still runs the command instead of installing completions, generate a static file instead:

```bash
mkdir -p ~/.zfunc
_SCCFM_CLI_COMPLETE=zsh_source sccfm-cli > ~/.zfunc/_sccfm-cli
echo 'fpath+=(~/.zfunc)' >> ~/.zshrc
autoload -U compinit && compinit
```

After sourcing, tab completion will work for all `sccfm` commands and options.

## Using the Python library

The same PyPI package exposes the typed `cisco_sccfm_core` library for Python automation:

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

The generated `scc-firewall-manager-sdk` remains the low-level SDK dependency.
`cisco_sccfm_core` is the higher-level library used by the CLI and Ansible collection.

## Installing the Ansible collection

> ⚠️ Before you do this, make sure you've installed the sccfm-cli following the instructions in the section above.

### Download the Ansible collection Bundle.

1. Navigate to the [GitHub Releases](https://github.com/CiscoDevNet/sccfm-devkit/releases) page for this project.
2. Download the latest tar.gz asset, named like `cisco-sccfm-<version>.tar.gz`, to your local machine.

### Install Ansible Collection
```bash
ansible-galaxy collection install /path/to/cisco-sccfm-{version}.tar.gz
```

### Verify installation

```bash
python -c "import cisco_sccfm_core; print('Python package installed')"
ansible-galaxy collection list | grep cisco.sccfm
```

### Try out examples

The fastest way to get going is to use the interactive devkit menu:

```bash
devkit
# select "change-tokens" from the menu
```

Or run the token setup directly:

```bash
change-tokens
```

This prompts for your region, API token, and vault password, then creates `.env`, `.vault_pass`,
`vars.yml`, and encrypted `vault.yml`. Local credential files are Git-ignored and explicitly
excluded from collection release artifacts. Pass `--path /path/to/examples` to override the
default `sccfm-ansible/examples` directory.

See the [Trying out examples](sccfm-ansible/README.md#trying-out-examples) section in the Ansible collection README for the full walkthrough including how to run playbooks.
