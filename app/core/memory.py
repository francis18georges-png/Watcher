import math
import os
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from app.utils import np

from app.tools.embeddings import embed_ollama
from app.core.logging_setup import get_logger


if TYPE_CHECKING:  # pragma: no cover - imported for type hints only
    from sqlalchemy.engine import Engine

logger = get_logger(__name__)


class Memory:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._embed_cache: dict[str, np.ndarray] = {}
        self._fts5_checked = False
        self._fts5_available = False
        self._fts5_requires_extension = False
        self._sqlcipher_requested = self._is_sqlcipher_enabled()
        self._sqlcipher_password = os.getenv("WATCHER_MEMORY_SQLCIPHER_PASSWORD")
        self._sqlcipher_available = self._detect_sqlcipher()
        if self._sqlcipher_requested and not self._sqlcipher_available:
            logger.warning(
                "SQLCipher was requested but the sqlite3 module does not expose it; "
                "continuing without encryption",
            )
        if self._sqlcipher_requested and not self._sqlcipher_password:
            logger.warning(
                "SQLCipher is enabled but no WATCHER_MEMORY_SQLCIPHER_PASSWORD was provided; "
                "continuing without encryption",
            )
        self._sqlcipher_enabled = (
            self._sqlcipher_requested
            and self._sqlcipher_available
            and bool(self._sqlcipher_password)
        )
        self._sqlcipher_key_sql = (
            f"PRAGMA key = '{self._sqlcipher_password.replace("'", "''")}'"
            if self._sqlcipher_enabled and self._sqlcipher_password
            else ""
        )
        self._init()

    def _init(self) -> None:
        self._run_migrations()

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

    @staticmethod
    def _is_sqlcipher_enabled() -> bool:
        value = os.getenv("WATCHER_MEMORY_ENABLE_SQLCIPHER", "")
        return value.lower() in {"1", "true", "yes", "on"}

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        self._apply_connection_settings(con)
        return con

    def _apply_connection_settings(self, con: sqlite3.Connection) -> None:
        self._configure_sqlcipher(con)
        self._apply_pragmas(con)

    def _apply_pragmas(self, con: sqlite3.Connection) -> None:
        pragma_statements = (
            "PRAGMA journal_mode=WAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA busy_timeout=5000",
            "PRAGMA secure_delete=ON",
        )
        for pragma in pragma_statements:
            try:
                con.execute(pragma)
            except sqlite3.DatabaseError:
                logger.debug("Failed to apply pragma '%s'", pragma, exc_info=True)
        self._ensure_fts5(con)

    def _ensure_fts5(self, con: sqlite3.Connection) -> None:
        need_extension_load = self._fts5_requires_extension

        if not self._fts5_checked:
            self._fts5_checked = True
            try:
                options = [row[0] for row in con.execute("PRAGMA compile_options")]
            except sqlite3.DatabaseError:
                options = []
            if any("FTS5" in str(option).upper() for option in options):
                self._fts5_available = True
                self._fts5_requires_extension = False
                logger.debug("FTS5 support detected via compile options")
                return
            need_extension_load = True
            self._fts5_requires_extension = True

        if not need_extension_load:
            return

        try:
            enable_load_extension = getattr(con, "enable_load_extension")
        except AttributeError:
            logger.debug(
                "FTS5 extension loading is not supported by this sqlite3 build"
            )
            return
        try:
            enable_load_extension(True)
            con.load_extension("fts5")
            self._fts5_available = True
            logger.debug("FTS5 extension successfully loaded")
        except (sqlite3.DatabaseError, sqlite3.OperationalError):
            self._fts5_available = False
            logger.debug("FTS5 extension could not be loaded", exc_info=True)
        finally:
            try:
                enable_load_extension(False)
            except Exception:  # pragma: no cover - defensive cleanup
                pass

    def _configure_sqlcipher(self, con: sqlite3.Connection) -> None:
        if not self._sqlcipher_enabled or not self._sqlcipher_key_sql:
            return
        try:
            con.execute(self._sqlcipher_key_sql)
        except sqlite3.DatabaseError:
            logger.warning(
                "Failed to configure SQLCipher; encryption will be disabled",
                exc_info=True,
            )
            self._sqlcipher_enabled = False

    def _run_migrations(self) -> None:
        try:
            from alembic import command
            from alembic.config import Config
            from sqlalchemy import create_engine, event
        except ImportError as exc:  # pragma: no cover - depends on environment
            logger.warning(
                "Alembic or SQLAlchemy unavailable (%s); falling back to direct schema setup",
                exc,
            )
            self._create_schema_fallback()
            return

        ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
        if not ini_path.exists():
            logger.error("Alembic configuration file not found at %s", ini_path)
            self._create_schema_fallback()
            return
        config = Config(str(ini_path))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
        engine = self._create_alembic_engine(create_engine, event)
        try:
            with engine.connect() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        except Exception:
            logger.exception("Alembic migration failed; falling back to direct schema setup")
            self._create_schema_fallback()
        finally:
            engine.dispose()

    def _create_schema_fallback(self) -> None:
        with self._connect() as con:
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

    def _create_alembic_engine(self, create_engine, event) -> "Engine":
        if self._sqlcipher_enabled:
            # SQLCipher requires configuring each DB-API connection manually.
            def _creator() -> sqlite3.Connection:
                con = sqlite3.connect(self.db_path)
                self._apply_connection_settings(con)
                return con

            return create_engine("sqlite://", creator=_creator)

        engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_connection, _connection_record):  # pragma: no cover - SQLAlchemy hook
            self._apply_connection_settings(dbapi_connection)

        return engine

    @staticmethod
    def _detect_sqlcipher() -> bool:
        try:
            with sqlite3.connect(":memory:") as con:
                rows = con.execute("PRAGMA cipher_version").fetchall()
        except sqlite3.DatabaseError:
            return False
        return bool(rows and rows[0] and rows[0][0])

    @property
    def sqlcipher_available(self) -> bool:
        return self._sqlcipher_available

    @property
    def sqlcipher_enabled(self) -> bool:
        return self._sqlcipher_enabled

    @property
    def fts5_available(self) -> bool:
        return self._fts5_available

    def _embed(self, text: str, use_cache: bool = True) -> np.ndarray:
        """Return embedding for ``text`` using a simple in-memory cache."""
        if use_cache and text in self._embed_cache:
            return self._embed_cache[text]
        vecs = embed_ollama([text])
        vec = vecs[0].astype("float32") if vecs else np.zeros(1, dtype=np.float32)
        if use_cache:
            self._embed_cache[text] = vec
        return vec
