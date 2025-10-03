"""Helpers to configure OS-level autostart for the autopilot scheduler."""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from config import _CONFIG_DIR

DEFAULT_TASK_NAME = "Watcher Autopilot"
SERVICE_NAME = "watcher-autopilot.service"
TIMER_NAME = "watcher-autopilot.timer"
RUN_ONCE_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce"
RUN_ONCE_VALUE = "WatcherAutopilot"
KILL_SWITCH_FILENAME = "autostart.disable"


class AutostartError(RuntimeError):
    """Raised when the autostart configuration cannot be applied."""


def _command_parts() -> list[str]:
    """Return the command used to evaluate the autopilot scheduler."""

    return [sys.executable, "-m", "watcher", "autopilot", "status"]


def _windows_command() -> str:
    parts = _command_parts()
    quoted = [f'"{parts[0]}"'] + parts[1:]
    return " ".join(quoted)


def _systemd_command() -> str:
    return " ".join(shlex.quote(part) for part in _command_parts())


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_env(env_path: Path) -> tuple[list[str], dict[str, str]]:
    comments: list[str] = []
    values: dict[str, str] = {}
    if not env_path.exists():
        return comments, values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            comments.append(line)
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return comments, values


def _write_env(env_path: Path, *, comments: Iterable[str], values: dict[str, str]) -> None:
    lines = list(comments)
    for key, value in values.items():
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_kill_switch_path(home: Path | None = None) -> Path:
    base = home or Path.home()
    return base / ".watcher" / KILL_SWITCH_FILENAME


def is_autostart_disabled(*, home: Path | None = None) -> bool:
    kill_switch = get_kill_switch_path(home)
    disable_env = os.environ.get("WATCHER_DISABLE")
    if disable_env:
        normalised = disable_env.strip().lower()
        if normalised in {"1", "true", "yes", "on"}:
            return True
        candidate = Path(disable_env).expanduser()
        if candidate.exists():
            return True
    if kill_switch.exists():
        return True
    return False


def _configure_windows(command: str) -> None:
    create_task = [
        "schtasks",
        "/Create",
        "/TN",
        DEFAULT_TASK_NAME,
        "/TR",
        command,
        "/SC",
        "MINUTE",
        "/MO",
        "5",
        "/F",
    ]
    subprocess.run(create_task, check=True)

    run_once = [
        "reg",
        "add",
        RUN_ONCE_KEY,
        "/v",
        RUN_ONCE_VALUE,
        "/d",
        command,
        "/f",
    ]
    subprocess.run(run_once, check=True)


def _configure_systemd(home: Path, command: str) -> None:
    systemd_dir = home / ".config" / "systemd" / "user"
    _ensure_directory(systemd_dir)

    service_path = systemd_dir / SERVICE_NAME
    timer_path = systemd_dir / TIMER_NAME

    service_content = f"""[Unit]
Description=Watcher Autopilot scheduler

[Service]
Type=oneshot
ExecStart={command}
"""
    timer_content = f"""[Unit]
Description=Watcher Autopilot periodic trigger

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit={SERVICE_NAME}

[Install]
WantedBy=default.target
"""

    service_path.write_text(service_content, encoding="utf-8")
    timer_path.write_text(timer_content, encoding="utf-8")

    subprocess.run(
        ["systemctl", "--user", "enable", "--now", TIMER_NAME],
        check=True,
    )


def configure_autostart(
    *,
    home: Path | None = None,
    env_path: Path | None = None,
    consent_granted: bool = True,
) -> bool:
    """Configure scheduled execution of the autopilot if permitted.

    Returns :data:`True` when the configuration succeeded, :data:`False`
    otherwise.  The ``.env`` file is updated with ``WATCHER_AUTOSTART`` and
    ``WATCHER_DISABLE`` entries in all cases.
    """

    base_home = home or Path.home()
    env_file = env_path or (_CONFIG_DIR.parent / ".env")
    kill_switch = get_kill_switch_path(base_home)

    comments, values = _read_env(env_file)

    success = False
    if consent_granted and not is_autostart_disabled(home=base_home):
        command = _windows_command()
        system = platform.system().lower()
        try:
            if system.startswith("win"):
                _configure_windows(command)
            else:
                _configure_systemd(base_home, _systemd_command())
            success = True
        except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
            raise AutostartError(str(exc)) from exc

    values["WATCHER_DISABLE"] = str(kill_switch)
    values["WATCHER_AUTOSTART"] = "1" if success else "0"
    _write_env(env_file, comments=comments, values=values)

    if "WATCHER_DISABLE" not in os.environ:
        os.environ["WATCHER_DISABLE"] = str(kill_switch)
    os.environ["WATCHER_AUTOSTART"] = "1" if success else "0"

    return success

