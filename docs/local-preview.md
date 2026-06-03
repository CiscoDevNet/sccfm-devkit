---
layout: page
title: Local Preview
---

[Back to Documentation Home](index.html){:.doc-button}

Generate and validate the local docs from the repository root:

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

To install the generated CLI man pages into a local man directory for testing
`man sccfm-cli`, run `install-cli-man-docs`.

Pull requests run the Docs workflow, which regenerates all docs, validates internal
generated links, scans generated text artifacts for terminal escape sequences, and builds
the static docs site without publishing it.
