"""LLM client that prefers a locally running Ollama server."""

from __future__ import annotations

import http.client
import json
import logging
from collections.abc import Iterable
from urllib.parse import urlparse

from config import load_config


def validate_prompt(prompt: str) -> str:
    """Return a sanitized version of *prompt*.

    Leading and trailing whitespace is stripped and an empty prompt raises a
    ``ValueError``.
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    return prompt


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

    def generate(self, prompt: str, *, separator: str = "") -> tuple[str, str]:
        """Return a response and trace for *prompt*.

        If the backend returns chunked responses they are joined using
        ``separator`` (defaults to ``""``) without injecting additional
        whitespace.
        """

        trace: list[str] = []
        try:  # pragma: no cover - network path
            trace.append("ollama")
            resp = generate_ollama(prompt, host=self.host, model=self.model)

            if isinstance(resp, str):
                text = resp
            elif isinstance(resp, Iterable):
                text = separator.join(resp)
            else:  # defensive: unexpected return type
                text = str(resp)

            trace.append("success")
            return text, " -> ".join(trace)
        except Exception as exc:
            trace.append(f"error:{exc.__class__.__name__}")
            trace.append("fallback")
            logging.exception("Failed to generate response: %s", exc)
            return f"{self.fallback_phrase}: {prompt}", " -> ".join(trace)
