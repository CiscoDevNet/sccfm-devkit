# Releasing

Releases are deliberate maintainer operations. Merging or pushing to `main` runs CI but does not
bump a version, create a tag, or publish a package. A maintainer starts the GitHub Actions
**Release** workflow manually and supplies the exact version to publish.

The workflow publishes the Python package first and the matching Ansible collection second. It
builds the wheel, source distribution, and collection tarball once, then promotes those exact
verified files to GitHub Releases, PyPI, and Ansible Galaxy without rebuilding them.

## One-time repository setup

Configure these protected GitHub environments, ideally with required reviewers:

- `release-bot`: `SCCFM_CI_DEPLOY_KEY`, with permission to push the release commit and tag.
- `pypi`: `PYPI_API_TOKEN`, authorized to publish `cisco-sccfm-devkit`. For the first release, the
  token must be allowed to create the project.
- `ansible-galaxy`: `GALAXY_API_KEY`, owned by an account authorized to publish in the `cisco`
  namespace.

Store credentials only as environment secrets. Do not put them in workflow inputs or repository
files. Protect `main`, the release environments, and release tags according to the repository's
maintainer policy.

## Before a release

1. Merge all intended changes and confirm CI passes on the exact `main` commit to release.
2. Confirm the changelogs and documentation describe the intended public release.
3. Choose an unused exact version such as `0.39.0`. Enter it without a leading `v`.
4. Confirm that the version and its `v<version>` tag do not already exist on PyPI, Ansible Galaxy,
   or GitHub Releases.
5. Confirm the PyPI account and Galaxy account still have the required namespace permissions.

Published registry versions are immutable. Never reuse a version for different contents.

## Run the release

1. Open **Actions** in `CiscoDevNet/sccfm-devkit` and select **Release**.
2. Select **Run workflow**, choose the `main` branch, and enter the exact `version`.
3. Review and approve the protected environments as each publication stage is reached.
4. Keep the run open until every job succeeds.

The workflow performs these operations in order:

1. Validates the requested version and release source, synchronizes version metadata, and runs the
   release gates.
2. Builds the wheel, source distribution, and Galaxy tarball once; scans and verifies all three.
3. Creates the release commit and `v<version>` tag, then uploads the three artifacts and their
   SHA-256 manifest to a draft GitHub Release.
4. Downloads and re-verifies the draft-release assets, publishes the wheel and source distribution
   to PyPI, and verifies the published files.
5. Downloads and re-verifies the same collection tarball, publishes it to Ansible Galaxy, and
   waits for Galaxy import validation.
6. Publishes the GitHub Release only after both registries succeed.

## Verify the release

The successful run is the authoritative publication record. Confirm that:

- the GitHub Release is public and contains the wheel, source distribution, collection tarball,
  and `release-manifest.json`;
- PyPI exposes `cisco-sccfm-devkit==<version>`; and
- Ansible Galaxy exposes `cisco.sccfm` at the same version.

For an independent clean-install check:

```bash
RELEASE_VERSION=0.39.0
RELEASE_CHECK_ROOT="$(mktemp -d)"
python3.12 -m venv "${RELEASE_CHECK_ROOT}/venv"
"${RELEASE_CHECK_ROOT}/venv/bin/python" -m pip install \
  "cisco-sccfm-devkit==${RELEASE_VERSION}" \
  "ansible-core>=2.20,<2.22"
"${RELEASE_CHECK_ROOT}/venv/bin/sccfm-cli" --help
"${RELEASE_CHECK_ROOT}/venv/bin/ansible-galaxy" collection install \
  "cisco.sccfm:==${RELEASE_VERSION}" \
  --collections-path "${RELEASE_CHECK_ROOT}/collections"
ANSIBLE_COLLECTIONS_PATH="${RELEASE_CHECK_ROOT}/collections" \
  "${RELEASE_CHECK_ROOT}/venv/bin/ansible-galaxy" collection list cisco.sccfm
```

## Failures and retries

- Use **Re-run failed jobs**. Do not use **Re-run all jobs** after any registry publication may
  have succeeded.
- If PyPI succeeds and Galaxy fails, retry only the failed Galaxy path. It downloads and verifies
  the collection from the draft GitHub Release; it must not rebuild it.
- A draft GitHub Release after a failed run is expected. Do not publish it manually while either
  registry is incomplete or unverified.
- If a checksum, version, tag, or published-file verification fails, stop and investigate. Do not
  replace an artifact, delete a registry release, or bypass a verification gate.
- Before starting a new workflow run after a failure, inspect the tag, draft release, PyPI, and
  Galaxy state. If any registry accepted the version, continue only by promoting the existing
  manifest-bound artifacts.

