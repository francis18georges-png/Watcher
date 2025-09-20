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
        training=SimpleNamespace(seed=42),
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
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


class _DummyEngine:
    def __init__(self) -> None:
        self.offline = False
        self.start_msg = "prêt"
        self.chats: list[str] = []
        self.ratings: list[float] = []

    @property
    def is_offline(self) -> bool:
        return self.offline

    def set_offline(self, offline: bool) -> None:
        self.offline = bool(offline)

    def chat(self, prompt: str) -> str:
        self.chats.append(prompt)
        return f"echo:{prompt}"

    def add_feedback(self, score: float) -> str:
        self.ratings.append(score)
        return "feedback enregistré"


def test_run_command_forces_offline(monkeypatch, capsys):
    created: list[_DummyEngine] = []

    def fake_engine() -> _DummyEngine:
        engine = _DummyEngine()
        created.append(engine)
        return engine

    monkeypatch.setattr(cli, "Engine", fake_engine)

    inputs = iter(["hello", "rate 0.5"])

    def fake_input(prompt: str) -> str:
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)

    exit_code = cli.main(["run", "--offline"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert created and created[0].is_offline
    assert created[0].chats == ["hello"]
    assert created[0].ratings == [0.5]
    assert "Mode offline activé" in captured.out
    assert "echo:hello" in captured.out


def test_run_command_enables_online(monkeypatch, capsys):
    created: list[_DummyEngine] = []

    def fake_engine() -> _DummyEngine:
        engine = _DummyEngine()
        created.append(engine)
        return engine

    monkeypatch.setattr(cli, "Engine", fake_engine)
    monkeypatch.setattr("builtins.input", lambda prompt: "quit")

    exit_code = cli.main(["run", "--online"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert created and not created[0].is_offline
    assert "Mode online activé" in captured.out
