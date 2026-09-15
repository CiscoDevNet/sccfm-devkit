# SCCFM agent harness CLI reference

Every flag accepted by `poetry run sccfm-agent-harness`, and when to reach for it.
See [README.md](README.md) for what the harness evaluates, the report format, and
how Claude provider credentials are isolated.

The CLI has three subcommands: `validate`, `run`, and `dashboard`. Only `run`
invokes a model.

## `run`

### Selecting what executes

| Flag | Default | When to use |
|---|---|---|
| `--agent {codex,claude}` | `codex` | Pick the model provider. Claude works with Bedrock, Vertex, Foundry, and API-key logins from environment variables; it runs a credential-isolation preflight before the first fixture. |
| `--mode {explicit-skill,installed-plugin}` | `explicit-skill` | `explicit-skill` isolates instruction quality: user configuration is off and the session is told which `SKILL.md` to read. `installed-plugin` exercises packaging, skill discovery, and hooks. |
| `--fixture ID` | every matching fixture | Repeatable. Use it while iterating on one skill. Unknown ids fail fast. |
| `--tier {required,aspirational,all}` | `required` | `required` is the merge gate. `aspirational` is stretch behavior that should not block merges. `all` runs both. |
| `--fixtures PATH` | `agent-harness/fixtures` | Only to point at a fixture set outside this checkout. |
| `--samples N` | `1` | Measures non-determinism. One model call per fixture per sample. |
| `--model NAME` | the provider default | Pin it in CI so baseline changes are attributable to a known model. |

`--fixture`, `--tier`, and `--mode` intersect. A fixture that does not declare the
selected mode is skipped, and a selection that matches nothing fails with
`no fixtures matched the selection` rather than reporting a vacuous pass.

Sample-count guidance: use one to three for a pull-request gate, 10–20 for
scheduled critical-fixture runs, and 35 clean valid samples when you need a 95%
lower bound near 90%. Raise it on targeted fixtures instead of multiplying the
whole suite.

Model naming is provider-specific. Bedrock model ids carry a region prefix, so an
`eu-west-1` profile needs `eu.anthropic.claude-sonnet-5` rather than the `us.`
form.

### Controlling the run

| Flag | Default | When to use |
|---|---|---|
| `--dry-run` | off | Prints the exact agent invocation per fixture and makes no model call. Use it to inspect flags after changing command construction. It also skips the Claude preflight. |
| `--timeout SECONDS` | `300` | Raise it for Ansible fixtures, which run many commands; 420 is comfortable. The same value bounds the Claude credential-isolation preflight. Must be at least 1. |
| `--runtime-retries N` | `1` | Retries provider exits and timeouts only. Assertion, safety, and harness-integrity failures are never retried. Recovered samples retain the prior runtime error and attempt count in `results.json`. |
| `--output DIR` | `agent-harness/results/<UTC timestamp>` | Point reports at a specific directory, for example a CI artifact path. |
| `--strict-quality` | off | Promotes quality-only failures into the process exit gate. Use it when deliberately improving answer quality; leave it off for normal gating, where quality failures are warnings. |

### Baselines

| Flag | When to use |
|---|---|
| `--write-baseline PATH` | Snapshot a reviewed run as the reference. Do it deliberately, with several samples, after reading the results. |
| `--compare-baseline PATH` | Fail on pass-rate regressions against that snapshot. This is the CI gate. |

`--compare-baseline` compares observed valid-sample pass rates; it does not gate on
Wilson confidence bounds. Both baseline operations require `--model`. Reports
record a comparison fingerprint containing agent, exact agent version, model,
mode, selected-fixture digest, and plugin-source digest. Comparison refuses a
baseline with a different or missing fingerprint. A Codex baseline says nothing
about a Claude run.

### Codex-only flags

| Flag | When to use |
|---|---|
| `--refresh-installed-plugin` | Requires `--mode installed-plugin` and `--agent codex`. Codex hashes the checkout against the installed plugin cache and fails on a stale one; this adds a local cachebuster and reinstalls from the existing local marketplace. Claude rejects the flag because it loads a staged copy of the checkout directly with `--plugin-dir`. |
| `--bypass-hook-trust` | Skips Codex hook trust. Keep it off for normal installed-plugin runs, because hook trust is part of the installed experience. Use it only in a separately isolated diagnostic job. Claude rejects the flag. |

## `validate`

```bash
poetry run sccfm-agent-harness validate [--fixtures PATH]
```

Checks fixture schemas, the stub dispatcher, every skill file a fixture references,
and the plugin manifest. No model call and no network. Run it before a real run and
as a cheap CI pre-gate.

## `dashboard`

```bash
poetry run sccfm-agent-harness dashboard RESULTS.json [--fixtures PATH] [--output PATH]
```

Re-renders the HTML dashboard from an existing JSON report without spending model
calls. Use it after changing the dashboard template, or to review an older run.
`--output` defaults to the JSON path with an `.html` suffix. `--fixtures` supplies
the fixture metadata used to enrich reports written by an older harness version.

## Typical invocations

Fast static pre-check:

```bash
poetry run sccfm-agent-harness validate
```

Iterating on one skill with Claude:

```bash
poetry run sccfm-agent-harness run \
  --agent claude \
  --mode explicit-skill \
  --fixture cli-readonly-list
```

Pull-request gate:

```bash
poetry run sccfm-agent-harness run \
  --agent claude \
  --mode explicit-skill \
  --tier required \
  --samples 3 \
  --model eu.anthropic.claude-sonnet-5 \
  --compare-baseline agent-harness/baselines/explicit-skill-claude.json
```

Reliability measurement on one critical fixture:

```bash
poetry run sccfm-agent-harness run \
  --agent claude \
  --mode explicit-skill \
  --fixture cli-mutation-confirmation \
  --samples 20 \
  --timeout 420
```

Inspecting an invocation without calling a model:

```bash
poetry run sccfm-agent-harness run --agent claude --dry-run
```

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Every selected sample passed the configured gate. |
| `1` | Sample failures or baseline regressions. |
| `2` | Usage or setup error, including an unknown fixture id, an empty selection, a stale Codex plugin, or a failed Claude credential-isolation preflight. Setup errors abort before any fixture runs. |
