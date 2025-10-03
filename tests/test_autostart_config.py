"""Tests for OS-specific autostart helpers."""

from __future__ import annotations

from pathlib import Path

from app.utils import autostart


def test_systemd_unit_uses_cli_module(monkeypatch) -> None:
    monkeypatch.setattr(autostart.sys, "executable", "/opt/python/bin/python3")
    unit = autostart.systemd_service_unit(Path("/srv/watcher"))
    assert "ExecStart=/opt/python/bin/python3 -m app.cli autopilot status" in unit


def test_windows_task_uses_cli_module(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autostart.sys, "executable", r"C:\\Python311\\python.exe")
    definition = autostart.windows_task_definition(tmp_path)
    assert definition["action"]["path"] == r"C:\\Python311\\python.exe"
    assert definition["action"]["arguments"] == [
        "-m",
        "app.cli",
        "autopilot",
        "status",
    ]
