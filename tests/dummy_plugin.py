"""Dummy plugin used in tests."""

# mypy: ignore-errors


class DummyPlugin:
    """Simple plugin returning a marker message."""

    def run(self) -> str:  # pragma: no cover - trivial
        return "dummy plugin loaded"
