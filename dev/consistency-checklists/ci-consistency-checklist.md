# ci-consistency-checklist

Use this file as the primary prompt/checklist for an agent reviewing every new PR in CI for consistency drift.

Supporting references:
- `dev/inconsistency-findings/consolidated-inconsistencies.md`
- `dev/consistency-checklists/codex-consistency.md`
- `dev/consistency-checklists/claude-consistency.md`

This file is the operational version. It is intentionally shorter and more enforceable than the deeper audit docs.

## 1. Agent mission

Review the PR for validated consistency drift from both perspectives:
- Code perspective: maintenance cost, drift risk, refactor risk, review complexity.
- User perspective: CLI behavior, Ansible behavior, docs/examples trustworthiness, automation impact, error clarity.

Your job is not to invent new architectural preferences. Your job is to detect when the PR changes one repeated mechanism but fails to keep sibling surfaces aligned.

## 2. Inputs CI should provide

Pass all of the following to the agent:
- This file: `dev/consistency-checklists/ci-consistency-checklist.md`
- PR diff: `git diff --unified=3 BASE...HEAD`
- Changed file list: `git diff --name-only BASE...HEAD`
- Base SHA and head SHA
- The contents of changed files

When possible, also provide nearby sibling files for touched mechanism families.

## 3. Review rules

1. Validate findings directly in the repo and diff. Do not rely on memory or prior reports alone.
2. When one repeated mechanism is touched, inspect the relevant sibling surfaces even if they are not in the diff.
3. Report only real validated inconsistencies, not style opinions unless the repo clearly treats them as a shared contract.
4. Treat filename parity as an audit signal, not proof of missing behavioral coverage.
5. Distinguish between:
   - confirmed mismatch
   - structural inconsistency
   - parity gap
6. Prefer high-signal findings over long inventories.
7. If no validated findings exist, say so explicitly.

## 4. Pass/fail policy

- `FAIL`: the PR introduces or worsens a confirmed mismatch in a shared external contract, user-visible behavior, or documented behavior.
- `WARN`: the PR introduces or worsens structural inconsistency or parity drift, but not a clear external contract break.
- `PASS`: no validated consistency findings.

Blocking families are listed in section 5.
Advisory families are listed in section 6.

## 5. Blocking checklist

If the PR touches one of these areas, check all related siblings and fail the review if the PR introduces or worsens drift.

### A. Region, auth, and environment contract

Check when touching:
- `cisco_sccfm_cli/commands/configure.py`
- `sccfm-ansible/plugins/module_utils/config.py`
- `.env.example`
- `README.md`
- `INSTALL.md`
- Ansible module region docs

Verify:
- One canonical region vocabulary is used everywhere.
- Region casing behavior is aligned across CLI and Ansible.
- `SCCFM_REGION`, `SCCFM_API_TOKEN`, and `SCCFM_CONFIG` semantics remain aligned.
- Docs/examples do not advertise different region names or availability.

Fail if:
- The PR changes region handling in only one surface.
- CLI and Ansible accept different region values or casing after the change.
- Docs/examples become less aligned with actual validation behavior.

### B. Ansible collection module contract

Check when touching:
- any file under `sccfm-ansible/plugins/modules/`
- `sccfm-ansible/plugins/module_utils/`
- `sccfm-ansible/meta/runtime.yml`

Verify:
- New/edited modules are present in `cisco.sccfm.all` when appropriate.
- Modules use `base_argument_spec()` and `create_config(module)` unless there is a clear justified exception.
- SDK failures are converted through `ApiException` -> `SccApiError`.
- `supports_check_mode=True` is declared where the collection contract expects it.
- `module_defaults` examples do not promise behavior the action group does not provide.

Fail if:
- Runtime action-group behavior and docs/examples diverge.
- A module bypasses shared auth/config/error-handling patterns without good reason.
- A module weakens structured failure payloads or check-mode consistency.

### C. CLI JSON output contract

Check when touching:
- any CLI command renderer or `_render_*` method
- `cisco_sccfm_cli/commands/base.py`
- `cisco_sccfm_cli/commands/inventory/devices/rendering.py`

Verify:
- JSON mode uses one consistent machine-readable contract.
- JSON output is not routed through Rich rendering paths that may alter output semantics.
- `json.dumps(...)` kwargs remain aligned across similar commands.

Fail if:
- The PR adds or preserves inconsistent JSON rendering for a touched command family.
- Similar commands in the same family diverge further in JSON behavior.

### D. Async transaction contract

Check when touching:
- `cisco_sccfm_core/services/transaction_service.py`
- async inventory services
- upgrade, onboard, deploy, shun, CLI execution flows
- CLI/Ansible timeout settings

Verify:
- Timeout defaults stay aligned across core, CLI, and Ansible surfaces.
- Polling cadence changes are intentional and named, not ad hoc.
- Terminal state handling remains `DONE` / `ERROR` / `CANCELLED`.
- Submitted transaction summaries and wait behavior remain consistent.

Fail if:
- A touched async flow now uses different timeout semantics without aligning sibling surfaces.
- CLI and Ansible diverge further on transaction behavior.

