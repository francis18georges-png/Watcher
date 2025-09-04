"""LLM client with optional OpenAI integration."""

from __future__ import annotations

import os


class Client:
    """Generate text using an LLM backend.

    If an OpenAI API key is available the client will attempt to call the
    `openai` package. Otherwise a deterministic echo response is returned.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    def generate(self, prompt: str) -> str:
        """Return a response for *prompt*.

        When the OpenAI SDK or API key is missing, a simple echo is produced so
        the rest of the application can continue to function in offline mode.
        """

        if self.api_key:
            try:  # pragma: no cover - network path
                import openai  # type: ignore[import-not-found]

                openai.api_key = self.api_key
                resp = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp["choices"][0]["message"]["content"].strip()
            except Exception:
                # Fall back to a deterministic response in case of errors
                pass

        return f"Echo: {prompt}"
