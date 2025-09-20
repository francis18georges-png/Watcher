from contextlib import contextmanager
from pathlib import Path

from app import cli


def _assert_lists_hello(capsys, exit_code: int) -> None:
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "hello" in {line.strip() for line in captured.out.splitlines()}


def test_plugin_list_shows_default_plugin(capsys):
    _assert_lists_hello(capsys, cli.main(["plugin", "list"]))


@contextmanager
def _hide_source_manifest(tmp_path: Path):
    """Temporarily move the repository manifest out of the way."""

    manifest = Path("plugins.toml")
    if not manifest.exists():
        yield
        return

    backup = tmp_path / manifest.name
    manifest.rename(backup)
    try:
        assert not manifest.exists()
        yield
    finally:
        backup.rename(manifest)


def test_plugin_list_installed_layout(tmp_path, capsys):
    with _hide_source_manifest(tmp_path):
        _assert_lists_hello(capsys, cli.main(["plugin", "list"]))


def test_run_status_only_reports_offline(capsys):
    exit_code = cli.main(["run", "--offline", "--status-only"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "hors ligne" in captured.out.lower()
