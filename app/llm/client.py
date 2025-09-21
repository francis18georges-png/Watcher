"""LLM client that prefers a locally running Ollama server."""

from __future__ import annotations

import http.client
import json
import logging
from urllib.parse import urlparse

from config import get_settings


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
    scheme = parsed.scheme or "http"
    if scheme == "https":
        connection_cls = http.client.HTTPSConnection
        default_port = 443
    else:
        connection_cls = http.client.HTTPConnection
        default_port = 11434

    conn = connection_cls(
        parsed.hostname or "127.0.0.1", parsed.port or default_port, timeout=30
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


def chunk_prompt(prompt: str, *, size: int = 1000) -> list[str]:
    """Yield slices of *prompt* of at most *size* characters."""
    if size <= 0:
        raise ValueError("size must be a positive integer")
    return [prompt[i : i + size] for i in range(0, len(prompt), size)]


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
        ctx: Context window size used by the LLM. Defaults to ``None`` which
            means the value is read from ``config/settings.toml``. Must be a
            positive integer.
        fallback_phrase: Text prefix used when generation fails. When omitted
            the value defined in the configuration is used.
    """

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        *,
        ctx: int | None = None,
        fallback_phrase: str | None = None,
    ) -> None:
        settings = get_settings()
        llm_cfg = settings.llm

        if ctx is not None and ctx < 1:
            raise ValueError("ctx must be a positive integer")

        self.model = model or llm_cfg.model
        self.host = host or llm_cfg.host
        self.ctx = ctx if ctx is not None else llm_cfg.ctx
        self.fallback_phrase = fallback_phrase or llm_cfg.fallback_phrase
        self._offline = False

    def set_offline(self, offline: bool) -> None:
        """Enable or disable offline mode for the client."""

        self._offline = bool(offline)

    def generate(self, prompt: str, *, separator: str = "") -> tuple[str, str]:
        """Return a response and trace for *prompt*.

        Args:
            prompt: Text prompt to send for generation.
            separator: String inserted between responses for each chunk when
                concatenated. Defaults to ``""``.

        The prompt is sent in fixed-size chunks so very large prompts can be
        handled without overwhelming the backend. Successful responses from
        each chunk are concatenated before being returned.
        """

        trace: list[str] = []
        if self._offline:
            trace.extend(["offline", "fallback"])
            return f"{self.fallback_phrase}: {prompt}", " -> ".join(trace)

        try:  # pragma: no cover - network path
            responses: list[str] = []
            for idx, chunk in enumerate(chunk_prompt(prompt)):
                trace.append(f"ollama:{idx}")
                responses.append(
                    generate_ollama(chunk, host=self.host, model=self.model)
                )
            trace.append("success")
            return separator.join(responses), " -> ".join(trace)
        except Exception as exc:
            trace.append(f"error:{exc.__class__.__name__}")
            trace.append("fallback")
            logging.exception("Failed to generate response: %s", exc)
            return f"{self.fallback_phrase}: {prompt}", " -> ".join(trace)
