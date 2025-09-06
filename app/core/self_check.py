"""Simple consistency checks for chat responses."""
from __future__ import annotations

import re
from typing import List


def analyze(prompt: str, answer: str) -> str:
    """Return a human readable error report if obvious mistakes are detected.

    For now only a very small set of heuristics is implemented.  When *prompt*
    contains a basic arithmetic expression like ``"2 + 2"`` the result is
    evaluated and compared to the first number found in *answer*.  A mismatch
    yields an error report, otherwise an empty string is returned.
    """

    report: List[str] = []

    # Detect and evaluate simple arithmetic expressions in the prompt
    expr_match = re.search(r"(\d+\s*[+\-*/]\s*\d+)", prompt)
    if expr_match:
        expr = expr_match.group(1)
        try:
            expected = eval(expr)
            nums = re.findall(r"-?\d+", answer)
            if nums:
                got = int(nums[0])
                if got != expected:
                    report.append(
                        f"Erreur calcul: {expr} = {expected} (pas {got})"
                    )
            else:
                report.append(
                    "Réponse sans nombre pour calcul demandé"
                )
        except Exception:
            # If evaluation fails the check is silently ignored
            pass

    return "\n".join(report)
