from pathlib import Path

from app.core.autostart import render_systemd_scripts, render_windows_scripts


def test_windows_scripts_render_expected_content(tmp_path: Path) -> None:
    artifacts = render_windows_scripts(tmp_path, autopilot_command="watcher autopilot run")
    paths = {artifact.path.name: artifact for artifact in artifacts}
    assert "watcher-register-autostart.ps1" in paths
    rendered = paths["watcher-register-autostart.ps1"].write()
    content = rendered.read_text(encoding="utf-8")
    assert "watcher autopilot run" in content
    assert content.endswith("\n")


def test_systemd_scripts_are_deterministic(tmp_path: Path) -> None:
    artifacts = render_systemd_scripts(
        tmp_path,
        autopilot_command="/usr/bin/python -m app.cli autopilot run",
        working_dir=Path("/srv/watcher"),
    )
    names = {artifact.path.name for artifact in artifacts}
    assert {"watcher-autopilot.service", "watcher-autopilot.timer"} <= names
    for artifact in artifacts:
        path = artifact.write()
        content = path.read_text(encoding="utf-8")
        assert content.endswith("\n")
