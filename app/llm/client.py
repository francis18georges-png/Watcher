"""LLM client that prefers a locally running Ollama server."""

from __future__ import annotations

import http.client
import json


def generate_ollama(prompt: str) -> str:
    """Send *prompt* to a locally running Ollama server.

    The request is performed against ``http://127.0.0.1:11434/api/generate``
    using a JSON payload. The response value is returned as a stripped string.
    """

    conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=30)
    try:  # pragma: no cover - network path
        payload = json.dumps({"model": "llama3.2:3b", "prompt": prompt})
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
    """

    def generate(self, prompt: str) -> str:
        """Return a response for *prompt*."""

        try:  # pragma: no cover - network path
            return generate_ollama(prompt)
        except Exception:
            return f"Echo: {prompt}"
