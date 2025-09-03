import sqlite3
import time
import logging
from pathlib import Path

import numpy as np

from app.tools.embeddings import embed_ollama


class Memory:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            c.execute(
                "CREATE TABLE IF NOT EXISTS items("  # noqa: E501
                "id INTEGER PRIMARY KEY, kind TEXT, text TEXT, vec BLOB, ts REAL)"
            )

    def add(self, kind: str, text: str) -> None:
        try:
            vec = embed_ollama([text])[0].astype("float32").tobytes()
        except Exception:
            logging.exception("Failed to embed text for kind '%s'", kind)
            vec = np.array([], dtype=np.float32).tobytes()
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            c.execute(
                "INSERT INTO items(kind,text,vec,ts) VALUES(?,?,?,?)",
                (kind, text, vec, time.time()),
            )

    def search(self, query: str, top_k: int = 8):
        try:
            q = embed_ollama([query])[0].astype("float32")
        except Exception:
            logging.exception("Failed to embed search query")
            return []
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            rows = c.execute("SELECT id,kind,text,vec FROM items").fetchall()
        scored = []
        for _id, kind, text, vec in rows:
            v = np.frombuffer(vec, dtype=np.float32)
            if v.size != q.size or v.size == 0:
                continue
            s = float(q @ v / ((np.linalg.norm(q) * np.linalg.norm(v)) + 1e-9))
            scored.append((s, _id, kind, text))
        scored.sort(reverse=True)
        return scored[:top_k]
