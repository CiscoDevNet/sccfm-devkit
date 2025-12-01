# Installation

Follow these steps to install the `sccfm` CLI from a released wheel and enable shell completion.

## Prerequisites

- Python 3.12 or later available on your `PATH`
  - You can do this by running `python --version` and checking the version you've got installed.
- `pip` installed for that Python (e.g., `python3.12 -m pip`).


### Install Python 3.12 using Pyenv

```bash
brew install pyenv
pyenv install -s 3.12
pyenv global 3.12
```

## Download the wheel

1. Navigate to the [GitHub Releases](https://github.com/cisco-lockhart/sccfm-devkit/releases) page for this project.
2. Download the latest wheel asset named like `sccfm-<version>-py3-none-any.whl` to your local machine.

## Install with pip

```bash
pip install /path/to/sccfm-<version>-py3-none-any.whl
```

Replace the path with where you saved the wheel. You can also install into a virtual environment if desired.

## Enable shell completion

Add one of the following lines to your shell startup file, then reload your shell (`source ~/.bashrc`, `source ~/.zshrc`, etc.).

- **bash**

  ```bash
  eval "$(_SCCFM_COMPLETE=bash_source sccfm)"
  ```

- **zsh**

  ```bash
  eval "$(_SCCFM_COMPLETE=zsh_source sccfm-cli)"
  autoload -U compinit && compinit
  ```

- **fish**

  ```fish
  eval (env _SCCFM_COMPLETE=fish_source sccfm)
  ```

After sourcing, tab completion will work for all `sccfm` commands and options.
