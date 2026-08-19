# Releasing

Releases have two separate stages:

1. After CI succeeds for a push to `main`, Commitizen inspects the conventional commits since the
   last release. When a version bump is required, CI infers the next version, creates the release
   commit and `v<version>` tag, builds and verifies the wheel, source distribution, and Ansible
   collection once, and stores those files with their SHA-256 manifest in a **draft** GitHub
   Release. This stage does not publish to PyPI or Ansible Galaxy.
2. When the draft is ready, a maintainer manually runs the GitHub Actions **Release** workflow for
   that existing version. It promotes the exact draft-release assets to PyPI and Ansible Galaxy,
   then makes the GitHub Release public.

Merging does not publish packages. The manual workflow dispatch is the publication gate; it does
not choose or create a new version.

## One-time repository setup

Configure these GitHub Actions repository secrets under **Settings > Secrets and variables >
Actions**:

- `SCCFM_CI_DEPLOY_KEY`, with permission to push the release commit and tag.
- `PYPI_API_TOKEN`, authorized to publish `cisco-sccfm-devkit`. For the first release, the token
  must be allowed to create the project.
- `GALAXY_API_KEY`, owned by an account authorized to publish in the `cisco` namespace.

Store credentials only as repository Actions secrets. Do not put them in workflow inputs or
repository files. Protect `main` and release tags, ensure the release key can perform its narrowly
scoped push, and limit repository write access to maintainers authorized to release. This setup
does not use GitHub environments or per-environment approvals.

## Before merging a release

1. Confirm PR CI passes and the intended conventional commit will produce the correct bump. You
   can preview Commitizen's inference without changing files:

   ```bash
   poetry run cz bump --dry-run --yes --changelog
   ```

2. Confirm the public documentation and changelogs describe the intended release.
3. Prepare the Ansible changelog for the version Commitizen will infer. For the first public
   release only, CI may retarget the checked-in `0.39.0` seed to that inferred version. Do not move
   or replace the seed marker afterward. Before every later release, commit the inferred version
   as the newest entry in `sccfm-ansible/changelogs/changelog.yaml` and the matching
   `v<version>` section in `sccfm-ansible/CHANGELOG.rst`, preserving all published history. The
   YAML entry must have non-empty `changes`, a `fragments` list, and a valid `release_date`.
4. Confirm the inferred version and its `v<version>` tag are unused on PyPI, Ansible Galaxy, and
   GitHub Releases, and confirm both registry accounts still have publishing permission.

Published registry versions are immutable. Never reuse a version for different contents.

## Confirm automatic preparation

After the release change reaches `main` and CI succeeds, confirm that:

- Commitizen created the expected version commit and `v<version>` tag;
- the tag identifies a commit contained in `main`;
- a draft GitHub Release exists for the tag; and
- the draft contains one wheel, one source distribution, one collection tarball, and
  `release-manifest.json`.

Do not edit the tag or replace draft-release assets after preparation.

## Publish the prepared release

1. Open **Actions** in `CiscoDevNet/sccfm-devkit` and select **Release**.
2. Select **Run workflow** on `main` and enter the prepared version without the leading `v`.
3. Keep the run open until every job succeeds.

The workflow validates the existing tag and draft release, downloads and re-verifies its assets,
publishes the wheel and source distribution to PyPI, publishes the same collection tarball to
Ansible Galaxy, waits for registry validation, and finally makes the GitHub Release public. It
does not rebuild or retag the release.

## Verify the release

The successful deployment run is the authoritative publication record. Confirm that:

- the GitHub Release is public and contains the wheel, source distribution, collection tarball,
  and `release-manifest.json`;
- PyPI exposes `cisco-sccfm-devkit==<version>`; and
- Ansible Galaxy exposes `cisco.sccfm` at the same version.

For an independent clean-install check:

```bash
RELEASE_VERSION=X.Y.Z
RELEASE_CHECK_ROOT="$(mktemp -d)"
python3.12 -m venv "${RELEASE_CHECK_ROOT}/venv"
"${RELEASE_CHECK_ROOT}/venv/bin/python" -m pip install \
  "cisco-sccfm-devkit==${RELEASE_VERSION}" \
  "ansible-core>=2.20,<2.22"
"${RELEASE_CHECK_ROOT}/venv/bin/sccfm-cli" --help
"${RELEASE_CHECK_ROOT}/venv/bin/sccfm-cli-interactive" --help
"${RELEASE_CHECK_ROOT}/venv/bin/ansible-galaxy" collection install \
  "cisco.sccfm:==${RELEASE_VERSION}" \
  --collections-path "${RELEASE_CHECK_ROOT}/collections"
ANSIBLE_COLLECTIONS_PATH="${RELEASE_CHECK_ROOT}/collections" \
  "${RELEASE_CHECK_ROOT}/venv/bin/ansible-galaxy" collection list cisco.sccfm
```

## Failures and retries

- If automatic preparation fails after pushing the release commit and tag, use **Re-run failed
  jobs** on that same CI run. The retry accepts only the matching manifest-bound bundle already
  produced by that run and completes the draft Release without rebuilding it.
- A failed deployment leaves the GitHub Release as a draft. Do not publish it manually while
  either registry is incomplete or unverified.
- Re-run the failed deployment jobs or dispatch **Release** again for the same prepared version.
  Every attempt downloads and verifies the manifest-bound draft-release assets; it must not
  rebuild them.
- If PyPI succeeded and Galaxy failed, retry the same version. The workflow must verify the files
  already on PyPI against the manifest before continuing to Galaxy; it must not upload different
  contents under that version.
- If a checksum, version, tag, draft asset, or published-file verification fails, stop and
  investigate. Do not replace an asset, move a tag, delete a registry release, or bypass a gate.
- Before retrying, inspect the tag, draft release, PyPI, and Galaxy. If either registry accepted
  the version, continue only by promoting the existing draft-release assets.
