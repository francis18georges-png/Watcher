from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from types import SimpleNamespace

from app import cli


def _assert_lists_hello(capsys, exit_code: int) -> None:
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "hello" in {line.strip() for line in captured.out.splitlines()}


def _patch_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: SimpleNamespace(
            llm=SimpleNamespace(backend="ollama", model="llama3"),
        ),
    )


def test_plugin_list_shows_default_plugin(monkeypatch, capsys):
    _patch_settings(monkeypatch)
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


def test_plugin_list_installed_layout(tmp_path, monkeypatch, capsys):
    _patch_settings(monkeypatch)
    with _hide_source_manifest(tmp_path):
        assert not Path("plugins.toml").exists()
        manifest = resources.files("app") / "plugins.toml"
        assert manifest.is_file()
        _assert_lists_hello(capsys, cli.main(["plugin", "list"]))


def test_run_command_offline_prompt(monkeypatch, capsys):
    _patch_settings(monkeypatch)
    created = []

    class DummyEngine:
        def __init__(self) -> None:
            self._offline = False
            self.calls: list[str] = []
            created.append(self)

        def set_offline_mode(self, value: bool) -> None:
            self._offline = bool(value)

        def is_offline(self) -> bool:
            return self._offline

        def chat(self, prompt: str) -> str:
            self.calls.append(prompt)
            return f"offline={self._offline}"

    monkeypatch.setattr(cli, "Engine", DummyEngine)

    exit_code = cli.main(["run", "--offline", "--prompt", "salut"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mode offline activé" in captured.out
    assert "offline=True" in captured.out
    assert created[0]._offline is True
    assert created[0].calls == ["salut"]


def test_run_command_online_override(monkeypatch, capsys):
    _patch_settings(monkeypatch)

    class DummyEngine:
        def __init__(self) -> None:
            self._offline = True

        def set_offline_mode(self, value: bool) -> None:
            self._offline = bool(value)

        def is_offline(self) -> bool:
            return self._offline

        def chat(self, prompt: str) -> str:  # pragma: no cover - not used
            raise AssertionError("chat should not be called")

    monkeypatch.setattr(cli, "Engine", DummyEngine)

    exit_code = cli.main(["run", "--online"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mode offline désactivé" in captured.out
