"""Utility helpers to collect simple performance metrics."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import logging
import time
from typing import Iterator, List, MutableSequence, Any


@dataclass
class PerformanceMetrics:
    """Collects timing, evaluation scores and error logs."""

    max_entries: int | None = None
    response_times: List[float] = field(default_factory=list)
    evaluation_scores: List[float] = field(default_factory=list)
    error_logs: List[str] = field(default_factory=list)
    engine_calls: int = 0
    db_calls: int = 0
    plugin_calls: int = 0
    engine_response_times: List[float] = field(default_factory=list)
    db_response_times: List[float] = field(default_factory=list)
    plugin_response_times: List[float] = field(default_factory=list)
    engine_time_total: float = 0.0
    db_time_total: float = 0.0
    plugin_time_total: float = 0.0

    def _append_with_limit(self, seq: MutableSequence[Any], value: Any) -> None:
        seq.append(value)
        if self.max_entries is not None and len(seq) > self.max_entries:
            del seq[0]

    def log_response_time(self, duration: float) -> None:
        """Record a new response time measurement."""

        self._append_with_limit(self.response_times, duration)

    def log_evaluation_score(self, score: float) -> None:
        """Record a new evaluation score."""

        self._append_with_limit(self.evaluation_scores, score)

    def log_error(self, message: str) -> None:
        """Record an error message and forward it to the logger."""

        self._append_with_limit(self.error_logs, message)
        logging.getLogger(__name__).error(message)

    @contextmanager
    def track_engine(self) -> Iterator[None]:
        """Measure and log the duration of an engine call."""

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.engine_calls += 1
            self._append_with_limit(self.engine_response_times, duration)
            self.engine_time_total += duration
            self.log_response_time(duration)

    @contextmanager
    def track_db(self) -> Iterator[None]:
        """Measure and log the duration of a database call."""

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.db_calls += 1
            self._append_with_limit(self.db_response_times, duration)
            self.db_time_total += duration
            self.log_response_time(duration)

    @contextmanager
    def track_plugin(self) -> Iterator[None]:
        """Measure and log the duration of a plugin execution."""

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.plugin_calls += 1
            self._append_with_limit(self.plugin_response_times, duration)
            self.plugin_time_total += duration
            self.log_response_time(duration)


# Shared instance used across the application.
metrics = PerformanceMetrics()

__all__ = ["PerformanceMetrics", "metrics"]
