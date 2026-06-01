# Generated Documentation

The CLI and Ansible references are generated from source metadata:

- CLI docs come from Click `--help` output.
- Ansible docs come from `ansible-doc` output.

Generate local previews with:

```bash
source scripts/activate.sh
generate-cli-docs
generate-ansible-docs
check-doc-links
```

The generated files are written to:

- `docs/cli/`
- `docs/ansible/`

On every merge to `main`, GitHub Actions regenerates those folders and commits any changes
back to `main` before publishing the same generated files to GitHub Pages.
CI checks internal generated links before committing or publishing. External links are
intentionally not checked in CI to avoid release noise from unrelated remote outages.
