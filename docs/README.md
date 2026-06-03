---
layout: page
title: Generated Documentation
---

# Generated Documentation

The CLI and Ansible references are generated from source metadata:

- CLI docs come from Click `--help` output.
- CLI man pages come from Click command metadata via `click-man`.
- Ansible docs come from `ansible-doc` output.

Generate local previews with:

```bash
source scripts/activate.sh
sync-docs-readme
generate-cli-docs
generate-cli-man-docs
generate-ansible-docs
check-doc-links
check-doc-artifacts
```

The generated files are written to:

- `docs/cli/`
- `docs/man/man1/`
- `docs/ansible/`
- `docs/_includes/repository-readme.md` (ignored locally; generated from the root `README.md`)

Pull requests run the Docs workflow, which regenerates all docs, validates internal
generated links, scans generated text artifacts for terminal escape sequences, and builds
the static docs site without publishing it. After CI succeeds on `main`, the Generated
Docs workflow regenerates those folders and commits any changes back to `main`.

The Pages workflow publishes committed docs from `docs/` when `docs/**` changes on
`main`.

External links are intentionally not checked in CI to avoid release noise from unrelated
remote outages.

Manual pages are generated for Unix-style package managers. A package installer can place
`docs/man/man1/*.1` into its normal `man1` directory so `man sccfm-cli` works without
users editing `MANPATH`. Direct `pip` and `pipx` installs do not reliably install system
man pages, especially inside virtual environments.

For local repository installs, run:

```bash
install-cli-man-docs
```

It regenerates the CLI man pages, replaces the installed `sccfm-cli*.1` files in a
user-level man directory, and prints the `MANPATH` export to add if that directory is not
already searched. Windows does not include `man` by default, so Windows users should use
`sccfm-cli --help` or the generated Markdown docs.
