"""Dummy plugin used in tests."""


class DummyPlugin:
    """Simple plugin returning a marker message."""

    name = "dummy"

    def run(self) -> str:  # pragma: no cover - trivial
        return "dummy plugin loaded"
