# Generated Documentation

The CLI and Ansible references are generated from source metadata:

- CLI docs come from Click `--help` output.
- CLI man pages come from Click command metadata via `click-man`.
- Ansible docs come from `ansible-doc` output.

Generate local previews with:

```bash
source scripts/activate.sh
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

Pull requests run the Docs workflow, which regenerates all docs, validates internal
generated links, scans generated text artifacts for terminal escape sequences, and builds
the GitHub Pages site without publishing it. After CI succeeds on `main`, the Generated
Docs workflow regenerates those folders and commits any changes back to `main`; the Pages
workflow publishes committed docs when `docs/**` changes.

External links are intentionally not checked in CI to avoid release noise from unrelated
remote outages.

Manual pages are generated for Unix-style package managers. A Homebrew, Debian, or RPM
package should install `docs/man/man1/*.1` into its normal `man1` directory so `man
sccfm-cli` works without users editing `MANPATH`. Direct `pip` and `pipx` installs do
not reliably install system man pages, especially inside virtual environments. Windows
does not include `man` by default, so Windows users should use `sccfm-cli --help` or the
published web docs.
