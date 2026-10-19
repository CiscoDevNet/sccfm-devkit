#!/usr/bin/env bash

set -euo pipefail

PYTHON_VERSION="3.12.4"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

function ensure_homebrew() {
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required to install pyenv" >&2
    exit 1
  fi
}

function ensure_pyenv() {
  if command -v pyenv >/dev/null 2>&1; then
    return
  fi
  ensure_homebrew
  echo "Installing pyenv via Homebrew"
  brew install pyenv
}

function ensure_python() {
  if pyenv versions --bare | grep -Fx "${PYTHON_VERSION}" >/dev/null; then
    return
  fi
  echo "Installing Python ${PYTHON_VERSION}"
  pyenv install -s "${PYTHON_VERSION}"
}

function create_venv() {
  local poetry_venv python_bin
  python_bin="$(pyenv root)/versions/${PYTHON_VERSION}/bin/python3"
  if [[ ! -x "${python_bin}" ]]; then
    echo "Python ${PYTHON_VERSION} is not available in pyenv" >&2
    exit 1
  fi
  if [[ -d "${VENV_DIR}" ]]; then
    echo "Virtualenv already exists at ${VENV_DIR}"
  else
    "${python_bin}" -m venv "${VENV_DIR}"
  fi
  # shellcheck source=/dev/null
  source "${VENV_DIR}/bin/activate"

  if python -c 'import importlib.metadata; importlib.metadata.version("poetry")' \
      >/dev/null 2>&1; then
    echo "The existing ${VENV_DIR} contains Poetry in the project runtime." >&2
    echo "Remove ${VENV_DIR} and rerun this script to migrate to the isolated setup." >&2
    exit 1
  fi

  python -m pip install --upgrade pip

  poetry_venv="${VENV_DIR}/.poetry"
  if [[ ! -x "${poetry_venv}/bin/poetry" ]]; then
    echo "Installing Poetry in an isolated tooling environment at ${poetry_venv}"
    "${python_bin}" -m venv "${poetry_venv}"
    "${poetry_venv}/bin/python" -m pip install --upgrade pip
    "${poetry_venv}/bin/pip" install poetry
  fi

  POETRY_VIRTUALENVS_IN_PROJECT=1 "${poetry_venv}/bin/poetry" install --with dev
  ln -sfn "../.poetry/bin/poetry" "${VENV_DIR}/bin/poetry"

  if ! python -m pip check; then
    echo "The project environment has incompatible dependencies." >&2
    exit 1
  fi
  if [[ ! -x "${VENV_DIR}/bin/cz" ]]; then
    echo "Commitizen did not install correctly." >&2
    exit 1
  fi
}

function configure_git_alias() {
  if git -C "${PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "${PROJECT_ROOT}" config alias.cz '!./cisco_sccfm_scripts/cz.sh commit'
  else
    echo "Skipping git alias setup (not a git repository)" >&2
  fi
}

function install_pre_commit_hooks() {
  if ! git -C "${PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Skipping pre-commit install (not a git repository)" >&2
    return
  fi
  echo "Installing pre-commit hooks (pre-commit + commit-msg)"
  pre-commit install --hook-type pre-commit --hook-type commit-msg
}

ensure_pyenv
ensure_python
create_venv
configure_git_alias
install_pre_commit_hooks
