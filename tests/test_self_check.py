import sqlite3

import numpy as np

from app.core.memory import Memory
from app.core.self_check import self_check


def test_correct_answer_produces_no_report(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    mem = Memory(tmp_path / "mem.db")

    report = self_check("2 + 2 = 4", mem)
    assert report is None

    with sqlite3.connect(tmp_path / "mem.db") as con:
        count = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert count == 0
