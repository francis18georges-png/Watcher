"""Demonstration Hello plugin."""

from __future__ import annotations

import hashlib
from pathlib import Path


class HelloPlugin:
    """Plugin de démonstration qui retourne un message de salutation."""

    name = "hello"
    api_version = "1.0"
    signature = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def run(self) -> str:
        return "Hello from plugin"
