#!/usr/bin/env bash
# CI environment setup for Linux Jenkins agents.
#
# Uses pyenv when the agent can install build dependencies. On unprivileged
# container agents it falls back to uv's prebuilt, user-space Python.
#
# For local macOS development, use setup_environment.sh instead.

set -euo pipefail

PYTHON_VERSION="3.12.4"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_BIN=""

can_run_as_root() {
  [[ "$(id -u)" -eq 0 ]] || command -v sudo >/dev/null 2>&1
}

run_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi
  echo "No root or sudo access is available."
  return 127
}

install_system_packages() {
  if ! can_run_as_root; then
    echo "Cannot install build dependencies; using a prebuilt Python instead."
    return 1
  fi

  echo "Installing system build dependencies..."
  if command -v yum >/dev/null 2>&1; then
    run_as_root yum groupinstall -y 'Development Tools' || return 1
    run_as_root yum install -y \
      bzip2-devel \
      libffi-devel \
      openssl11-devel \
      readline-devel \
      sqlite-devel \
      xz-devel \
      zlib-devel \
      git || return 1
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    run_as_root apt-get update || return 1
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      build-essential \
      curl \
      git \
      libbz2-dev \
      libffi-dev \
      liblzma-dev \
      libncursesw5-dev \
      libreadline-dev \
      libsqlite3-dev \
      libssl-dev \
      tk-dev \
      uuid-dev \
      xz-utils \
      zlib1g-dev || return 1
    return
  fi

  echo "No supported package manager found; using a prebuilt Python instead."
  return 1
}

setup_pyenv() {
  export PYENV_ROOT="${HOME}/.pyenv"
  export PATH="${PYENV_ROOT}/bin:${PATH}"

  if [[ ! -x "${PYENV_ROOT}/bin/pyenv" ]]; then
    echo "Installing pyenv..."
    curl -fsSL https://pyenv.run | bash
  fi

  eval "$(pyenv init -)"
}

build_python() {
  if pyenv versions --bare 2>/dev/null | grep -qx "${PYTHON_VERSION}"; then
    echo "Python ${PYTHON_VERSION} already installed."
    return
  fi

  # Clean up partial installs from a previous run.
  local versions_dir
  versions_dir="$(pyenv root)/versions/${PYTHON_VERSION}"
  if [[ -d "${versions_dir}" ]]; then
    echo "Cleaning partial install at ${versions_dir}"
    rm -rf "${versions_dir}"
  fi

  echo "Building Python ${PYTHON_VERSION}..."

  # Amazon Linux 2 ships OpenSSL 1.0.2 by default but Python 3.12+
  # requires >= 1.1.1.  The openssl11-devel package puts headers in
  # /usr/include/openssl11 and libs in /usr/lib64/openssl11.
  local build_cppflags="" build_ldflags=""
  if [[ -d /usr/include/openssl11 ]]; then
    build_cppflags="-I/usr/include/openssl11"
  fi
  if [[ -d /usr/lib64/openssl11 ]]; then
    build_ldflags="-L/usr/lib64/openssl11"
  fi

  if ! CPPFLAGS="${build_cppflags}" LDFLAGS="${build_ldflags}" \
       pyenv install "${PYTHON_VERSION}"; then
    echo "Python ${PYTHON_VERSION} build failed." >&2
    local log
    log="$(ls -t /tmp/python-build.*.log 2>/dev/null | head -1)"
    if [[ -n "${log}" && -f "${log}" ]]; then
      echo "=== Last 40 lines of build log ===" >&2
      tail -40 "${log}" >&2
    fi
    exit 1
  fi
}

setup_pyenv_python() {
  setup_pyenv
  build_python
  PYTHON_BIN="$(pyenv root)/versions/${PYTHON_VERSION}/bin/python3"
}

setup_prebuilt_python() {
  local uv_bin_dir="${HOME}/.local/bin"
  export PATH="${uv_bin_dir}:${PATH}"

  if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv for user-space Python management..."
    curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh \
      | env UV_UNMANAGED_INSTALL="${uv_bin_dir}" sh
  fi

  echo "Installing prebuilt Python ${PYTHON_VERSION}..."
  uv python install "${PYTHON_VERSION}"
  PYTHON_BIN="$(uv python find "${PYTHON_VERSION}")"
}

prepare_python() {
  if install_system_packages; then
    setup_pyenv_python
  else
    setup_prebuilt_python
  fi
}

create_venv() {
  if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
    echo "Python ${PYTHON_VERSION} binary not found." >&2
    exit 1
  fi

  if [[ ! -d "${VENV_DIR}" ]]; then
    echo "Creating virtualenv at ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi

  # shellcheck source=/dev/null
  source "${VENV_DIR}/bin/activate"
  python -m pip install --upgrade pip

  if ! command -v poetry >/dev/null 2>&1; then
    pip install poetry
  fi

  POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --with dev,build

  if [[ ! -x "${VENV_DIR}/bin/cz" ]]; then
    echo "Commitizen did not install correctly." >&2
    exit 1
  fi
}

configure_git_alias() {
  if git -C "${PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "${PROJECT_ROOT}" config alias.cz '!./scripts/cz.sh commit'
  fi
}

prepare_python
create_venv
configure_git_alias

echo "CI environment ready."
