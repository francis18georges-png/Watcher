import runpy  # ensure CLI module runs without NameError
import sys
from pathlib import Path
import logging

import pytest

from app import cli as watcher_cli
from app.tools.scaffold import create_python_cli


def test_create_python_cli(tmp_path, caplog):
    proj_dir = Path(create_python_cli("foo", tmp_path))
    sys.path.insert(0, str(proj_dir))
    argv = sys.argv
    sys.argv = ["foo", "--ping"]
    try:
        caplog.set_level(logging.INFO)
        runpy.run_module("foo.cli", run_name="__main__")
    finally:
        sys.argv = argv
        sys.path.pop(0)
    assert "pong" in caplog.text


def test_create_python_cli_refuses_overwrite_without_force(tmp_path):
    proj_dir = tmp_path / "app" / "projects" / "foo"
    proj_dir.mkdir(parents=True)
    (proj_dir / "existing.txt").write_text("content", encoding="utf-8")

    with pytest.raises(FileExistsError):
        create_python_cli("foo", tmp_path)


def test_create_python_cli_force_overwrite(tmp_path, caplog):
    proj_dir = tmp_path / "app" / "projects" / "foo"
    (proj_dir / "foo").mkdir(parents=True)
    (proj_dir / "foo/cli.py").write_text("print('old')\n", encoding="utf-8")

    proj_dir = Path(create_python_cli("foo", tmp_path, force=True))
    sys.path.insert(0, str(proj_dir))
    argv = sys.argv
    sys.argv = ["foo", "--ping"]
    try:
        caplog.set_level(logging.INFO)
        runpy.run_module("foo.cli", run_name="__main__")
    finally:
        sys.argv = argv
        sys.path.pop(0)
    assert "pong" in caplog.text


@pytest.fixture(autouse=True)
def _stub_watcher_settings(monkeypatch):
    """Avoid full runtime config loading while testing watcher CLI routes."""

    class _Settings:
        class llm:
            backend = "stub"
            model = "stub-model"

        class training:
            seed = 42

        class intelligence:
            mode = "offline"

    monkeypatch.setattr(watcher_cli, "auto_configure_if_needed", lambda *args, **kwargs: None)
    monkeypatch.setattr(watcher_cli, "get_settings", lambda: _Settings())


def test_watcher_policy_cli_approve_revoke_flow(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()

    configurator = watcher_cli.FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)
    manager = watcher_cli.PolicyManager(home=home)
    monkeypatch.setattr(watcher_cli, "PolicyManager", lambda: manager)

    approve_code = watcher_cli.main(
        ["policy", "approve", "--domain", "example.com", "--scope", "git"]
    )
    assert approve_code == 0
    assert "Autorisation enregistrée pour example.com (git)" in capsys.readouterr().out

    revoke_code = watcher_cli.main(
        ["policy", "revoke", "--domain", "example.com", "--scope", "git"]
    )
    assert revoke_code == 0
    assert "Autorisation révoquée pour example.com (git)" in capsys.readouterr().out


def test_watcher_policy_cli_rejects_invalid_scope(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()

    configurator = watcher_cli.FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)
    manager = watcher_cli.PolicyManager(home=home)
    monkeypatch.setattr(watcher_cli, "PolicyManager", lambda: manager)

    with pytest.raises(SystemExit) as exc:
        watcher_cli.main(
            ["policy", "approve", "--domain", "example.com", "--scope", "api"]
        )

    assert exc.value.code == 2
