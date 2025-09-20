from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import cli


def _assert_lists_hello(capsys, exit_code: int) -> None:
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "hello" in {line.strip() for line in captured.out.splitlines()}


@pytest.fixture(autouse=True)
def _stub_cli_settings(monkeypatch):
    """Avoid loading full configuration when exercising the CLI."""

    settings = SimpleNamespace(
        llm=SimpleNamespace(backend="stub-backend", model="stub-model"),
        training=SimpleNamespace(seed=123),
        intelligence=SimpleNamespace(mode="offline"),
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "set_seed", lambda seed: None)
    return settings


def test_plugin_list_shows_default_plugin(tmp_path, capsys):
    with _hide_source_manifest(tmp_path):
        _assert_lists_hello(capsys, cli.main(["plugin", "list"]))


@contextmanager
def _hide_source_manifest(tmp_path: Path):
    """Temporarily move the repository manifest out of the way."""

    manifest = Path("plugins.toml")
    backup = None
    if manifest.exists():
        backup = tmp_path / manifest.name
        manifest.rename(backup)
    try:
        assert not manifest.exists()
        yield
    finally:
        if backup is not None:
            backup.rename(manifest)


def test_plugin_list_installed_layout(tmp_path, capsys):
    with _hide_source_manifest(tmp_path):
        assert not Path("plugins.toml").exists()
        base = cli._plugin_base()
        assert base is not None
        assert base.is_file()
        manifest = resources.files("app") / "plugins.toml"
        assert manifest.is_file()
        _assert_lists_hello(capsys, cli.main(["plugin", "list"]))


def test_run_command_defaults_to_offline(monkeypatch):
    called: dict[str, bool] = {}

    def fake_run(offline: bool) -> int:
        called["offline"] = offline
        return 0

    monkeypatch.setattr(cli, "_run_watcher", fake_run)
    exit_code = cli.main(["run"])
    assert exit_code == 0
    assert called["offline"] is True


def test_run_command_explicit_online(monkeypatch):
    called: dict[str, bool] = {}

    def fake_run(offline: bool) -> int:
        called["offline"] = offline
        return 0

    monkeypatch.setattr(cli, "_run_watcher", fake_run)
    exit_code = cli.main(["run", "--online"])
    assert exit_code == 0
    assert called["offline"] is False
