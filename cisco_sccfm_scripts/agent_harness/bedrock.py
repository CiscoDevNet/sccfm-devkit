# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Run one SCCFM harness session through Amazon Bedrock tool use."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .credentials import redact
from .models import CommandRecord, Transcript

DEFAULT_TOOL_IMAGE = "python:3.12-slim"
MAX_TOOL_ROUNDS = 40
MAX_TOOL_OUTPUT = 64 * 1024
CONTAINER_TOOL_ROOT = Path("/opt/sccfm-agent-harness")
CONTAINER_BINARY_DIRECTORY = CONTAINER_TOOL_ROOT / "bin"
CONTAINER_EVENT_LOG = CONTAINER_TOOL_ROOT / "events.jsonl"


class UnservedToolRequest(ValueError):
    """A tool request the harness cannot execute but can answer with an error."""

    def __init__(self, tool_name: str, message: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name


@dataclass(frozen=True)
class BedrockExecution:
    """Provider execution result consumed by the common harness scorer."""

    transcript: Transcript
    exit_code: int
    stderr: str = ""


def provider_version() -> str:
    """Return an inspectable provider version for report fingerprints."""

    try:
        version = importlib.metadata.version("boto3")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return f"amazon-bedrock/boto3-{version}"


def validate_access(model: str, region: str, timeout_seconds: int) -> None:
    """Prove the ambient AWS identity can invoke the selected Bedrock model."""

    try:
        client = _client(region, timeout_seconds)
        client.converse(
            modelId=model,
            messages=[{"role": "user", "content": [{"text": "Reply with ready."}]}],
            inferenceConfig={"maxTokens": 16, "temperature": 0},
        )
    except Exception as error:
        diagnostic = redact(str(error))
        raise ValueError(
            "Amazon Bedrock preflight failed. Confirm that the Jenkins agent's ambient AWS "
            f"identity can invoke {model!r} in {region!r}: {diagnostic[-500:]}"
        ) from None


def run_session(
    prompt: str,
    model: str,
    region: str,
    timeout_seconds: int,
    workspace: Path,
    binary_directory: Path,
    event_log: Path,
    tool_environment: dict[str, str],
    tool_image: str = DEFAULT_TOOL_IMAGE,
    system_prompt: str | None = None,
) -> BedrockExecution:
    """Run a Bedrock Converse loop with one isolated POSIX-shell tool."""

    transcript = Transcript()
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": [{"text": prompt}]},
    ]
    deadline = time.monotonic() + timeout_seconds

    try:
        for _round in range(MAX_TOOL_ROUNDS + 1):
            client = _client(region, _remaining_seconds(deadline))
            request: dict[str, Any] = {
                "modelId": model,
                "messages": messages,
                "toolConfig": {"tools": [_bash_tool()]},
                "inferenceConfig": {"maxTokens": 4096, "temperature": 0},
            }
            if system_prompt:
                request["system"] = [{"text": system_prompt}]
            response = client.converse(
                **request,
            )
            message = _assistant_message(response)
            messages.append(message)
            _record_request_id(response, transcript)
            text = _message_text(message)
            tool_uses = _tool_uses(message)
            if not tool_uses:
                transcript.response = text
                stop_reason = response.get("stopReason", "unknown")
                if not transcript.response or stop_reason not in {"end_turn", "stop_sequence"}:
                    return BedrockExecution(
                        transcript,
                        1,
                        f"Bedrock stopped with {stop_reason} before completing its response",
                    )
                return BedrockExecution(transcript, 0)
            if _round == MAX_TOOL_ROUNDS:
                return BedrockExecution(
                    transcript,
                    1,
                    f"Bedrock exceeded the {MAX_TOOL_ROUNDS}-round tool limit",
                )
            tool_results = []
            for tool_use in tool_uses:
                try:
                    command = _tool_command(tool_use)
                except UnservedToolRequest as error:
                    # A model that reaches for a tool this lane does not serve can
                    # still complete the task with the shell, so the request is
                    # answered with an error result the way a failed command is.
                    # Ending the session instead would discard a whole sample over
                    # one recoverable turn.
                    transcript.unserved_tool_requests.append(error.tool_name)
                    tool_results.append(_tool_error_result(tool_use, str(error)))
                    continue
                record = _run_bash(
                    command,
                    workspace,
                    binary_directory,
                    event_log,
                    tool_environment,
                    tool_image,
                    _remaining_seconds(deadline),
                )
                transcript.commands.append(record.command)
                transcript.command_outputs.append(record.output)
                transcript.command_records.append(record)
                tool_results.append(_tool_result(tool_use, record))
            messages.append({"role": "user", "content": tool_results})
    except subprocess.TimeoutExpired:
        return BedrockExecution(
            transcript,
            124,
            f"bedrock timed out after {timeout_seconds} seconds",
        )
    except Exception as error:
        return BedrockExecution(transcript, 1, redact(str(error)))

    return BedrockExecution(transcript, 1, "Bedrock session ended unexpectedly")


def _client(region: str, timeout_seconds: int) -> Any:
    import boto3
    from botocore.config import Config

    timeout = max(1, timeout_seconds)
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            connect_timeout=min(10, timeout),
            read_timeout=timeout,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def _bash_tool() -> dict[str, Any]:
    return {
        "toolSpec": {
            "name": "Bash",
            "description": (
                "Run one POSIX shell command in the disposable evaluation workspace. "
                "Network access and provider credentials are unavailable."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The POSIX shell command to execute.",
                        }
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                }
            },
        }
    }


