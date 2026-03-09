#!/usr/bin/env bash

set -euo pipefail

PYTHON_VERSION="3.12.4"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

function ensure_homebrew() {
  if command -v brew >/dev/null 2>&1; then
    return
  fi
  echo "Installing Homebrew"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  elif [[ -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  else
    echo "Homebrew installation failed" >&2
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

function ensure_python_build_deps() {
  # pyenv compiles Python from source.  python-build auto-detects only a
  # handful of Homebrew packages (readline, ncurses, zlib, tcl-tk,
  # openssl).  Others — notably xz — are silently missed.
  #
  # CPython 3.12+ uses pkg-config (PKG_CHECK_MODULES) to locate
  # libraries such as liblzma.  Without pkg-config the fallback detection
  # often fails to set the module-specific compiler/linker flags
  # (LIBLZMA_CFLAGS / LIBLZMA_LIBS), so the _lzma extension silently
  # fails to compile even though generic CPPFLAGS/LDFLAGS are present.
  echo "Installing Python build dependencies via Homebrew"
  brew install bzip2 libffi openssl@3 pkg-config readline sqlite3 xz zlib tcl-tk

  # Many of these formulae are keg-only (bzip2, libffi, openssl@3,
  # readline, zlib) — they are not symlinked into the main Homebrew
  # prefix by default, so neither pkg-config nor the compiler can find
  # them without explicit paths.  Force-linking puts the headers, libs,
  # and .pc files at $(brew --prefix)/{include,lib,lib/pkgconfig} where
  # the Linuxbrew compiler toolchain and pkg-config search by default.
  local pkg
  for pkg in bzip2 libffi openssl@3 readline sqlite3 xz zlib; do
    brew link --force "${pkg}" 2>/dev/null || true
  done
}

function ensure_python() {
  if pyenv versions --bare | grep -qx "${PYTHON_VERSION}"; then
    return
  fi
  ensure_python_build_deps

  # Remove leftovers from a previous failed build so pyenv retries.
  local versions_dir
  versions_dir="$(pyenv root)/versions/${PYTHON_VERSION}"
  if [[ -d "${versions_dir}" ]]; then
    echo "Cleaning partial install at ${versions_dir}"
    rm -rf "${versions_dir}"
  fi

  # Build per-package compiler/linker/pkg-config flags as a safety net
  # on top of the force-linked packages above.
  local flags_ld="" flags_cpp="" flags_pkg=""
  local pkg prefix
  for pkg in bzip2 libffi openssl@3 readline sqlite3 xz zlib; do
    prefix="$(brew --prefix "${pkg}" 2>/dev/null)" || continue
    [[ -d "${prefix}/lib" ]]            && flags_ld="${flags_ld} -L${prefix}/lib"
    [[ -d "${prefix}/include" ]]        && flags_cpp="${flags_cpp} -I${prefix}/include"
    [[ -d "${prefix}/lib/pkgconfig" ]]  && flags_pkg="${flags_pkg:+${flags_pkg}:}${prefix}/lib/pkgconfig"
  done

  local openssl_prefix
  openssl_prefix="$(brew --prefix openssl@3 2>/dev/null)" \
    || openssl_prefix="$(brew --prefix openssl 2>/dev/null)" \
    || openssl_prefix=""

  local configure_opts=""
  if [[ -n "${openssl_prefix}" ]]; then
    configure_opts="--with-openssl=${openssl_prefix} --with-openssl-rpath=auto"
  fi

  echo "Installing Python ${PYTHON_VERSION}"
  LDFLAGS="${flags_ld}" \
  CPPFLAGS="${flags_cpp}" \
  PKG_CONFIG_PATH="${flags_pkg}" \
  PYTHON_CONFIGURE_OPTS="${configure_opts}" \
    pyenv install -v "${PYTHON_VERSION}"

  # Verify the build actually produced a working interpreter.
  local python_bin
  python_bin="$(pyenv root)/versions/${PYTHON_VERSION}/bin/python3"
  if [[ ! -x "${python_bin}" ]]; then
    echo "Python ${PYTHON_VERSION} failed to build. Check the pyenv build log above." >&2
    exit 1
  fi
}

function create_venv() {
  local python_bin
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

function configure_git_alias() {
  if git -C "${PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "${PROJECT_ROOT}" config alias.cz '!./scripts/cz.sh commit'
  else
    echo "Skipping git alias setup (not a git repository)" >&2
  fi
}

ensure_homebrew
ensure_pyenv
ensure_python
create_venv
configure_git_alias
