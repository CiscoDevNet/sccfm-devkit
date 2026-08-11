# Installation

These are instructions to install the CLI and Python library from PyPI, plus the matching
`cisco.sccfm` collection from Ansible Galaxy or a GitHub release.

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
  - [Install a matched release](#install-a-matched-release)
  - [Install downloaded release artifacts](#install-downloaded-release-artifacts)
  - [Verify installation](#verify-installation)
  - [Authentication and examples](#authentication-and-examples)

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

Installing the CLI with `pipx` is not sufficient for Ansible because pipx keeps that package in an
isolated environment. The collection imports `cisco_sccfm_core` from `cisco-sccfm-devkit`, so the
Python package must be installed in the Python environment that executes the Ansible modules.

### Install a matched release

Use Python `>=3.12,<4.0` and `ansible-core>=2.20,<2.22`. Replace `X.Y.Z` with a version published
on both PyPI and Ansible Galaxy, and install both artifacts at that exact version:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ansible-core>=2.20,<2.22" "cisco-sccfm-devkit==X.Y.Z"
ansible-galaxy collection install "cisco.sccfm:==X.Y.Z"
```

Upgrade or roll back the Python package and collection together. Mixing release versions is
unsupported.

### Install downloaded release artifacts

To install release artifacts directly, download the wheel and same-version collection tarball from
[GitHub Releases](https://github.com/CiscoDevNet/sccfm-devkit/releases), then install both into the
Ansible environment:

```bash
python -m pip install /path/to/cisco_sccfm_devkit-X.Y.Z-py3-none-any.whl
ansible-galaxy collection install /path/to/cisco-sccfm-X.Y.Z.tar.gz --force
```

### Verify installation

```bash
python -c 'from importlib.metadata import version; print(version("cisco-sccfm-devkit"))'
python -m pip check
ansible-galaxy collection list cisco.sccfm
ansible-doc -l -t module cisco.sccfm
ansible-doc -t inventory cisco.sccfm.sccfm
```

The Python and collection versions printed above must be identical.

### Authentication and examples

Provide `SCCFM_REGION` and `SCCFM_API_TOKEN` through the controller or execution environment's
secret manager. See the collection's [packaged installation, authentication, execution environment,
and example instructions](sccfm-ansible/README.md#installation) for the complete consumer workflow.
