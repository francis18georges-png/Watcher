"""Self-check utilities for verifying arithmetic answers.

This module provides a lightweight :func:`analyze` function that evaluates
simple arithmetic expressions contained in free-form text.  It is used to
check that a model's response matches the expected result for the expression.
Numbers are parsed as :class:`float` to support division and negative values
and results are compared using :func:`math.isclose` to avoid issues with
floating point precision.
"""

from __future__ import annotations

import math
import re

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def analyze(problem: str, response: str, *, rel_tol: float = 1e-9, abs_tol: float = 1e-9) -> bool:
    """Analyze a simple arithmetic *problem* and check *response*.

    Parameters
    ----------
    problem:
        Text containing a binary arithmetic operation (e.g. ``"2 + 2"``).
    response:
        Text containing the model's answer.
    rel_tol, abs_tol:
        Tolerances forwarded to :func:`math.isclose` when comparing floating
        point results.

    Returns
    -------
    bool
        ``True`` if the numeric value found in *response* matches the computed
        result of the expression within the given tolerance; otherwise
        ``False``.
    """

    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)", problem)
    if not match:
        return False

    a, op, b = float(match.group(1)), match.group(2), float(match.group(3))

    ans_match = _NUM_RE.search(response)
    if not ans_match:
        return False
    result = float(ans_match.group())

    if op == "+":
        expected = a + b
    elif op == "-":
        expected = a - b
    elif op == "*":
        expected = a * b
    elif op == "/":
        if b == 0:
            return False
        expected = a / b
    else:  # pragma: no cover - regex restricts operators but keep for safety
        return False

    return math.isclose(result, expected, rel_tol=rel_tol, abs_tol=abs_tol)
