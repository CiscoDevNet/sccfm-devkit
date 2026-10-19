---
layout: page
title: Local Documentation Validation
---

[Back to Documentation Home](index.html){:.doc-button}

Generate and validate the documentation sources from the repository root:

```bash
source cisco_sccfm_scripts/activate.sh
sync-docs-readme
generate-cli-docs
generate-cli-man-docs
generate-ansible-docs
check-doc-links
check-doc-links --docs-root sccfm-ansible
check-doc-artifacts
```

The generated files are written to:

- `docs/cli/`
- `docs/man/man1/`
- `docs/ansible/`

To install the generated CLI man pages into a local man directory for testing
`man sccfm-cli`, run `install-cli-man-docs`.

This repository does not pin a local Ruby/Jekyll toolchain or provide a supported local Pages
server. Open the generated Markdown directly for a source preview. The Docs workflow performs the
authoritative rendered-site build with GitHub's Pages builder.

Pull requests run the Docs workflow, which regenerates all docs, validates internal
generated links, scans generated text artifacts for terminal escape sequences, and builds
the static docs site without publishing it.
