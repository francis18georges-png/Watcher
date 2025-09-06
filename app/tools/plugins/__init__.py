"""Plugin protocol and discovery helpers."""
from __future__ import annotations

from typing import Protocol


class Plugin(Protocol):
    """Simple plugin interface."""

    def run(self) -> str:  # pragma: no cover - interface definition
        """Execute the plugin and return a human readable message."""
        ...
