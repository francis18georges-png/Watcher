"""Utility helpers to collect simple performance metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import List


@dataclass
class PerformanceMetrics:
    """Collects timing, evaluation scores and error logs."""

    response_times: List[float] = field(default_factory=list)
    evaluation_scores: List[float] = field(default_factory=list)
    error_logs: List[str] = field(default_factory=list)

    def log_response_time(self, duration: float) -> None:
        """Record a new response time measurement."""

        self.response_times.append(duration)

    def log_evaluation_score(self, score: float) -> None:
        """Record a new evaluation score."""

        self.evaluation_scores.append(score)

    def log_error(self, message: str) -> None:
        """Record an error message and forward it to the logger."""

        self.error_logs.append(message)
        logging.getLogger(__name__).error(message)


# Shared instance used across the application.
metrics = PerformanceMetrics()

__all__ = ["PerformanceMetrics", "metrics"]

