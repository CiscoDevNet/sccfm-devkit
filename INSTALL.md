# Installation

These are instructions to install the latest CLI and Ansible collection from Github releases. Eventually,
- The `sccfm-cli` will be available on Pypi.org
- The `sccfm-ansible` collection will be available on Ansible Galaxy.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [Installing the CLI](#installing-the-cli)
  - [Prerequisites](#prerequisites)
    - [Install Python 3.12 using Pyenv](#install-python-312-using-pyenv)
  - [Download the wheel](#download-the-wheel)
  - [Install with pip](#install-with-pip)
  - [Enable shell completion](#enable-shell-completion)
- [Installing the Ansible collection](#installing-the-ansible-collection)
  - [Download the Ansible collection Bundle.](#download-the-ansible-collection-bundle)
  - [Install Ansible Collection](#install-ansible-collection)
  - [Verify installation](#verify-installation)
  - [Try out examples](#try-out-examples)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Installing the CLI

Follow these steps to install the `sccfm` CLI from a released wheel and enable shell completion.

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

### Download the wheel

1. Navigate to the [GitHub Releases](https://github.com/cisco-lockhart/sccfm-devkit/releases) page for this project.
2. Download the latest wheel asset named like `sccfm-<version>-py3-none-any.whl` to your local machine.

### Install with pip

```bash
pip install /path/to/sccfm-<version>-py3-none-any.whl
```

Replace the path with where you saved the wheel. You can also install into a virtual environment if desired.

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


## Installing the Ansible collection

> ⚠️ Before you do this, make sure you've installed the sccfm-cli following the instructions in the section above.

### Download the Ansible collection Bundle.

1. Navigate to the [GitHub Releases](https://github.com/cisco-lockhart/sccfm-devkit/releases) page for this project.
2. Download the latest tar.gz asset, named like `cisco-sccfm-<version>.tar.gz`, to your local machine.

### Install Ansible Collection
```bash
ansible-galaxy collection install /path/to/cisco-sccfm-{version}.tar.gz
```

### Verify installation

```bash
python -c "import sccfm_core; print('✅ Python package installed')"
ansible-galaxy collection list | grep cisco.sccfm
```

### Try out examples

The fastest way to get going is to use the interactive devkit menu:

```bash\npoetry run devkit\n# select "setup-tokens" from the menu\n```

Or run the token setup directly:

```bash
poetry run setup-tokens
```

This will prompt for your region, API token, and vault password, then create all the required files (.env, vars.yml, vault.yml).

See the [Trying out examples](sccfm-ansible/README.md#trying-out-examples) section in the Ansible collection README for the full walkthrough including how to run playbooks.
