"""Simple heuristic critic module.

This module provides a lightweight text evaluation strategy used by the
Watcher project.  The implementation intentionally avoids external network
calls so that the test-suite can run in an isolated environment.  The design
however mirrors how an LLM based critic could be structured by accepting
weights for different quality criteria and producing a granular score.

The critic exposes a :class:`Critic` class whose :meth:`evaluate` method
returns both individual sub‑scores and the combined weighted score.  A caller
can tweak the ``threshold`` and ``weights`` to reflect different quality
requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Critic:
    """Evaluate text quality using simple heuristics.

    Parameters
    ----------
    weights:
        Mapping of criterion name to weighting factor.  The available criteria
        are ``"length"`` and ``"politeness"``.  Additional criteria can be added
        later without affecting the public API.
    threshold:
        Minimum overall score required for ``passed`` to be ``True``.
    """

    weights: dict[str, float] = field(
        default_factory=lambda: {"length": 0.5, "politeness": 0.5}
    )
    threshold: float = 0.75

    def evaluate(self, text: str) -> dict[str, float | dict[str, float] | bool]:
        """Return a granular evaluation of ``text``.

        The evaluation is intentionally simple:

        * ``length`` – proportion of the first 100 words that are populated.
        * ``politeness`` – ``1.0`` when the text contains polite keywords such
          as "please" or "thank you", otherwise ``0.0``.

        Returns
        -------
        dict
            A dictionary with ``score`` (weighted total), ``scores`` containing
            individual criterion scores and ``passed`` which indicates whether
            the score meets the configured threshold.
        """

        words = text.split()
        scores = {
            "length": min(len(words) / 100.0, 1.0),
            "politeness": (
                1.0
                if any(keyword in text.lower() for keyword in ("please", "thank you"))
                else 0.0
            ),
        }

        total_weight = sum(self.weights.values()) or 1.0
        weighted_total = (
            sum(scores.get(k, 0.0) * self.weights.get(k, 0.0) for k in scores)
            / total_weight
        )

        return {
            "score": weighted_total,
            "scores": scores,
            "passed": weighted_total >= self.threshold,
        }


def suggest(prompt: str, answer: str) -> str:
    """Return a simple improvement plan for ``answer``.

    The heuristic mirrors the :class:`Critic` scoring rules.  Two basic
    suggestions are provided:

    * Encourage adding more detail when the length score is low.
    * Request a polite phrase when none is detected.

    Parameters
    ----------
    prompt:
        The original user prompt.  Currently unused but allows future
        expansion to contextual suggestions.
    answer:
        The assistant response to critique.

    Returns
    -------
    str
        A human readable plan combining zero or more improvement steps.
    """

    critic = Critic()
    result = critic.evaluate(answer)
    suggestions: list[str] = []

    if result["scores"].get("length", 0.0) < 0.5:
        suggestions.append("Ajoutez des détails.")
    if result["scores"].get("politeness", 0.0) < 1.0:
        suggestions.append("Ajoutez une formule de politesse.")

    # Present each suggestion on a new line for readability.
    return "\n".join(suggestions)
