from pathlib import Path

import pytest

from app import cli


def _assert_lists_hello(capsys, exit_code: int) -> None:
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "hello" in {line.strip() for line in captured.out.splitlines()}


def test_plugin_list_shows_default_plugin(capsys):
    _assert_lists_hello(capsys, cli.main(["plugin", "list"]))


def test_plugin_list_installed_layout(tmp_path, capsys):
    manifest = Path("plugins.toml")
    if not manifest.exists():
        pytest.skip("source-layout manifest not present")

    backup = tmp_path / "plugins.toml.bak"
    manifest.rename(backup)
    try:
        _assert_lists_hello(capsys, cli.main(["plugin", "list"]))
    finally:
        backup.rename(manifest)
