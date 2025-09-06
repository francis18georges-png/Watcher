"""Simple critic module evaluating LLM responses."""

from __future__ import annotations


def review(prompt: str, answer: str) -> float:
    """Return a naive quality score for *answer* given *prompt*.

    The current implementation is intentionally lightweight: it merely checks
    that the answer is non-empty and returns a float in the ``[0, 1]`` range.
    A real implementation could hook into an LLM-based evaluator or any other
    heuristic.  This function is easily monkeypatched in tests to emulate
    various critic behaviours.
    """

    return 1.0 if answer.strip() else 0.0
