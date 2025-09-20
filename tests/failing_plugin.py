"""Plugin intentionally raising an error for tests."""


class FailingPlugin:
    """Simple plugin that always fails."""

    name = "failing"

    def run(self) -> str:  # pragma: no cover - deterministic failure
        raise RuntimeError("boom")