### E. Public naming, docs, and mirrored paths

Check when touching:
- user-facing CLI command names
- test path/layout for a feature
- docs/examples/README/install content
- shared imports that affect public conventions

Verify:
- CLI names, docs, examples, and tests describe the same feature using the same vocabulary.
- Source and test paths remain grep-friendly and mirror each other cleanly.
- Example filenames and referenced files actually exist.

Fail if:
- The PR introduces new naming drift across source, tests, docs, or examples.
- Public docs become less truthful than code.

### F. Shared option contract

Check when touching:
- any list command
- shared option files
- policy list commands

Verify:
- Shared option factories are used where the repo expects them.
- Pagination behavior remains aligned:
  `--limit`, `--offset`, `-l`, `-o`, defaults, ranges.
- `--format`, `--wait`, `--timeout`, and config options remain aligned with the shared layer.

Fail if:
- A touched command bypasses shared option factories and creates new public drift.

## 6. Advisory checklist

Report as `WARN` when the PR introduces or worsens these, unless it also creates a blocking contract break.

### A. Helper duplication drift

Check when touching one family helper but not its siblings:
- device-target selection helpers
- raw-response helpers
- Ansible `resolve_device_uids_from_query(...)`
- Ansible serializer helpers
- family-specific constants such as entity-type lists

Warn if:
- The PR updates one repeated helper family but leaves sibling implementations inconsistent.

### B. Coverage and discoverability parity

Check when adding or editing:
- Ansible modules
- core services
- new user-facing features

Verify:
- tests, examples, e2e coverage, and docs are reviewed for parity

Warn if:
- A new or heavily changed surface lands with noticeably weaker surrounding parity than its sibling features
- but do not claim behavior is untested solely from filename mismatch

### C. User-facing error wording drift

Check when touching:
- `NotFoundError` messages
- CLI/user-facing error text
- reusable error helpers

Warn if:
- similar failures now use more divergent message templates, punctuation, or identifier wording

### D. Low-signal convention drift

Check opportunistically:
- legacy typing syntax
- frozen vs non-frozen dataclasses
- missing `from __future__ import annotations`
- developer script output style

Warn only if:
- the PR makes the convention drift materially worse in touched files

## 7. Trigger map by changed paths

Use this map to decide which sibling surfaces to inspect beyond the diff.

### If changed path starts with `cisco_sccfm_cli/commands/`

Also inspect as relevant:
- `cisco_sccfm_cli/commands/base.py`
- `cisco_sccfm_cli/commands/shared_options.py`
- sibling command families under the same feature tree
- matching tests under `cisco_sccfm_cli/commands/tests/`
- matching docs/examples if the command is public-facing

### If changed path starts with `cisco_sccfm_core/services/`

Also inspect as relevant:
- sibling services in the same family
- `cisco_sccfm_core/constants.py`
- matching CLI and Ansible entry points that consume the service
- matching tests and parser/model clusters

### If changed path starts with `sccfm-ansible/plugins/modules/`

Also inspect as relevant:
- `sccfm-ansible/plugins/module_utils/config.py`
- `sccfm-ansible/meta/runtime.yml`
- same-family modules
- same-name tests under `plugins/modules/tests/`
- example playbooks under `sccfm-ansible/examples/`

### If changed path is a doc or example

Also inspect as relevant:
- actual command/module/service behavior in code
- referenced filenames and env vars
- public naming consistency with source and tests

## 8. Required agent output format

Return exactly this structure:

```text
VERDICT: PASS|WARN|FAIL

BLOCKING FINDINGS:
- <none> | <finding>

ADVISORY FINDINGS:
- <none> | <finding>

SURFACES CHECKED:
- <paths or mechanism families inspected>

RATIONALE:
- 1-3 short bullets explaining why the verdict is correct from both code and user perspectives.
```

For each finding, use this format:

```text
- [Severity] <short title>
  Files: <comma-separated paths>
  Mechanism family: <shared contract or repeated mechanism>
  Code impact: <one sentence>
  User impact: <one sentence>
  Evidence: <one sentence with concrete mismatch>
  Required fix: <one sentence>
```

Severity values:
- `Blocker`
- `Major`
- `Minor`

## 9. Non-goals

Do not fail a PR for:
- a pure architectural preference not grounded in current repo conventions
- a hypothetical issue you did not verify in code
- filename parity alone without explaining the actual consistency risk
- style differences that do not affect either maintenance risk or user experience

## 10. Pass-through prompt

If CI needs a single prompt block to pass to an agent, use this:

```text
Review this PR for consistency drift using
dev/consistency-checklists/ci-consistency-checklist.md as the governing policy.

You must:
1. Validate findings directly in the repo and diff.
2. Review both code impact and user impact.
3. Check sibling surfaces when a repeated mechanism is touched.
4. Report only validated inconsistencies.
5. Use the exact output format required by the checklist.

Inputs provided:
- PR diff
- changed file list
- changed file contents
- base SHA
- head SHA
- dev/consistency-checklists/ci-consistency-checklist.md
```
