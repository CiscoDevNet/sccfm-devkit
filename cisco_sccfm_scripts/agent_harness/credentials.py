# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Keep Claude provider credentials in the parent process only.

Claude Code authenticates the parent session from the environment when a user
selects Bedrock, Vertex, Foundry, or an API key. Passing those variables to the
evaluated session used to expose them to its Bash tool, so the harness stripped
them and refused to run. ``CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`` removes them from
Bash commands, hooks, and stdio MCP servers instead, which keeps the parent
authenticated while the evaluated commands stay credential free.

Environment scrubbing does not protect credential *files*. The evaluated session
can still read an absolute path such as ``~/.aws/credentials``, so the harness
also denies those paths and reports any command that references them.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

SCRUB_VARIABLE = "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"
CREDENTIAL_NAMES_VARIABLE = "SCCFM_HARNESS_CREDENTIAL_NAMES"

# Non-secret provider selection and model routing the parent session needs.
PROVIDER_VARIABLES = (
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "CLOUD_ML_REGION",
    "GOOGLE_CLOUD_PROJECT",
)

# Secrets the parent session needs and no subprocess may ever observe.
CREDENTIAL_VARIABLES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
    "AWS_BEARER_TOKEN_BEDROCK",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
)

# Codex authenticates from its own CODEX_HOME, so it never needs these in the
# environment; the harness strips them entirely rather than scrubbing them per
# subprocess the way it does for Claude's provider variables.
CODEX_CREDENTIAL_VARIABLES = ("OPENAI_API_KEY",)

# Host credential stores the evaluated session must not read by absolute path.
CREDENTIAL_DIRECTORIES = (
    ".aws",
    ".claude",
    ".config/anthropic",
    ".config/gcloud",
    ".azure",
    ".ssh",
    ".docker",
    ".kube",
)
CREDENTIAL_FILES = (
    ".netrc",
    ".git-credentials",
)

_PROBE_SCRIPT = """#!/bin/sh
# Records which credential variables remain visible to a Claude subprocess.
# Writes variable names only, never values.
report="$SCCFM_HARNESS_PROBE_REPORT"
: > "$report"
for name in $SCCFM_HARNESS_CREDENTIAL_NAMES; do
  eval "present=\\${$name+visible}"
  if [ -n "$present" ]; then
    printf 'visible %s\\n' "$name" >> "$report"
  fi
done
printf 'probe-complete\\n' >> "$report"
exit 0
"""


