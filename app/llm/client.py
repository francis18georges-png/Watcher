"""LLM client that prefers a locally running Ollama server."""

from __future__ import annotations

import http.client
import json
import logging
from urllib.parse import urlparse

from config import load_config


def generate_ollama(prompt: str, *, host: str, model: str) -> str:
    """Send *prompt* to an Ollama server.

    Args:
        prompt: Text prompt to send for generation.
        host: Hostname (and optional port) of the Ollama server.
        model: Model identifier used for the request.

    The response value is returned as a stripped string.
    """

    parsed = urlparse(host if "://" in host else f"http://{host}")
    conn = http.client.HTTPConnection(
        parsed.hostname or "127.0.0.1", parsed.port or 11434, timeout=30
    )
    try:  # pragma: no cover - network path
        payload = json.dumps({"model": model, "prompt": prompt})
        conn.request(
            "POST",
            "/api/generate",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"Generate request failed: {resp.status}")
        data = json.loads(resp.read())
        return data.get("response", "").strip()
    finally:
        try:
            conn.close()
        except Exception:  # pragma: no cover - defensive
            pass


class Client:
    """Generate text using an LLM backend.

    A locally running Ollama server is preferred. If it cannot be reached a
    deterministic echo response is returned so the rest of the application can
    continue to function in offline mode.

    Args:
        model: Model identifier passed to the Ollama server. If omitted, the
            value is read from ``config/settings.toml``.
        host: Hostname (and optional port) of the Ollama server. If omitted,
            the value is read from ``config/settings.toml``.
        fallback_phrase: Text prefix used when generation fails. Defaults to
            ``"Echo"``.
    """

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        *,
        fallback_phrase: str = "Echo",
    ) -> None:
        cfg = load_config().get("llm", {})

        if model is not None:
            cfg["model"] = model
        if host is not None:
            cfg["host"] = host

        self.model = cfg.get("model", "llama3.2:3b")
        self.host = cfg.get("host", "127.0.0.1:11434")
        self.fallback_phrase = fallback_phrase

    def generate(self, prompt: str) -> str:
        """Return a response for *prompt*."""

        try:  # pragma: no cover - network path
            return generate_ollama(prompt, host=self.host, model=self.model)
        except Exception as exc:
            logging.exception("Failed to generate response: %s", exc)
            return f"{self.fallback_phrase}: {prompt}"
