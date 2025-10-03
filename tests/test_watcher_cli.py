import importlib
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
        intelligence=SimpleNamespace(mode="offline"),
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


def test_plugin_list_imported_without_root_manifest(tmp_path, capsys):
    module = cli
    try:
        with _hide_source_manifest(tmp_path):
            module = importlib.reload(cli)
            manifest = resources.files("app") / "plugins.toml"
            assert manifest.is_file()
            packaged = module._plugin_base()
            assert packaged is not None
            assert packaged.is_file()
            assert packaged.read_text(encoding="utf-8") == manifest.read_text(
                encoding="utf-8"
            )
            _assert_lists_hello(capsys, module.main(["plugin", "list"]))
    finally:
        importlib.reload(module)


def test_run_command_sets_offline_and_uses_engine(monkeypatch, capsys):
    class DummyClient:
        backend = "llama.cpp"

        def __init__(self) -> None:
            self.model_path = Path("/tmp/model.gguf")

    class DummyEngine:
        def __init__(self) -> None:
            self.client = DummyClient()
            self.offline = False
            self.prompt = None

        def set_offline(self, value: bool) -> None:
            self.offline = bool(value)

        def chat(self, prompt: str) -> str:
            self.prompt = prompt
            return "stub-answer"

    engine = DummyEngine()
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["run", "--prompt", "Salut", "--offline"])

    assert exit_code == 0
    assert engine.offline is True
    assert engine.prompt == "Salut"
    captured = capsys.readouterr()
    assert "stub-answer" in captured.out


def test_ask_command_uses_rag(monkeypatch, capsys):
    class DummyEngine:
        def __init__(self) -> None:
            self.offline = False
            self.client = object()

        def set_offline(self, value: bool) -> None:
            self.offline = bool(value)

    engine = DummyEngine()
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    captured_kwargs: dict[str, object] = {}

    def _fake_answer(question: str, *, client, store, k: int) -> str:
        captured_kwargs.update(
            {"question": question, "client": client, "store": store, "k": k}
        )
        return "réponse déterministe"

    monkeypatch.setattr(cli.rag, "answer_question", _fake_answer)

    class DummyStore:
        def __init__(self, namespace: str) -> None:
            self.namespace = namespace

    monkeypatch.setattr(cli, "SimpleVectorStore", DummyStore)

    exit_code = cli.main(["ask", "Que fais-tu?", "--top-k", "2", "--namespace", "docs"])

    assert exit_code == 0
    assert engine.offline is True  # hérite de l'environnement offline par défaut
    assert captured_kwargs["question"] == "Que fais-tu?"
    assert captured_kwargs["k"] == 2
    assert isinstance(captured_kwargs["store"], DummyStore)
    assert captured_kwargs["store"].namespace == "docs"
    captured = capsys.readouterr()
    assert "réponse déterministe" in captured.out


def test_ingest_command_reads_files(monkeypatch, tmp_path, capsys):
    file_a = tmp_path / "a.md"
    file_a.write_text("Contenu A", encoding="utf-8")
    dir_b = tmp_path / "docs"
    dir_b.mkdir()
    file_b = dir_b / "b.txt"
    file_b.write_text("Contenu B", encoding="utf-8")

    added: list[tuple[list[str], list[dict[str, str]]]] = []

    class DummyStore:
        def __init__(self, namespace: str) -> None:
            self.namespace = namespace

        def add(self, texts, metas) -> None:  # pragma: no cover - runtime validated
            added.append((list(texts), list(metas)))

    monkeypatch.setattr(cli, "SimpleVectorStore", DummyStore)

    exit_code = cli.main(
        [
            "ingest",
            str(file_a),
            str(dir_b),
            "--namespace",
            "tests",
            "--batch-size",
            "1",
        ]
    )

    assert exit_code == 0
    flat_texts = [text for batch, _ in added for text in batch]
    assert "Contenu A" in flat_texts
    assert "Contenu B" in flat_texts
    captured = capsys.readouterr()
    assert "namespace 'tests'" in captured.out
