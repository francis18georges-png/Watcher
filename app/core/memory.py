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
            c.execute(
                "CREATE TABLE IF NOT EXISTS feedback("  # noqa: E501
                "id INTEGER PRIMARY KEY, kind TEXT, prompt TEXT, answer TEXT, rating REAL, ts REAL)"
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

    def add_feedback(
        self, kind: str, prompt: str, answer: str, rating: float
    ) -> None:
        """Persist a rated question/answer pair."""
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            c.execute(
                "INSERT INTO feedback(kind,prompt,answer,rating,ts) VALUES(?,?,?,?,?)",
                (kind, prompt, answer, rating, time.time()),
            )

    def all_feedback(self) -> list[tuple[str, str, str, float]]:
        """Return all stored feedback entries."""
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            rows = c.execute(
                "SELECT kind,prompt,answer,rating FROM feedback"
            ).fetchall()
        return rows

    @staticmethod
    def _cosine_similarity(vec_blob: bytes, query_blob: bytes) -> float:
        """Compute cosine similarity between two embedded vectors stored as BLOBs."""
        v1 = np.frombuffer(vec_blob, dtype=np.float32)
        v2 = np.frombuffer(query_blob, dtype=np.float32)
        if len(v1) != len(v2) or len(v1) == 0:
            return 0.0
        return float(v1 @ v2 / ((np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-9))

    def search(self, query: str, top_k: int = 8) -> list[tuple[float, int, str, str]]:
        """Search memory for items similar to ``query``.

        The SQL query is limited to ``top_k`` results using a similarity function to
        avoid loading the entire table into memory.

        Args:
            query: Text to search for.
            top_k: Maximum number of results to return.

        Returns:
            A list of tuples ``(score, id, kind, text)`` sorted by descending
            similarity score.
        """
        try:
            q = embed_ollama([query])[0].astype("float32")
        except Exception:
            logging.exception("Failed to embed search query")
            return []
        q_bytes = q.tobytes()
        with sqlite3.connect(self.db_path) as con:
            con.create_function("cosine_sim", 2, self._cosine_similarity)
            c = con.cursor()
            rows = c.execute(
                "SELECT id,kind,text,cosine_sim(vec, ?) as score FROM items "
                "ORDER BY score DESC LIMIT ?",
                (q_bytes, top_k),
            ).fetchall()
        scored = [
            (score, _id, kind, text)
            for _id, kind, text, score in rows
            if score is not None and score > 0
        ]
        return scored
