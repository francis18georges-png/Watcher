"""Arithmetic self-check utilities."""

from __future__ import annotations

import re
from typing import Callable

from app.core.memory import Memory


_OPERATORS: dict[str, Callable[[int, int], int]] = {
    '+': lambda a, b: a + b,
    '-': lambda a, b: a - b,
    '*': lambda a, b: a * b,
    '/': lambda a, b: a // b if b != 0 else 0,
}


def self_check(answer: str, mem: Memory | None = None) -> str | None:
    """Validate simple arithmetic expressions inside *answer*.

    The function looks for patterns of the form ``"A op B = C"`` where
    ``op`` is one of ``+``, ``-``, ``*`` or ``/``. When the expression is
    incorrect a human readable report is returned and optionally stored in
    ``mem`` under the ``"report"`` kind. Correct expressions return ``None``
    and do not touch memory.
    """

    match = re.search(r"(\d+)\s*([+\-*/])\s*(\d+)\s*=\s*(\d+)", answer)
    if not match:
        return None

    a, op, b, res = match.groups()
    a_i, b_i, res_i = int(a), int(b), int(res)
    calc = _OPERATORS.get(op)
    if calc is None:
        return None
    expected = calc(a_i, b_i)
    if expected != res_i:
        report = f"expected {expected} but got {res_i} for {a} {op} {b}"
        if mem is not None:
            mem.add("report", report)
        return report
    return None
