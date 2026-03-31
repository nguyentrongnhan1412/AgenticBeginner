"""Modal Sandbox Tool - Execute shell commands in an isolated Modal Sandbox."""

import logging
import os
import re

import modal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocklist — commands that are never allowed (substring match, case-insensitive)
# ---------------------------------------------------------------------------
_BLOCKLIST = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf $",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",  # fork bomb
    "> /dev/sd",
    "chmod -R 777 /",
    "nc -",
    "netcat",
    "/dev/tcp",
    "python -c 'import socket",
]

_MAX_COMMAND_LEN = 8000

# Optional: comma-separated prefixes; if set, command must start with one after strip
_PREFIXES_ENV = "SANDBOX_COMMAND_PREFIXES"

# Injection / subshell patterns (single-line commands with pipes/semicolons are still user-controlled)
_FORBIDDEN_SUBSTRINGS = [
    "\x00",
    "\n",
    "\r",
    "`",
    "$(",
    "${",
    "<(",
]


def _validate_command(cmd: str) -> None:
    """Raise ValueError if the command fails policy checks."""
    if not cmd or not cmd.strip():
        raise ValueError("Command is empty.")
    if len(cmd) > _MAX_COMMAND_LEN:
        raise ValueError(f"Command exceeds maximum length ({_MAX_COMMAND_LEN}).")

    cmd_stripped = cmd.strip()
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad in cmd:
            raise ValueError(f"Command blocked: disallowed token or character sequence ({bad!r}).")

    prefixes_raw = os.environ.get(_PREFIXES_ENV, "").strip()
    if prefixes_raw:
        prefixes = [p.strip() for p in prefixes_raw.split(",") if p.strip()]
        if prefixes and not any(cmd_stripped.startswith(p) for p in prefixes):
            raise ValueError(
                f"Command must start with one of these prefixes (set {_PREFIXES_ENV}): {prefixes}"
            )

    cmd_lower = cmd.lower()
    for blocked in _BLOCKLIST:
        if blocked.lower() in cmd_lower:
            raise ValueError(f"Command blocked for safety: contains '{blocked}'")

    # Block obvious path traversal in a single token (lightweight heuristic)
    if re.search(r"\.\./|\.\.\\", cmd):
        raise ValueError("Command blocked: path traversal (..) is not allowed.")


# ---------------------------------------------------------------------------
# Sandbox image
# ---------------------------------------------------------------------------
_IMAGE = (
    modal.Image.debian_slim()
    .pip_install("pandas", "openpyxl", "python-dotenv")
)


def sandbox_exec(cmd: str, timeout: int = 30) -> str:
    """Run *cmd* inside an isolated Modal Sandbox and return the output.

    The sandbox:
    - Runs in an ephemeral Debian Slim container with pandas/openpyxl.
    - Has no persistent filesystem mount to the host.
    - Times out after *timeout* seconds.
    - Streams stdout + stderr and returns combined output.

    Args:
        cmd:     Shell command to execute (passed to bash -c).
        timeout: Maximum execution time in seconds.

    Returns:
        Combined stdout/stderr string from the command.

    Raises:
        ValueError: If the command is blocked by the safety checklist.
    """
    _validate_command(cmd)
    logger.info("sandbox_exec starting timeout=%s", timeout)

    app = modal.App.lookup("sandbox-exec", create_if_missing=True)

    sb = modal.Sandbox.create(
        "bash",
        "-c",
        cmd,
        image=_IMAGE,
        timeout=timeout,
        app=app,
    )

    stdout_lines = []
    for line in sb.stdout:
        stdout_lines.append(line)

    stderr_lines = []
    for line in sb.stderr:
        stderr_lines.append(line)

    sb.wait()

    output_parts = []
    if stdout_lines:
        output_parts.append("".join(stdout_lines))
    if stderr_lines:
        output_parts.append("[stderr]\n" + "".join(stderr_lines))

    combined = "\n".join(output_parts).strip()
    out = combined if combined else "(no output)"
    logger.info("sandbox_exec finished output_chars=%s", len(out))
    return out
