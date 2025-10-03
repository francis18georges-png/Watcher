"""Tests for the autostart configuration performed on first run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from unittest.mock import ANY

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

    monkeypatch.setenv("WATCHER_AUTOSTART", "1")
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
    assert "OnUnitActiveSec=1h" in timer_content

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

    monkeypatch.setenv("WATCHER_AUTOSTART", "1")
    monkeypatch.delenv("WATCHER_DISABLE", raising=False)
    monkeypatch.setattr("app.core.first_run.platform.system", lambda: "Windows")
    monkeypatch.setattr("app.core.first_run.sys.executable", r"C:\\Watcher\\python.exe")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.core.first_run.subprocess.run", _fake_subprocess_run(calls)
    )

    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)

    assert ["powershell", "-NoProfile", "-Command", ANY] in calls
    schtasks_call = next(call for call in calls if call and call[0] == "schtasks")
    assert "/Create" in schtasks_call
    assert "Watcher Autopilot" in schtasks_call
    assert any(
        "python.exe" in part and "autopilot run --noninteractive" in part
        for part in schtasks_call
    )


def test_autostart_respects_disable_switches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    (home / ".watcher").mkdir(parents=True)
    (home / ".watcher" / "disable").write_text("blocked", encoding="utf-8")

    monkeypatch.setenv("WATCHER_AUTOSTART", "1")
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
