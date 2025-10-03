"""Tests for the autostart helper routines."""

from __future__ import annotations

from pathlib import Path

import platform
import subprocess

import pytest

from app.utils import autostart


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WATCHER_DISABLE", raising=False)
    monkeypatch.delenv("WATCHER_AUTOSTART", raising=False)


def test_configure_autostart_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def _fake_run(cmd, check):
        commands.append(list(cmd))

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    home = tmp_path / "home"
    home.mkdir()
    env_path = tmp_path / ".env"

    result = autostart.configure_autostart(home=home, env_path=env_path, consent_granted=True)

    assert result is True
    assert commands[0][:4] == ["schtasks", "/Create", "/TN", autostart.DEFAULT_TASK_NAME]
    assert "watcher autopilot status" in " ".join(commands[0])
    assert commands[1][:4] == ["reg", "add", autostart.RUN_ONCE_KEY, "/v"]
    env_content = env_path.read_text(encoding="utf-8")
    assert "WATCHER_AUTOSTART=1" in env_content
    assert "WATCHER_DISABLE=" in env_content


def test_configure_autostart_systemd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def _fake_run(cmd, check):
        commands.append(list(cmd))

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    home = tmp_path / "home"
    home.mkdir()
    env_path = tmp_path / ".env"

    result = autostart.configure_autostart(home=home, env_path=env_path, consent_granted=True)

    assert result is True
    systemd_dir = home / ".config" / "systemd" / "user"
    service = systemd_dir / autostart.SERVICE_NAME
    timer = systemd_dir / autostart.TIMER_NAME
    assert service.exists()
    assert timer.exists()
    service_text = service.read_text(encoding="utf-8")
    assert "watcher autopilot status" in service_text
    assert commands == [["systemctl", "--user", "enable", "--now", autostart.TIMER_NAME]]
    env_content = env_path.read_text(encoding="utf-8")
    assert "WATCHER_AUTOSTART=1" in env_content
    assert "WATCHER_DISABLE=" in env_content


def test_autostart_respects_kill_switch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    home = tmp_path / "home"
    kill_switch = home / ".watcher" / autostart.KILL_SWITCH_FILENAME
    kill_switch.parent.mkdir(parents=True)
    kill_switch.write_text("", encoding="utf-8")
    env_path = tmp_path / ".env"

    result = autostart.configure_autostart(home=home, env_path=env_path, consent_granted=True)

    assert result is False
    assert not (home / ".config" / "systemd" / "user" / autostart.SERVICE_NAME).exists()
    env_content = env_path.read_text(encoding="utf-8")
    assert "WATCHER_AUTOSTART=0" in env_content
    assert "WATCHER_DISABLE=" in env_content
