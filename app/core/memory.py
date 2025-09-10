import sqlite3
import time
import logging
import math
from pathlib import Path

from app.utils import np

from app.tools.embeddings import embed_ollama


class Memory:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        self._embed_cache: dict[str, np.ndarray] = {}
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
            c.execute("CREATE INDEX IF NOT EXISTS idx_items_kind_ts ON items(kind, ts)")

    def add(self, kind: str, text: str) -> None:
        try:
            vec_arr = self._embed(text)
            vec = vec_arr.astype("float32").tobytes()
        except Exception:
            logging.exception("Failed to embed text for kind '%s'", kind)
            vec = np.array([], dtype=np.float32).tobytes()
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            c.execute(
                "INSERT INTO items(kind,text,vec,ts) VALUES(?,?,?,?)",
                (kind, text, vec, time.time()),
            )

    def summarize(self, kind: str, max_items: int) -> None:
        with sqlite3.connect(self.db_path) as con:
            c = con.cursor()
            rows = c.execute(
                "SELECT id,text FROM items WHERE kind=? ORDER BY ts ASC",
                (kind,),
            ).fetchall()
            if len(rows) <= max_items:
                return
            excess = len(rows) - max_items + 1
            oldest = rows[:excess]
            texts = [t for _, t in oldest]
            summary = " ".join(texts)
            if len(summary) > 200:
                summary = summary[:197] + "..."
            ids = [str(_id) for _id, _ in oldest]
            placeholders = ",".join("?" for _ in ids)
            c.execute(
                f"DELETE FROM items WHERE id IN ({placeholders})",
                ids,
            )
        self.add(kind, summary)

    def add_feedback(self, kind: str, prompt: str, answer: str, rating: float) -> None:
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
        """Compute cosine similarity between two embedded vectors stored as BLOBs.

        The product of vector norms ``b`` is compared to zero using
        :func:`math.isclose` with ``rel_tol=1e-9`` and ``abs_tol=1e-12``.  When
        ``b`` is effectively zero, the similarity is defined as ``0.0`` to avoid
        division by a tiny denominator.
        """
        v1 = np.frombuffer(vec_blob, dtype=np.float32)
        v2 = np.frombuffer(query_blob, dtype=np.float32)
        if len(v1) != len(v2) or len(v1) == 0:
            return 0.0
        b = float(np.linalg.norm(v1) * np.linalg.norm(v2))
        if math.isclose(b, 0.0, rel_tol=1e-9, abs_tol=1e-12):
            return 0.0
        return float((v1 @ v2) / b)

    def search(
        self, query: str, top_k: int = 8, threshold: float = 0.0
    ) -> list[tuple[float, int, str, str]]:
        """Search memory for items similar to ``query``.

        The SQL query is limited to ``top_k`` results using a similarity function to
        avoid loading the entire table into memory.

        Args:
            query: Text to search for.
            top_k: Maximum number of results to return.
            threshold: Minimum acceptable similarity score. When set to a value
                greater than zero, an exception is raised if no results meet
                this threshold.

        Returns:
            A list of tuples ``(score, id, kind, text)`` sorted by descending
            similarity score.
        """
        try:
            q = self._embed(query, use_cache=False).astype("float32")
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
        if threshold > 0 and (not scored or scored[0][0] < threshold):
            raise ValueError(f"no results with score >= {threshold}")
        return scored

    # Internal helpers -------------------------------------------------

    def _embed(self, text: str, use_cache: bool = True) -> np.ndarray:
        """Return embedding for ``text`` using a simple in-memory cache."""
        if use_cache and text in self._embed_cache:
            return self._embed_cache[text]
        vecs = embed_ollama([text])
        vec = vecs[0].astype("float32") if vecs else np.zeros(1, dtype=np.float32)
        if use_cache:
            self._embed_cache[text] = vec
        return vec
