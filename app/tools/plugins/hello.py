"""Demonstration Hello plugin."""


class HelloPlugin:
    """Plugin de démonstration qui retourne un message de salutation."""

    name = "hello"

    def run(self) -> str:
        return "Hello from plugin"
