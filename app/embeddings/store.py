"""Local vector store backed by SQLite and SentenceTransformers."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from config import get_settings

try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore[assignment]


class _Encoder:
    """Thread-safe lazy loader for the embedding model."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model: SentenceTransformer | None = None
        settings = get_settings()
        self._model_id = settings.memory.embed_model
        self._model_path = settings.paths.resolve(settings.memory.embed_model_path)

    def _load(self) -> SentenceTransformer:
        if SentenceTransformer is None:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "sentence-transformers est requis mais n'est pas installé. "
                "Ajoutez 'sentence-transformers' aux dépendances."
            )

        with self._lock:
            if self._model is None:
                if self._model_path.exists():
                    self._model = SentenceTransformer(
                        str(self._model_path), trust_remote_code=False
                    )
                else:
                    self._model_path.parent.mkdir(parents=True, exist_ok=True)
                    self._model = SentenceTransformer(
                        self._model_id,
                        cache_folder=str(self._model_path.parent),
                        trust_remote_code=False,
                    )
        return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        vectors = model.encode(
            list(texts),
            convert_to_numpy=True,
            show_progress_bar=False,
            device="cpu",
        )
        return np.asarray(vectors, dtype="float32")


class SimpleVectorStore:
    """Persist embeddings in a SQLite database with cosine similarity search."""

    def __init__(self, path: str | Path | None = None, namespace: str = "default"):
        settings = get_settings()
        mem_cfg = settings.memory
        base_path = settings.paths.resolve(mem_cfg.db_path).parent
        default_path = base_path / "vector-store.db"
        self.path = Path(path) if path is not None else default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.namespace = namespace
        self._encoder = _Encoder()
        self._retention = int(mem_cfg.retention_limit)
        self._init_db()

    # ------------------------------------------------------------------
    # Public API

    def add(self, texts: Sequence[str], metas: Sequence[dict[str, Any]]) -> None:
        if len(texts) != len(metas):
            raise ValueError("texts and metas must have the same length")
        if not texts:
            return

        vectors = self._encoder.encode(texts)
        now = time.time()
        payload = [
            (
                self.namespace,
                json.dumps(meta, ensure_ascii=False),
                text,
                memoryview(vec.astype("float32").tobytes()),
                now,
            )
            for text, meta, vec in zip(texts, metas, vectors, strict=True)
        ]

        with self._connect() as con:
            con.executemany(
                """
                INSERT INTO documents(namespace, metadata, text, embedding, created_at)
                VALUES(?,?,?,?,?)
                """,
                payload,
            )
        self._prune()

    def search(self, query: str, k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not query:
            return []

        try:
            q_vector = self._encoder.encode([query])[0]
        except Exception:
            return []

        with self._connect() as con:
            rows = con.execute(
                "SELECT metadata, text, embedding FROM documents WHERE namespace = ?",
                (self.namespace,),
            ).fetchall()

        if not rows:
            return []

        vectors = np.vstack(
            [np.frombuffer(row[2], dtype="float32") for row in rows]
        )
        norms = np.linalg.norm(vectors, axis=1)
        q_norm = float(np.linalg.norm(q_vector))
        if q_norm == 0.0:
            return []
        denom = (norms * q_norm)
        denom[denom == 0.0] = 1e-12
        scores = (vectors @ q_vector) / denom

        paired = [
            (
                self._decode_meta(row[0], row[1]),
                float(score),
            )
            for row, score in zip(rows, scores, strict=True)
        ]
        paired.sort(key=lambda item: item[1], reverse=True)
        return paired[:k]

    # ------------------------------------------------------------------
    # Internal helpers

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    metadata TEXT,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_namespace_created_at "
                "ON documents(namespace, created_at DESC)"
            )

    @staticmethod
    def _decode_meta(raw: str, text: str) -> dict[str, Any]:
        try:
            meta = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            meta = {}
        if "text" not in meta:
            meta["text"] = text
        return meta

    def _prune(self) -> None:
        if self._retention < 1:
            return
        with self._connect() as con:
            rows = con.execute(
                "SELECT id FROM documents WHERE namespace = ? ORDER BY created_at DESC",
                (self.namespace,),
            ).fetchall()
            if len(rows) <= self._retention:
                return
            to_delete = [row[0] for row in rows[self._retention :]]
            con.executemany(
                "DELETE FROM documents WHERE id = ?",
                [(doc_id,) for doc_id in to_delete],
            )


__all__ = ["SimpleVectorStore"]
