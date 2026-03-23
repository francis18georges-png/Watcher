import importlib
import config as config_module
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

import pytest

from app import bootstrap
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
    monkeypatch.setattr(bootstrap, "auto_configure_if_needed", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "auto_configure_if_needed", lambda *args, **kwargs: None)
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
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


def test_run_command_uses_engine_when_not_forced_offline(monkeypatch, capsys):
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

    exit_code = cli.main(["run", "--prompt", "Salut"])

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

    class DummyStore:
        def __init__(self, namespace: str) -> None:
            self.namespace = namespace

    class DummyPipeline:
        def __init__(self, store, *, min_sources: int) -> None:
            self.store = store
            self.min_sources = min_sources
            self.calls: list[Sequence[cli.RawDocument]] = []

        def ingest(self, documents, *, seen_digests):
            self.calls.append(tuple(documents))
            seen_digests.update({"dummy"})
            return 1

    dummy_store = DummyStore("tests")

    def _build_store(namespace: str) -> DummyStore:
        assert namespace == "tests"
        return dummy_store

    pipeline_calls: list[DummyPipeline] = []

    def _build_pipeline(store, *, min_sources: int) -> DummyPipeline:
        pipeline = DummyPipeline(store, min_sources=min_sources)
        pipeline_calls.append(pipeline)
        return pipeline

    monkeypatch.setattr(cli, "SimpleVectorStore", _build_store)
    monkeypatch.setattr(cli, "IngestPipeline", _build_pipeline)

    exit_code = cli.main(
        [
            "ingest",
            str(file_a),
            str(dir_b),
            "--namespace",
            "tests",
            "--batch-size",
            "2",
        ]
    )

    assert exit_code == 0
    assert pipeline_calls
    [pipeline] = pipeline_calls
    assert pipeline.store is dummy_store
    assert pipeline.min_sources == 2
    assert len(pipeline.calls) == 1
    captured_docs = pipeline.calls[0]
    captured_urls = {doc.url for doc in captured_docs}
    assert file_a.as_uri() in captured_urls
    assert file_b.as_uri() in captured_urls
    captured = capsys.readouterr()
    assert "extrait(s) validé(s)" in captured.out


def _prepare_policy_home(tmp_path: Path) -> Path:
    """Create a minimal Watcher home with policy/ledger files."""

    from app.core.first_run import FirstRunConfigurator

    home = tmp_path / "home"
    home.mkdir()
    configurator = FirstRunConfigurator(home=home)
    configurator.run(auto=True, download_models=False)
    return home


def test_policy_approve_and_revoke_roundtrip(monkeypatch, tmp_path, capsys):
    home = _prepare_policy_home(tmp_path)
    manager = cli.PolicyManager(home=home)
    monkeypatch.setattr(cli, "PolicyManager", lambda: manager)

    approve_exit = cli.main(
        ["policy", "approve", "--domain", "Example.COM", "--scope", "git"]
    )
    assert approve_exit == 0
    approve_output = capsys.readouterr().out
    assert "Autorisation enregistrée pour example.com (git)" in approve_output

    policy_text = (home / ".watcher" / "policy.yaml").read_text(encoding="utf-8")
    assert "example.com" in policy_text
    assert "scope: git" in policy_text

    revoke_exit = cli.main(
        ["policy", "revoke", "--domain", "example.com", "--scope", "git"]
    )
    assert revoke_exit == 0
    revoke_output = capsys.readouterr().out
    assert "Autorisation révoquée pour example.com (git)" in revoke_output


@pytest.mark.parametrize(
    ("argv", "message_fragment"),
    [
        (["policy", "approve", "--domain", "   "], "domain must not be empty"),
        (["policy", "revoke", "--domain", "unknown.test"], "aucune autorisation trouvée"),
        (
            ["policy", "approve", "--domain", "example.com", "--scope", "api"],
            "scope must be one of: web, git",
        ),
        (
            ["policy", "approve", "--domain", "example.com", "--bandwidth", "10"],
            "unrecognized arguments: --bandwidth 10",
        ),
    ],
)
def test_policy_commands_report_expected_errors(
    monkeypatch, tmp_path, argv, message_fragment, capsys
):
    home = _prepare_policy_home(tmp_path)
    manager = cli.PolicyManager(home=home)
    monkeypatch.setattr(cli, "PolicyManager", lambda: manager)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(argv)

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert message_fragment in captured.err
