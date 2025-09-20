import math
import sqlite3

from app.utils import np
import pytest

from app.core.memory import Memory


def test_add_and_search(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.add("note", "salut")

    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT kind,text,vec FROM items").fetchone()
    assert row[0] == "note"
    assert row[1] == "salut"
    vec = np.frombuffer(row[2], dtype=np.float32)
    assert vec.tolist() == [1.0]
    assert len(vec) == 1

    results = mem.search("salut")
    assert len(results) == 1
    assert results[0][2] == "note"
    assert results[0][3] == "salut"


def test_search_embedding_error(tmp_path, monkeypatch):
    def good_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", good_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.add("note", "bonjour")

    def bad_embed(texts, model="nomic-embed-text"):
        return [np.array([], dtype=np.float32)]

    monkeypatch.setattr("app.core.memory.embed_ollama", bad_embed)
    assert mem.search("bonjour") == []


def test_search_respects_threshold(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        if fake_embed.calls == 0:
            fake_embed.calls += 1
            return [np.array([1.0, 0.0])]
        return [np.array([0.0, 1.0])]

    fake_embed.calls = 0
    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    mem = Memory(tmp_path / "mem.db")
    mem.add("note", "salut")
    with pytest.raises(ValueError):
        mem.search("salut", threshold=0.5)


def test_search_threshold_checks_top_score(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        mapping = {
            "good": np.array([1.0, 0.0]),
            "bad": np.array([0.1, 1.0]),
        }
        return [mapping[text] for text in texts]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    mem = Memory(tmp_path / "mem.db")
    mem.add("note", "good")
    mem.add("note", "bad")

    results = mem.search("good", top_k=2, threshold=0.5)
    assert len(results) == 2
    assert results[0][0] >= 0.5
    assert results[1][0] < 0.5


def test_cosine_similarity_handles_tiny_denominator():
    tiny = np.array([1e-12], dtype=np.float32)
    blob = tiny.astype("float32").tobytes()
    assert Memory._cosine_similarity(blob, blob) == 0.0


def test_cosine_similarity_regular():
    vec = np.array([1.0], dtype=np.float32)
    blob = vec.tobytes()
    assert math.isclose(Memory._cosine_similarity(blob, blob), 1.0, rel_tol=1e-6)


def test_sqlcipher_configuration_executes_key_pragma(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCHER_MEMORY_ENABLE_SQLCIPHER", "1")
    monkeypatch.setenv("WATCHER_MEMORY_SQLCIPHER_PASSWORD", "pa'ss")

    mem = Memory(tmp_path / "mem.db")
    mem._sqlcipher_available = True
    mem._sqlcipher_enabled = True
    mem._sqlcipher_key_sql = "PRAGMA key = 'pa''ss'"

    executed: list[str] = []

    class FakeSQLCipherConnection:
        def execute(self, sql, params=None):
            if params is not None:
                raise AssertionError("SQLCipher PRAGMA should not use parameter binding")
            executed.append(sql)
            if sql.startswith("PRAGMA key ="):
                return self
            raise AssertionError(f"Unexpected SQL: {sql}")

        def cursor(self):  # pragma: no cover - not used but mimics sqlite interface
            return self

        def fetchall(self):  # pragma: no cover - compatibility shim
            return []

        def fetchmany(self, *_args, **_kwargs):  # pragma: no cover - compatibility shim
            return []

        def __enter__(self):  # pragma: no cover - allow use as context manager if needed
            return self

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - context manager protocol
            return False

    fake_con = FakeSQLCipherConnection()
    mem._configure_sqlcipher(fake_con)

    assert executed == ["PRAGMA key = 'pa''ss'"]


def test_connection_pragmas_applied(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    mem = Memory(tmp_path / "mem.db")

    with mem._connect() as con:
        journal_mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert isinstance(journal_mode, str)
        assert journal_mode.lower() == "wal"
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        secure_delete = con.execute("PRAGMA secure_delete").fetchone()[0]
        assert secure_delete in (1, "1", "on", "ON")


def test_ensure_fts5_detects_compile_option(tmp_path, monkeypatch):
    monkeypatch.setattr(Memory, "_run_migrations", lambda self: None)
    mem = Memory(tmp_path / "mem.db")
    mem._fts5_checked = False
    mem._fts5_available = False

    class FakeConnection:
        def execute(self, sql):
            assert sql == "PRAGMA compile_options"
            return [("ENABLE_FTS5",)]

    mem._ensure_fts5(FakeConnection())

    assert mem.fts5_available is True


def test_ensure_fts5_loads_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(Memory, "_run_migrations", lambda self: None)
    mem = Memory(tmp_path / "mem.db")
    mem._fts5_checked = False
    mem._fts5_available = False

    class FakeConnection:
        def __init__(self):
            self._extension_enabled = False

        def execute(self, sql):
            assert sql == "PRAGMA compile_options"
            raise sqlite3.DatabaseError

        def enable_load_extension(self, flag):
            self._extension_enabled = bool(flag)

        def load_extension(self, name):
            assert self._extension_enabled is True
            assert name == "fts5"

    mem._ensure_fts5(FakeConnection())

    assert mem.fts5_available is True
