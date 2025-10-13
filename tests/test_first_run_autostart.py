"""Tests for the autostart configuration performed on first run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.first_run import FirstRunConfigurator


def _fake_subprocess_run(collected: list[list[str]]):
    def _run(cmd: list[str], *args: Any, **kwargs: Any) -> None:
        collected.append(cmd)

    return _run


def test_autostart_creates_systemd_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.delenv("WATCHER_AUTOSTART", raising=False)
    monkeypatch.delenv("WATCHER_DISABLE", raising=False)
    monkeypatch.setattr("app.core.first_run.platform.system", lambda: "Linux")
    monkeypatch.setattr("app.core.first_run.sys.executable", "/opt/python/bin/python3")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.core.first_run.subprocess.run", _fake_subprocess_run(calls)
    )

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    systemd_dir = home / ".config" / "systemd" / "user"
    service_path = systemd_dir / "watcher-autopilot.service"
    timer_path = systemd_dir / "watcher-autopilot.timer"

    assert service_path.exists()
    content = service_path.read_text(encoding="utf-8")
    assert (
        "ExecStart=/opt/python/bin/python3 -m app.cli autopilot run --noninteractive"
        in content
    )

    assert timer_path.exists()
    timer_content = timer_path.read_text(encoding="utf-8")
    assert "OnBootSec=30s" in timer_content
    assert "OnUnitActiveSec=1h" in timer_content
    assert "Persistent=true" in timer_content

    assert [
        "systemctl",
        "--user",
        "daemon-reload",
    ] in calls

    assert [
        "systemctl",
        "--user",
        "enable",
        "--now",
        "watcher-autopilot.timer",
    ] in calls


def test_autostart_creates_windows_definitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.delenv("WATCHER_AUTOSTART", raising=False)
    monkeypatch.delenv("WATCHER_DISABLE", raising=False)
    monkeypatch.setattr("app.core.first_run.platform.system", lambda: "Windows")
    monkeypatch.setattr("app.core.first_run.sys.executable", r"C:\\Watcher\\python.exe")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.core.first_run.subprocess.run", _fake_subprocess_run(calls)
    )

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    powershell_call = next(call for call in calls if call and call[0] == "powershell")
    assert "watcher init --auto" in powershell_call[-1]
    assert "WatcherInit" in powershell_call[-1]

    schtasks_call = next(call for call in calls if call and call[0] == "schtasks")
    assert "/Create" in schtasks_call
    assert "Watcher Autopilot" in schtasks_call
    assert "/SC" in schtasks_call and "ONLOGON" in schtasks_call
    assert any(
        "watcher autopilot run --noninteractive" in part for part in schtasks_call
    )


def test_autostart_respects_disable_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.delenv("WATCHER_AUTOSTART", raising=False)
    monkeypatch.setenv("WATCHER_DISABLE", "1")
    monkeypatch.setattr("app.core.first_run.platform.system", lambda: "Linux")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.core.first_run.subprocess.run", _fake_subprocess_run(calls)
    )

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    systemd_dir = home / ".config" / "systemd" / "user"
    assert not (systemd_dir / "watcher-autopilot.service").exists()
    assert not (systemd_dir / "watcher-autopilot.timer").exists()
    assert calls == []


def test_autostart_force_overrides_kill_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    watcher_dir = home / ".watcher"
    watcher_dir.mkdir(parents=True)
    (watcher_dir / "disable").write_text("blocked", encoding="utf-8")

    monkeypatch.setenv("WATCHER_AUTOSTART", "1")
    monkeypatch.setenv("WATCHER_DISABLE", "1")
    monkeypatch.setattr("app.core.first_run.platform.system", lambda: "Linux")
    monkeypatch.setattr("app.core.first_run.sys.executable", "/usr/bin/python3")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.core.first_run.subprocess.run", _fake_subprocess_run(calls)
    )

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    systemd_dir = home / ".config" / "systemd" / "user"
    service_path = systemd_dir / "watcher-autopilot.service"
    timer_path = systemd_dir / "watcher-autopilot.timer"

    assert service_path.exists()
    assert timer_path.exists()
    assert any("watcher-autopilot.timer" in call for call in map(" ".join, calls))
