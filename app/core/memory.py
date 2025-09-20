import os
import sqlite3
import time
import math
from pathlib import Path
from typing import Iterator, Mapping

from app.utils import np

from app.tools.embeddings import embed_ollama
from app.core.logging_setup import get_logger


logger = get_logger(__name__)


class Memory:
    def __init__(self, db_path: Path, *, sqlcipher: Mapping[str, object] | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlcipher_config = dict(sqlcipher or {})
        self._sqlcipher_enabled = bool(self._sqlcipher_config.get("enabled"))
        self._sqlcipher_password = (
            self._resolve_sqlcipher_password() if self._sqlcipher_enabled else None
        )
        if self._sqlcipher_enabled and not self._sqlcipher_password:
            raise ValueError("SQLCipher is enabled but no password was provided")
        self._sqlcipher_verified = False
        self._embed_cache: dict[str, np.ndarray] = {}
        self._fts5_checked = False
        self._init()

    def _init(self) -> None:
        self._run_migrations()

    def _resolve_sqlcipher_password(self) -> str | None:
        password: str | None = None
        env_var = self._sqlcipher_config.get("password_env")
        if isinstance(env_var, str) and env_var:
            password = os.getenv(env_var) or None
        if not password:
            raw = self._sqlcipher_config.get("password")
            if isinstance(raw, str) and raw:
                password = raw
        return password

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path), timeout=5.0)
        try:
            self._configure_connection(con)
        except Exception:
            con.close()
            raise
        return con

    def _configure_connection(self, con: sqlite3.Connection) -> None:
        self._configure_sqlcipher(con)
        pragmas = (
            "PRAGMA journal_mode=WAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA busy_timeout=5000",
            "PRAGMA secure_delete=ON",
        )
        for pragma in pragmas:
            try:
                con.execute(pragma)
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to apply %s on %s", pragma, self.db_path, exc_info=True
                )
        self._register_fts5(con)

    def _configure_sqlcipher(self, con: sqlite3.Connection) -> None:
        if not self._sqlcipher_enabled:
            return
        assert self._sqlcipher_password is not None
        try:
            con.execute("PRAGMA key = ?", (self._sqlcipher_password,))
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(
                f"Failed to configure SQLCipher key for database {self.db_path}"
            ) from exc
        if self._sqlcipher_verified:
            return
        try:
            row = con.execute("PRAGMA cipher_version").fetchone()
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(
                f"SQLCipher support is not available for database {self.db_path}"
            ) from exc
        if not row or row[0] is None:
            raise RuntimeError(
                f"SQLCipher support is not available for database {self.db_path}"
            )
        self._sqlcipher_verified = True

    def _register_fts5(self, con: sqlite3.Connection) -> None:
        if self._fts5_checked:
            return
        self._fts5_checked = True
        try:
            row = con.execute(
                "SELECT 1 FROM pragma_module_list WHERE name='fts5'"
            ).fetchone()
            if row:
                return
        except sqlite3.DatabaseError:
            logger.debug(
                "Unable to query pragma_module_list for fts5 on %s", self.db_path,
                exc_info=True,
            )
        try:
            con.enable_load_extension(True)
            try:
                con.execute("SELECT load_extension('fts5')")
            finally:
                con.enable_load_extension(False)
        except (AttributeError, sqlite3.DatabaseError):
            logger.info(
                "FTS5 module could not be registered for %s", self.db_path
            )

    def _run_migrations(self) -> None:
        try:
            from alembic import command
            from alembic.config import Config
            from sqlalchemy import create_engine
            from sqlalchemy.pool import StaticPool
        except ModuleNotFoundError as exc:
            logger.warning(
                "Alembic or SQLAlchemy missing (%s); applying schema manually.", exc
            )
            self._ensure_schema()
            return

        base_dir = Path(__file__).resolve().parents[2]
        alembic_ini = base_dir / "alembic.ini"
        if not alembic_ini.exists():
            logger.warning("Alembic configuration not found at %s", alembic_ini)
            self._ensure_schema()
            return

        cfg = Config(str(alembic_ini))
        cfg.set_main_option("script_location", str(base_dir / "migrations"))
        db_uri = self.db_path.resolve().as_posix()
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_uri}")
        cfg.attributes["sqlcipher"] = {
            "enabled": self._sqlcipher_enabled,
            "password": self._sqlcipher_password,
        }

        engine = create_engine(
            "sqlite://",
            creator=self._connect,
            poolclass=StaticPool,
        )

        try:
            with engine.connect() as connection:
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, "head")
        except Exception:
            logger.exception("Failed to apply Alembic migrations; falling back to SQL")
            self._ensure_schema()
        finally:
            engine.dispose()

    def _ensure_schema(self) -> None:
        with self._connect() as con:
            c = con.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS items(
                    id INTEGER PRIMARY KEY,
                    kind TEXT,
                    text TEXT,
                    vec BLOB,
                    ts REAL
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_kind_ts ON items(kind, ts)"
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback(
                    id INTEGER PRIMARY KEY,
                    kind TEXT,
                    prompt TEXT,
                    answer TEXT,
                    rating REAL,
                    ts REAL
                )
                """
            )

    def add(self, kind: str, text: str) -> None:
        try:
            vec_arr = self._embed(text)
            vec = vec_arr.astype("float32").tobytes()
        except Exception:
            logger.exception("Failed to embed text for kind '%s'", kind)
            vec = np.array([], dtype=np.float32).tobytes()
        with self._connect() as con:
            c = con.cursor()
            c.execute(
                "INSERT INTO items(kind,text,vec,ts) VALUES(?,?,?,?)",
                (kind, text, vec, time.time()),
            )

    def summarize(self, kind: str, max_items: int) -> None:
        with self._connect() as con:
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
        with self._connect() as con:
            c = con.cursor()
            c.execute(
                "INSERT INTO feedback(kind,prompt,answer,rating,ts) VALUES(?,?,?,?,?)",
                (kind, prompt, answer, rating, time.time()),
            )

    def all_feedback(self) -> list[tuple[str, str, str, float]]:
        """Return all stored feedback entries."""
        with self._connect() as con:
            c = con.cursor()
            rows = c.execute(
                "SELECT kind,prompt,answer,rating FROM feedback"
            ).fetchall()
        return rows

    def iter_feedback(
        self, batch_size: int = 100
    ) -> Iterator[tuple[str, str, str, float]]:
        """Yield stored feedback entries in batches.

        Parameters
        ----------
        batch_size:
            Number of rows to fetch per batch.

        Yields
        ------
        tuple[str, str, str, float]
            Each ``(kind, prompt, answer, rating)`` tuple from the
            ``feedback`` table.
        """

        with self._connect() as con:
            c = con.cursor()
            c.execute("SELECT kind,prompt,answer,rating FROM feedback")
            while True:
                rows = c.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    yield row

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
            logger.exception("Failed to embed search query")
            return []
        q_bytes = q.tobytes()
        with self._connect() as con:
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
