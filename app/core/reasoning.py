"""Utilities to record explicit reasoning steps.

This module implements :class:`ReasoningChain`, a lightweight helper that
collects reasoning steps during an interaction.  The chain can be persisted
to :class:`~app.core.memory.Memory` for later inspection which
provides a basic form of explicit reasoning and audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.core.memory import Memory


@dataclass
class ReasoningChain:
    """Container storing a sequence of reasoning steps.

    Examples
    --------
    >>> chain = ReasoningChain()
    >>> chain.add("analyse input")
    >>> chain.add("produce answer")
    >>> chain.to_text()
    'analyse input\nproduce answer'
    """

    steps: List[str] = field(default_factory=list)

    def add(self, step: str) -> None:
        """Append a new reasoning *step* to the chain."""

        self.steps.append(step)

    def clear(self) -> None:
        """Remove all stored steps."""

        self.steps.clear()

    def to_text(self) -> str:
        """Return the chain as a single string joined by newlines."""

        return "\n".join(self.steps)

    def save(self, mem: Memory, kind: str = "reasoning") -> None:
        """Persist the reasoning chain to *mem* using ``Memory.add``.

        Parameters
        ----------
        mem:
            Memory instance where the chain should be stored.
        kind:
            ``kind`` value used when saving to memory.  Defaults to
            ``"reasoning"``.
        """

        if self.steps:
            mem.add(kind, self.to_text())
