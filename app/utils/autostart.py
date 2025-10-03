"""Helpers to build autostart definitions for the autopilot scheduler."""

from __future__ import annotations

import shlex
import sys
import textwrap
from pathlib import Path
from typing import Mapping

CommandParts = list[str]


def _command_parts() -> CommandParts:
    """Return the command used to query the autopilot status.

    The command calls the project CLI module directly so that it works both in
    editable installs and in packaged distributions where the ``watcher`` entry
    point may not be available (for example inside Windows scheduled tasks or
    systemd units).
    """

    return [sys.executable, "-m", "app.cli", "autopilot", "status"]


def _command_string() -> str:
    """Return the command formatted as a shell-safe string."""

    return shlex.join(_command_parts())


def windows_task_definition(
    working_directory: Path,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build the action block for a Windows scheduled task.

    Parameters
    ----------
    working_directory:
        Directory from which the task should run.
    env:
        Optional environment variables to inject into the task.
    """

    command = _command_parts()
    return {
        "trigger": "logon",
        "action": {
            "path": command[0],
            "arguments": command[1:],
            "working_directory": str(working_directory),
        },
        "environment": dict(env or {}),
    }


def systemd_service_unit(
    working_directory: Path,
    env: Mapping[str, str] | None = None,
) -> str:
    """Render the systemd unit file that probes the autopilot status."""

    env_block = ""
    if env:
        env_block = "".join(
            f"Environment={key}={value}\n        " for key, value in env.items()
        )

    body = textwrap.dedent(
        f"""
        [Unit]
        Description=Watcher Autopilot status probe
        After=network-online.target

        [Service]
        Type=oneshot
        WorkingDirectory={working_directory}
        {env_block}ExecStart={_command_string()}

        [Install]
        WantedBy=multi-user.target
        """
    ).strip()

    # Ensure there is a single trailing newline and no trailing whitespace.
    body = "\n".join(line.rstrip() for line in body.splitlines())
    return body + "\n"
