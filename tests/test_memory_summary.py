import sqlite3
from app.utils import np

from app.core.memory import Memory


def test_summarize_limits_items(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0]) for _ in texts]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.set_offline(False)
    max_items = 5
    for i in range(max_items + 3):
        mem.add("note", f"msg {i}")
        mem.summarize("note", max_items)
        with sqlite3.connect(db_path) as con:
            count = con.execute(
                "SELECT COUNT(*) FROM items WHERE kind='note'"
            ).fetchone()[0]
        assert count <= max_items