def provider_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return the provider and credential variables the parent session needs."""

    environment = source if source is not None else dict(os.environ)
    return {
        name: environment[name]
        for name in (*PROVIDER_VARIABLES, *CREDENTIAL_VARIABLES)
        if name in environment
    }


def claude_provider_environment(source: dict[str, str]) -> dict[str, str]:
    """Return Claude's provider variables with any Bedrock AWS profile pre-resolved.

    The evaluated session runs with a disposable ``HOME``, so a profile-based login
    (``credential_process``, SSO, assume-role) cannot find ``~/.aws/config`` and
    Claude waits on a credential chain that never resolves. The parent process
    still sees the real home, so it resolves the profile into short-lived keys,
    which ``CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`` removes from every subprocess.
    """

    environment = provider_environment(source)
    profile = environment.get("AWS_PROFILE")
    if not source.get("CLAUDE_CODE_USE_BEDROCK") or not profile:
        return environment
    if "AWS_ACCESS_KEY_ID" in environment:
        return environment
    del environment["AWS_PROFILE"]
    environment.update(_resolved_aws_profile(profile, environment.get("AWS_REGION")))
    return environment


def _resolved_aws_profile(profile: str, region: str | None) -> dict[str, str]:
    import boto3

    try:
        session = boto3.Session(profile_name=profile)
        credentials = session.get_credentials()
        frozen = credentials.get_frozen_credentials() if credentials is not None else None
    except Exception as error:
        raise ValueError(
            f"could not resolve AWS profile {profile!r} for Claude on Bedrock: "
            f"{redact(str(error))[-300:]}"
        ) from None
    if frozen is None:
        raise ValueError(f"AWS profile {profile!r} returned no credentials for Claude on Bedrock")
    resolved = {
        "AWS_ACCESS_KEY_ID": frozen.access_key,
        "AWS_SECRET_ACCESS_KEY": frozen.secret_key,
    }
    if frozen.token:
        resolved["AWS_SESSION_TOKEN"] = frozen.token
    resolved_region = region or session.region_name
    if resolved_region:
        resolved["AWS_REGION"] = resolved_region
    return resolved


def preserved_credential_names(source: dict[str, str] | None = None) -> tuple[str, ...]:
    """Return the credential variables actually present in the parent process."""

    environment = source if source is not None else dict(os.environ)
    return tuple(name for name in CREDENTIAL_VARIABLES if name in environment)


def visible_credentials(environment: dict[str, str]) -> list[str]:
    """Return credential variable names still readable in an environment."""

    return [name for name in CREDENTIAL_VARIABLES if name in environment]


def redact(text: str, source: dict[str, str] | None = None) -> str:
    """Replace any preserved credential value in diagnostic text."""

    environment = source if source is not None else dict(os.environ)
    for name in CREDENTIAL_VARIABLES:
        value = environment.get(name)
        if value and len(value) > 3:
            text = text.replace(value, f"[redacted {name}]")
    return text


def credential_paths(home: Path) -> tuple[str, ...]:
    """Return absolute host credential stores that must stay unreadable."""

    return tuple(str(home / entry) for entry in (*CREDENTIAL_DIRECTORIES, *CREDENTIAL_FILES))


def isolation_settings(home: Path, writable: tuple[Path, ...] = ()) -> dict[str, object]:
    """Build Claude settings that keep host credential stores unreadable.

    Two layers cover the two ways the evaluated session could reach a credential
    file: ``permissions.deny`` refuses Read tool calls, and the OS sandbox refuses
    the same paths to Bash subprocesses, which permission rules cannot express.
    Absolute permission paths require the ``//`` prefix; sandbox paths do not.

    Both sandbox defaults are permissive, so the restrictive value of each is
    stated explicitly rather than inherited: ``failIfUnavailable`` aborts instead
    of running unconfined where the platform cannot start a sandbox, and
    ``allowUnsandboxedCommands`` makes the ``dangerouslyDisableSandbox`` request
    parameter inert instead of relying on ``--restricted`` to reject it.

    ``writable`` must list only the paths the run genuinely writes. Everything
    else, including the command doubles and this settings file, stays read-only
    because the sandbox permits writes only inside the paths named here.
    """

    directories = tuple(str(home / entry) for entry in CREDENTIAL_DIRECTORIES)
    files = tuple(str(home / entry) for entry in CREDENTIAL_FILES)
    return {
        "permissions": {
            "deny": [
                *(f"Read(/{path}/**)" for path in directories),
                *(f"Read(/{path})" for path in files),
            ],
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "denyRead": [*(f"{path}/**" for path in directories), *files],
                "allowWrite": [str(path) for path in writable],
            },
        },
    }


def install_probe(
    directory: Path,
    credential_names: tuple[str, ...],
    base: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    """Install a SessionStart hook that records subprocess credential visibility.

    Hooks run in the same scrubbed environment as the Bash tool, so the hook
    fires deterministically regardless of how the model chooses to respond.
    """

    probe = directory / "credential-probe.sh"
    report = directory / "credential-probe.txt"
    probe.write_text(_PROBE_SCRIPT, encoding="utf-8")
    probe.chmod(0o755)
    settings = directory / "probe-settings.json"
    command = (
        f"SCCFM_HARNESS_PROBE_REPORT={shlex.quote(str(report))} "
        f"SCCFM_HARNESS_CREDENTIAL_NAMES={shlex.quote(' '.join(credential_names))} "
        f"{shlex.quote(str(probe))}"
    )
    payload = dict(base or {})
    payload["hooks"] = {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}
    settings.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return settings, report


def read_probe(report: Path) -> tuple[bool, list[str]]:
    """Return whether the probe completed and which credentials stayed visible."""

    if not report.exists():
        return False, []
    completed = False
    visible: list[str] = []
    for line in report.read_text(encoding="utf-8").splitlines():
        if line.strip() == "probe-complete":
            completed = True
        elif line.startswith("visible "):
            visible.append(line.split(" ", 1)[1].strip())
    return completed, visible