def _assistant_message(response: dict[str, Any]) -> dict[str, Any]:
    output = response.get("output")
    message = output.get("message") if isinstance(output, dict) else None
    if not isinstance(message, dict):
        raise ValueError("Bedrock response did not contain output.message")
    return message


def _record_request_id(response: dict[str, Any], transcript: Transcript) -> None:
    metadata = response.get("ResponseMetadata")
    request_id = metadata.get("RequestId") if isinstance(metadata, dict) else None
    if transcript.thread_id is None and isinstance(request_id, str):
        transcript.thread_id = request_id


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )


def _tool_uses(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        block["toolUse"]
        for block in content
        if isinstance(block, dict) and isinstance(block.get("toolUse"), dict)
    ]


def _tool_command(tool_use: dict[str, Any]) -> str:
    name = tool_use.get("name")
    if name != "Bash":
        raise UnservedToolRequest(
            name if isinstance(name, str) else repr(name),
            f"The tool {name!r} is not available in this evaluation. Bash is the only "
            "tool: read files with cat, grep, or ls, and create them with a quoted "
            "heredoc such as cat > playbook.yml <<'EOF'.",
        )
    tool_input = tool_use.get("input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        raise UnservedToolRequest(
            "Bash",
            "The Bash tool request did not contain a command. Put the POSIX shell "
            "command to run in the 'command' field.",
        )
    return command


def _tool_use_id(tool_use: dict[str, Any]) -> str:
    tool_use_id = tool_use.get("toolUseId")
    if not isinstance(tool_use_id, str):
        raise ValueError("Bedrock tool request did not contain toolUseId")
    return tool_use_id


def _tool_error_result(tool_use: dict[str, Any], message: str) -> dict[str, Any]:
    """Return the error result that lets a model retry an unserved tool request."""

    return {
        "toolResult": {
            "toolUseId": _tool_use_id(tool_use),
            "content": [{"text": message}],
            "status": "error",
        }
    }


def _tool_result(tool_use: dict[str, Any], record: CommandRecord) -> dict[str, Any]:
    tool_use_id = _tool_use_id(tool_use)
    output = record.output[-MAX_TOOL_OUTPUT:]
    text = f"Exit code: {record.exit_code}\n{output}".rstrip()
    return {
        "toolResult": {
            "toolUseId": tool_use_id,
            "content": [{"text": text}],
            "status": "success" if record.exit_code == 0 else "error",
        }
    }


def _run_bash(
    command: str,
    workspace: Path,
    binary_directory: Path,
    event_log: Path,
    environment: dict[str, str],
    image: str,
    timeout_seconds: int,
) -> CommandRecord:
    container_environment = _container_environment(environment)
    container_name = f"sccfm-agent-harness-{uuid.uuid4().hex}"
    docker_command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit",
        "256",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--workdir",
        str(workspace),
        "--volume",
        f"{workspace}:{workspace}:rw,Z",
        "--volume",
        f"{binary_directory}:{CONTAINER_BINARY_DIRECTORY}:ro,Z",
        "--volume",
        f"{event_log}:{CONTAINER_EVENT_LOG}:rw,Z",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "--entrypoint",
        "/bin/sh",
    ]
    for name, value in sorted(container_environment.items()):
        docker_command.extend(["--env", f"{name}={value}"])
    docker_command.extend([image, "-c", command])
    try:
        completed = subprocess.run(
            docker_command,
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=max(1, timeout_seconds),
            env=_docker_environment(),
        )
    except subprocess.TimeoutExpired:
        # Killing the docker CLI does not reliably stop the container it
        # started. Force-remove the uniquely named container before allowing
        # the harness timeout to propagate, otherwise a model can leave an
        # unbounded command running after the sample has ended.
        try:
            subprocess.run(
                ["docker", "rm", "--force", container_name],
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=min(10, max(1, timeout_seconds)),
                env=_docker_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            # Preserve the original timeout as the useful harness result. The
            # cleanup command is best effort because the daemon may already
            # have removed a container that exited concurrently.
            pass
        raise
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).rstrip()
    if completed.returncode == 125:
        raise RuntimeError(f"Docker could not start the Bedrock tool sandbox: {output[-500:]}")
    return CommandRecord(command=command, output=output, exit_code=completed.returncode)


def _container_environment(environment: dict[str, str]) -> dict[str, str]:
    allowed = {
        name: value
        for name, value in environment.items()
        if name.startswith("SCCFM_HARNESS_")
        or name in {"HOME", "ZDOTDIR", "NO_COLOR", "PYTHONDONTWRITEBYTECODE"}
    }
    allowed["PATH"] = f"{CONTAINER_BINARY_DIRECTORY}:/usr/local/bin:/usr/bin:/bin"
    allowed["SCCFM_HARNESS_REAL_PYTHON"] = "/usr/local/bin/python3"
    allowed["SCCFM_HARNESS_DISPATCHER"] = str(CONTAINER_BINARY_DIRECTORY / "sccfm-cli")
    allowed["SCCFM_HARNESS_EVENT_LOG"] = str(CONTAINER_EVENT_LOG)
    return allowed


def _docker_environment() -> dict[str, str]:
    names = ("PATH", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "XDG_RUNTIME_DIR")
    return {name: os.environ[name] for name in names if name in os.environ}


def _remaining_seconds(deadline: float) -> int:
    remaining = int(deadline - time.monotonic())
    if remaining < 1:
        raise subprocess.TimeoutExpired("bedrock", 0)
    return remaining
