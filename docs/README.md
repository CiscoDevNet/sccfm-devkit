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

Those folders are ignored by Git. Commit the code metadata that generates the docs, not the generated preview files.

Docs are also generated and published from `main` by GitHub Actions so users can read them without installing the repo locally.
CI checks internal generated links before publishing. External links are intentionally not checked in CI to avoid release noise from unrelated remote outages.
