import sqlite3
import time
from pathlib import Path

import numpy as np

from app.tools.embeddings import embed_ollama


class Memory:
    def __init__(self, db_path: Path, top_k: int = 8):
        self.db_path = Path(db_path)
        self.top_k = top_k
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        con = sqlite3.connect(self.db_path)
        c = con.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS items("  # noqa: E501
            "id INTEGER PRIMARY KEY, kind TEXT, text TEXT, vec BLOB, ts REAL)"
        )
        con.commit()
        con.close()

    def add(self, kind: str, text: str) -> None:
        vec = embed_ollama([text])[0].astype("float32").tobytes()
        con = sqlite3.connect(self.db_path)
        c = con.cursor()
        c.execute(
            "INSERT INTO items(kind,text,vec,ts) VALUES(?,?,?,?)",
            (kind, text, vec, time.time()),
        )
        con.commit()
        con.close()

    def search(self, query: str, top_k: int | None = None):
        if top_k is None:
            top_k = self.top_k
        q = embed_ollama([query])[0].astype("float32")
        con = sqlite3.connect(self.db_path)
        c = con.cursor()
        rows = c.execute("SELECT id,kind,text,vec FROM items").fetchall()
        con.close()
        scored = []
        for _id, kind, text, vec in rows:
            v = np.frombuffer(vec, dtype=np.float32)
            s = float(q @ v / ((np.linalg.norm(q) * np.linalg.norm(v)) + 1e-9))
            scored.append((s, _id, kind, text))
        scored.sort(reverse=True)
        return scored[:top_k]
